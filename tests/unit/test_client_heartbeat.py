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
import asyncio

from aiotrino.client import _RequestHeartbeat


class _FakeResponse:
    def __init__(self, status: int = 200) -> None:
        self.status = status
        self.ok = status < 400
        self.closed = False

    def close(self) -> None:
        self.closed = True


class _FakeRequest:
    def __init__(self, status: int = 200) -> None:
        self.next_uri = "http://coordinator/v1/statement/next"
        self._status = status
        self.head_calls = 0

    async def head(self, uri: str) -> _FakeResponse:
        self.head_calls += 1
        return _FakeResponse(self._status)


async def test_heartbeat_sends_head_requests():
    request = _FakeRequest()
    async with _RequestHeartbeat(request, interval=0.01):
        await asyncio.sleep(0.05)
    assert request.head_calls >= 1


async def test_heartbeat_stops_when_unsupported():
    request = _FakeRequest(status=404)
    heartbeat = _RequestHeartbeat(request, interval=0.01)
    async with heartbeat:
        await asyncio.sleep(0.05)
        # A 404/405 means the server can't answer heartbeats: the loop must exit on its own.
        assert heartbeat._task.done()
    assert request.head_calls == 1


async def test_heartbeat_stops_when_no_next_uri():
    request = _FakeRequest()
    request.next_uri = None
    heartbeat = _RequestHeartbeat(request, interval=0.01)
    async with heartbeat:
        await asyncio.sleep(0.03)
        assert heartbeat._task.done()
    assert request.head_calls == 0
