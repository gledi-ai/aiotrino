import os
import time
from contextlib import contextmanager
from pathlib import Path

from testcontainers.core.container import DockerContainer
from testcontainers.core.network import Network
from testcontainers.core.wait_strategies import LogMessageWaitStrategy

from aiotrino.constants import DEFAULT_PORT


# Garage S3 credentials used by the spooling-manager.properties file under etc/.
# Keep these in sync with etc/spooling-manager.properties.
GARAGE_ACCESS_KEY = "GKAIOTRINOTESTKEY"
GARAGE_SECRET_KEY = "aiotrinoaiotrinoaiotrinoaiotrinoaiotrinoaiotrinoaiotrinoaiotrino"
GARAGE_BUCKET = "spooling"
GARAGE_IMAGE = "dxflrs/garage:v2.3.0"
GARAGE_S3_PORT = 3900

TRINO_VERSION = os.environ.get("TRINO_VERSION") or "latest"
TRINO_HOST = "localhost"


@contextmanager
def start_development_server(port=None, trino_version=TRINO_VERSION):
    network = None
    garage = None
    trino = None

    try:
        network = Network().create()
        supports_spooling_protocol = TRINO_VERSION == "latest" or int(TRINO_VERSION) >= 466
        if supports_spooling_protocol:
            root = Path(__file__).parent.parent
            garage = (
                DockerContainer(GARAGE_IMAGE)
                .with_name("garage")
                .with_kwargs(hostname="garage")
                .with_network(network)
                .with_bind_ports(GARAGE_S3_PORT, GARAGE_S3_PORT)
                .with_env("GARAGE_DEFAULT_ACCESS_KEY", GARAGE_ACCESS_KEY)
                .with_env("GARAGE_DEFAULT_SECRET_KEY", GARAGE_SECRET_KEY)
                .with_env("GARAGE_DEFAULT_BUCKET", GARAGE_BUCKET)
                .with_command("/garage server --single-node --default-bucket")
                .with_volume_mapping(str(root / "etc/garage/garage.toml"), "/etc/garage.toml", "ro")
                # "S3 API server listening on" is the last startup-phase log line
                # before Garage starts accepting requests.
                .waiting_for(LogMessageWaitStrategy("S3 API server listening on").with_startup_timeout(30))
            )

            print("Starting Garage container...")
            garage.start()

        trino = (
            DockerContainer(f"trinodb/trino:{trino_version}")
            .with_name("trino")
            .with_network(network)
            .with_env("TRINO_CONFIG_DIR", "/etc/trino")
            .with_bind_ports(DEFAULT_PORT, port)
            .waiting_for(LogMessageWaitStrategy("SERVER STARTED").with_startup_timeout(60))
        )

        root = Path(__file__).parent.parent

        trino = trino.with_volume_mapping(str(root / "etc/trino/catalog"), "/etc/trino/catalog")

        # Enable spooling config
        if supports_spooling_protocol:
            trino.with_volume_mapping(
                str(root / "etc/trino/spooling-manager.properties"), "/etc/trino/spooling-manager.properties", "rw"
            ).with_volume_mapping(str(root / "etc/trino/jvm.config"), "/etc/trino/jvm.config").with_volume_mapping(
                str(root / "etc/trino/config.properties"), "/etc/trino/config.properties"
            )
        else:
            trino.with_volume_mapping(
                str(root / "etc/trino/jvm-pre-466.config"), "/etc/trino/jvm.config"
            ).with_volume_mapping(str(root / "etc/trino/config-pre-466.properties"), "/etc/trino/config.properties")

        print("Starting Trino container...")
        trino.start()

        # Otherwise some tests fail with No nodes available
        time.sleep(2)

        yield garage, trino, network
    finally:
        # Stop containers when exiting the context
        if trino:
            try:
                print("Stopping Trino container...")
                trino.stop()
            except Exception as e:
                print(f"Error stopping Trino container: {e}")

        if garage:
            try:
                print("Stopping Garage container...")
                garage.stop()
            except Exception as e:
                print(f"Error stopping Garage container: {e}")

        if network:
            try:
                print("Removing network...")
                network.remove()
            except Exception as e:
                print(f"Error removing network: {e}")


def main():
    """Run Trino setup independently from pytest."""
    with start_development_server(port=DEFAULT_PORT):
        print(f"Trino started at {TRINO_HOST}:{DEFAULT_PORT}")

        # Keep the process running so that the containers stay up
        input("Press Enter to stop containers...")


if __name__ == "__main__":
    main()
