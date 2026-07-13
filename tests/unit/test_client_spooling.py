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
