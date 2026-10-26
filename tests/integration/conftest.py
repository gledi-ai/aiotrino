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
from collections.abc import Generator
from contextlib import ExitStack, closing, contextmanager
from pathlib import Path

import pytest
from testcontainers.core.container import DockerContainer
from testcontainers.core.network import Network
from testcontainers.core.wait_strategies import HealthcheckWaitStrategy, LogMessageWaitStrategy

import aiotrino.logging
from aiotrino.constants import DEFAULT_PORT


TRINO_HOST = "localhost"
TRINO_VERSION = os.environ.get("TRINO_VERSION") or "latest"
ETC = Path(__file__).parents[2] / "etc"

# Keep in sync with etc/trino/spooling-manager.properties.
GARAGE_IMAGE = "dxflrs/garage:v2.5.0"
GARAGE_ACCESS_KEY = "GKAIOTRINOTESTKEY"
GARAGE_SECRET_KEY = "aiotrinoaiotrinoaiotrinoaiotrinoaiotrinoaiotrinoaiotrinoaiotrino"
GARAGE_BUCKET = "spooling"


logger = aiotrino.logging.get_logger(__name__)


def is_trino_available(host, port):
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.settimeout(2)
        result = sock.connect_ex((host, port))
        if result == 0:
            return True
    return False


def running_trino() -> tuple[str, int]:
    return os.environ.get("TRINO_RUNNING_HOST", TRINO_HOST), int(os.environ.get("TRINO_RUNNING_PORT", DEFAULT_PORT))


@contextmanager
def trino_containers() -> Generator[int]:
    """Start Trino, plus Garage as the spooling store on Trino >= 466, and yield Trino's host port."""
    spooling = trino_version() >= 466
    suffix = "" if spooling else "-pre-466"
    trino = (
        DockerContainer(f"trinodb/trino:{TRINO_VERSION}")
        .with_env("TRINO_CONFIG_DIR", "/etc/trino")
        .with_exposed_ports(DEFAULT_PORT)
        .with_volume_mapping(str(ETC / "trino/catalog"), "/etc/trino/catalog")
        .with_volume_mapping(str(ETC / f"trino/jvm{suffix}.config"), "/etc/trino/jvm.config")
        .with_volume_mapping(str(ETC / f"trino/config{suffix}.properties"), "/etc/trino/config.properties")
        .waiting_for(HealthcheckWaitStrategy().with_startup_timeout(120))
    )
    with ExitStack() as stack:
        if spooling:
            network = stack.enter_context(Network())
            stack.enter_context(
                DockerContainer(GARAGE_IMAGE)
                .with_network(network)
                .with_network_aliases("garage")
                .with_env("GARAGE_DEFAULT_ACCESS_KEY", GARAGE_ACCESS_KEY)
                .with_env("GARAGE_DEFAULT_SECRET_KEY", GARAGE_SECRET_KEY)
                .with_env("GARAGE_DEFAULT_BUCKET", GARAGE_BUCKET)
                .with_command("/garage server --single-node --default-bucket")
                .with_volume_mapping(str(ETC / "garage/garage.toml"), "/etc/garage.toml", "ro")
                .waiting_for(LogMessageWaitStrategy("S3 API server listening on").with_startup_timeout(30))
            )
            trino.with_network(network).with_volume_mapping(
                str(ETC / "trino/spooling-manager.properties"), "/etc/trino/spooling-manager.properties"
            )
        stack.enter_context(trino)
        yield int(trino.get_exposed_port(DEFAULT_PORT))


@pytest.fixture(scope="session")
def run_trino():
    host, port = running_trino()
    if is_trino_available(host, port):
        yield host, port
        return

    with trino_containers() as port:
        yield TRINO_HOST, port


def trino_version() -> int:
    if TRINO_VERSION == "latest":
        return sys.maxsize
    return int(TRINO_VERSION)
