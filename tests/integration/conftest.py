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
import os
import socket
import sys
from contextlib import closing
from pathlib import Path

import pytest
from testcontainers.compose import DockerCompose

import aiotrino.logging
from aiotrino.constants import DEFAULT_PORT


TRINO_HOST = "localhost"
TRINO_VERSION = os.environ.get("TRINO_VERSION") or "latest"
COMPOSE_DIR = Path(__file__).parents[2] / "etc"


logger = aiotrino.logging.get_logger(__name__)


def is_trino_available(host, port):
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.settimeout(2)
        result = sock.connect_ex((host, port))
        if result == 0:
            return True
    return False


@pytest.fixture(scope="session")
def run_trino():
    host = os.environ.get("TRINO_RUNNING_HOST", TRINO_HOST)
    port = int(os.environ.get("TRINO_RUNNING_PORT", DEFAULT_PORT))

    # Is there any local Trino available
    if is_trino_available(host, port):
        yield host, port
        return

    print(f"Could not connect to Trino at {host}:{port}, starting etc/compose.yaml...")
    compose_files = ["compose.yaml"]
    if trino_version() < 466:
        compose_files.append("compose.pre-466.yaml")
    with DockerCompose(COMPOSE_DIR, compose_file_name=compose_files, wait=True):
        yield TRINO_HOST, DEFAULT_PORT


def trino_version() -> int:
    if TRINO_VERSION == "latest":
        return sys.maxsize
    return int(TRINO_VERSION)
