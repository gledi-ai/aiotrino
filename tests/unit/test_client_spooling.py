# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import base64
import json
from unittest import mock

import pytest

import aiotrino.client
from aiotrino.client import (
    ClientSession,
    SegmentIterator,
    TrinoQuery,
    TrinoRequest,
    TrinoResult,
    TrinoStatus,
    _prepend_row,
)


def _inline_segment(rows):
    return {
        "type": "inline",
        "data": base64.b64encode(json.dumps(rows).encode()).decode(),
        "metadata": {"rowsCount": len(rows)},
    }


def _status(rows, next_uri=None, columns=None):
    return TrinoStatus(
        id="q1",
        stats={},
        warnings=[],
        info_uri="http://coordinator/query.html?q1",
        next_uri=next_uri,
        update_type=None,
        update_count=None,
        rows=rows,
        columns=columns,
    )


def _spooled_status(segments, **kwargs):
    return _status({"encoding": "json", "segments": segments}, **kwargs)


COLUMNS = [{"name": "a", "type": "integer"}]


async def test_fetch_returns_lazy_segment_iterator():
    session = ClientSession(user="test", encoding="json")
    async with TrinoRequest(host="coordinator", port=8080, client_session=session, http_scheme="http") as request:
        request._next_uri = "http://coordinator/v1/statement/q1/1"
        query = TrinoQuery(request, query="SELECT 1")
        query._row_mapper = mock.Mock()
        query._row_mapper.map.side_effect = lambda rows: rows

        status = _spooled_status([_inline_segment([[1], [2]]), _inline_segment([[3]])])
        with (
            mock.patch.object(request, "get", mock.AsyncMock(return_value=mock.Mock())),
            mock.patch.object(request, "process", mock.AsyncMock(return_value=status)),
        ):
            result = await query.fetch()

        assert isinstance(result, SegmentIterator)
        # Nothing decoded/mapped until the iterator is consumed
        assert query._row_mapper.map.call_count == 0
        assert [row async for row in result] == [[1], [2], [3]]


async def test_execute_spooling_blocks_until_first_row_and_keeps_order():
    session = ClientSession(user="test", encoding="json")
    async with TrinoRequest(host="coordinator", port=8080, client_session=session, http_scheme="http") as request:
        query = TrinoQuery(request, query="SELECT 1")
        query._row_mapper = mock.Mock()
        query._row_mapper.map.side_effect = lambda rows: rows

        post_status = _status([], next_uri="http://coordinator/v1/statement/q1/1", columns=COLUMNS)
        fetch_status = _spooled_status([_inline_segment([[1], [2]]), _inline_segment([[3]])], columns=COLUMNS)
        with (
            mock.patch.object(request, "post", mock.AsyncMock(return_value=mock.Mock())),
            mock.patch.object(request, "get", mock.AsyncMock(return_value=mock.Mock())),
            mock.patch.object(request, "process", mock.AsyncMock(side_effect=[post_status, fetch_status])),
        ):
            result = await query.execute()

        # Blocked until the first row arrived: initial empty POST rows mapped,
        # first segment decoded, second segment still pending
        assert query._row_mapper.map.call_count == 2
        # First row consumed by execute() is prepended back: no loss, no duplication
        assert [row async for row in result] == [[1], [2], [3]]
        assert query._row_mapper.map.call_count == 3
        assert result.rownumber == 3


async def test_get_columns_spooling_preserves_buffered_rows():
    session = ClientSession(user="test", encoding="json")
    async with TrinoRequest(host="coordinator", port=8080, client_session=session, http_scheme="http") as request:
        query = TrinoQuery(request, query="SELECT 1")
        query._query_id = "q1"
        query._row_mapper = mock.Mock()
        query._row_mapper.map.side_effect = lambda rows: rows
        query._result = TrinoResult(query, [])

        status = _spooled_status([_inline_segment([[1], [2]]), _inline_segment([[3]])], columns=COLUMNS)
        with (
            mock.patch.object(request, "get", mock.AsyncMock(return_value=mock.Mock())),
            mock.patch.object(request, "process", mock.AsyncMock(return_value=status)),
        ):
            columns = await query.get_columns()

        assert columns == COLUMNS
        # Row consumed while waiting for columns is prepended back
        assert [row async for row in query._result] == [[1], [2], [3]]


async def test_prepend_row_keeps_order():
    async def rest():
        yield [2]
        yield [3]

    assert [row async for row in _prepend_row([1], rest())] == [[1], [2], [3]]


async def test_result_iterates_lazy_rows():
    query = mock.Mock()
    query.finished = True

    async def rows():
        yield [1]
        yield [2]

    result = TrinoResult(query, _prepend_row([0], rows()))
    assert [row async for row in result] == [[0], [1], [2]]
    assert result.rownumber == 3


async def test_result_iterator_recovers_after_transient_error():
    """A transient error while iterating must propagate but leave the iterator usable so a retried
    __anext__ resumes instead of silently dropping the remaining rows (regression for the previous
    generator-based TrinoResult, which was finalized by any raised exception)."""
    query = mock.Mock()
    query.finished = True

    class FlakyRows:
        def __init__(self, rows, fail_at):
            self._rows = list(rows)
            self._i = 0
            self._fail_at = fail_at
            self._failed = False

        def __aiter__(self):
            return self

        async def __anext__(self):
            if self._i == self._fail_at and not self._failed:
                self._failed = True
                raise RuntimeError("transient")
            if self._i >= len(self._rows):
                raise StopAsyncIteration
            row = self._rows[self._i]
            self._i += 1
            return row

    result = TrinoResult(query, FlakyRows([[1], [2], [3]], fail_at=1))
    collected = []
    iterator = result.__aiter__()
    while True:
        try:
            collected.append(await iterator.__anext__())
        except RuntimeError:
            continue
        except StopAsyncIteration:
            break

    assert collected == [[1], [2], [3]]
    assert result.rownumber == 3


async def test_segment_iterator_retries_failed_segment():
    """If decoding a segment fails, that same segment is retried on the next call instead of being
    acknowledged and skipped, so no rows are lost."""
    session = ClientSession(user="test", encoding="json")
    async with TrinoRequest(host="coordinator", port=8080, client_session=session, http_scheme="http") as request:
        request._next_uri = "http://coordinator/v1/statement/q1/1"
        query = TrinoQuery(request, query="SELECT 1")
        query._row_mapper = mock.Mock()
        query._row_mapper.map.side_effect = lambda rows: rows

        status = _spooled_status([_inline_segment([[1], [2]]), _inline_segment([[3]])])
        with (
            mock.patch.object(request, "get", mock.AsyncMock(return_value=mock.Mock())),
            mock.patch.object(request, "process", mock.AsyncMock(return_value=status)),
        ):
            iterator = await query.fetch()

        real_decode = aiotrino.client.SegmentDecoder.decode
        attempts = {"n": 0}

        async def flaky_decode(self, segment):
            attempts["n"] += 1
            if attempts["n"] == 1:
                raise RuntimeError("transient download failure")
            return await real_decode(self, segment)

        collected = []
        with mock.patch.object(aiotrino.client.SegmentDecoder, "decode", flaky_decode):
            segment_iterator = iterator.__aiter__()
            while True:
                try:
                    collected.append(await segment_iterator.__anext__())
                except RuntimeError:
                    continue
                except StopAsyncIteration:
                    break

        assert collected == [[1], [2], [3]]


async def test_stats_callback_invoked_on_execute():
    session = ClientSession(user="test", encoding="json")
    async with TrinoRequest(host="coordinator", port=8080, client_session=session, http_scheme="http") as request:
        received = []
        query = TrinoQuery(request, query="SELECT 1", stats_callback=received.append)
        query._row_mapper = mock.Mock()
        query._row_mapper.map.side_effect = lambda rows: rows

        status = _status([[1]], columns=COLUMNS)
        with (
            mock.patch.object(request, "post", mock.AsyncMock(return_value=mock.Mock())),
            mock.patch.object(request, "process", mock.AsyncMock(return_value=status)),
        ):
            await query.execute()

        assert received, "stats callback should be invoked"
        assert "queryId" in received[-1]
        # The callback receives a deep copy, not the live stats dict.
        assert received[-1] is not query._stats


async def test_execute_update_statement_drains_to_terminal_state():
    """Regression for https://github.com/trinodb/trino-python-client/issues/601: an update statement
    must be drained to a terminal state during execute() so closing the cursor does not cancel an
    already-completed statement."""
    session = ClientSession(user="test")
    async with TrinoRequest(host="coordinator", port=8080, client_session=session, http_scheme="http") as request:
        query = TrinoQuery(request, query="INSERT INTO t VALUES (1)")
        query._row_mapper = mock.Mock()
        query._row_mapper.map.side_effect = lambda rows: rows

        post_status = _status([], next_uri="http://coordinator/v1/statement/q1/1", columns=COLUMNS)
        update_status = TrinoStatus(
            id="q1",
            stats={},
            warnings=[],
            info_uri="http://coordinator/query.html?q1",
            next_uri="http://coordinator/v1/statement/q1/2",
            update_type="INSERT",
            update_count=1000,
            rows=[[1000]],
            columns=COLUMNS,
        )
        final_status = TrinoStatus(
            id="q1",
            stats={},
            warnings=[],
            info_uri="http://coordinator/query.html?q1",
            next_uri=None,
            update_type="INSERT",
            update_count=1000,
            rows=[],
            columns=COLUMNS,
        )
        with (
            mock.patch.object(request, "post", mock.AsyncMock(return_value=mock.Mock())),
            mock.patch.object(request, "get", mock.AsyncMock(return_value=mock.Mock())),
            mock.patch.object(
                request, "process", mock.AsyncMock(side_effect=[post_status, update_status, final_status])
            ),
        ):
            await query.execute()

        assert query.finished is True
        assert query.update_count == 1000


async def test_spooled_segment_forwards_custom_headers_only_to_coordinator():
    """User-supplied custom headers are forwarded to the Trino coordinator but never to external
    storage (e.g. S3 presigned URLs) where they can break the request."""
    session = ClientSession(user="test", encoding="json")
    async with TrinoRequest(host="coordinator", port=8080, client_session=session, http_scheme="http") as request:
        segment_to = {
            "type": "spooled",
            "uri": "http://coordinator/v1/spooled/segment1",
            "ackUri": "http://coordinator/v1/spooled/segment1/ack",
            "metadata": {"rowsCount": 1},
            "headers": {"x-amz-meta": ["v"]},
        }
        segment = aiotrino.client.SpooledSegment(
            segment_to, request, coordinator_host="coordinator", custom_headers={"X-Auth-Gateway": "token"}
        )
        request._get = mock.AsyncMock(return_value=mock.Mock())

        await segment._send_spooling_request("http://coordinator/v1/spooled/segment1")
        _, kwargs = request._get.call_args
        assert kwargs["headers"]["X-Auth-Gateway"] == "token"
        assert kwargs["headers"]["x-amz-meta"] == "v"

        request._get.reset_mock()
        await segment._send_spooling_request("http://external-storage.example.com/blob")
        _, kwargs = request._get.call_args
        assert "X-Auth-Gateway" not in kwargs["headers"]
        assert kwargs["headers"]["x-amz-meta"] == "v"


async def test_result_iterator_reraises_persistent_error_instead_of_stopping():
    """A persistent error must keep surfacing instead of turning into StopAsyncIteration, which the
    dbapi would report as a normally exhausted result set."""
    query = mock.Mock()
    query.finished = True

    class FailingRows:
        def __init__(self):
            self._count = 0

        def __aiter__(self):
            return self

        async def __anext__(self):
            if self._count >= 3:
                raise OSError("segment download failed")
            self._count += 1
            return [self._count]

    iterator = TrinoResult(query, FailingRows()).__aiter__()
    assert [await iterator.__anext__() for _ in range(3)] == [[1], [2], [3]]
    for _ in range(2):
        with pytest.raises(OSError):
            await iterator.__anext__()


async def test_result_iterator_resumes_after_transient_fetch_error():
    class FlakyQuery:
        def __init__(self):
            self.finished = False
            self._fetches = 0

        async def fetch(self):
            self._fetches += 1
            if self._fetches == 1:
                raise OSError("connection reset")
            self.finished = True
            return [[2]]

    iterator = TrinoResult(FlakyQuery(), [[1]]).__aiter__()
    # The next batch is prefetched before the first row is served, so the fetch error surfaces first.
    with pytest.raises(OSError):
        await iterator.__anext__()
    assert await iterator.__anext__() == [1]
    assert await iterator.__anext__() == [2]
    with pytest.raises(StopAsyncIteration):
        await iterator.__anext__()


async def test_spooled_segment_header_takes_precedence_over_custom_header():
    session = ClientSession(user="test", encoding="json")
    async with TrinoRequest(host="coordinator", port=8080, client_session=session, http_scheme="http") as request:
        segment_to = {
            "type": "spooled",
            "uri": "http://coordinator/v1/spooled/segment1",
            "ackUri": "http://coordinator/v1/spooled/segment1/ack",
            "metadata": {"rowsCount": 1},
            "headers": {"X-Trino-Spooling-Token": ["token-abc"]},
        }
        segment = aiotrino.client.SpooledSegment(
            segment_to,
            request,
            coordinator_host="coordinator",
            custom_headers={"X-Trino-Spooling-Token": "should-not-be-used"},
        )
        request._get = mock.AsyncMock(return_value=mock.Mock())

        await segment._send_spooling_request(segment.uri)
        _, kwargs = request._get.call_args
        assert kwargs["headers"]["X-Trino-Spooling-Token"] == "token-abc"
