import os
from contextlib import ExitStack
from pathlib import Path

from tests.integration.conftest import TRINO_HOST, is_trino_available, running_trino, trino_containers


UNIT_TESTS = Path(__file__).parent / "unit"


def pytest_configure(config):
    """Under xdist, start one Trino in the controller so the workers share it instead of each starting their own."""
    if hasattr(config, "workerinput") or not config.getoption("numprocesses", None):
        return
    if all(Path(arg.split("::")[0]).resolve().is_relative_to(UNIT_TESTS) for arg in config.args):
        return
    if is_trino_available(*running_trino()):
        return

    stack = ExitStack()
    config.add_cleanup(stack.close)
    port = stack.enter_context(trino_containers())
    os.environ["TRINO_RUNNING_HOST"] = TRINO_HOST
    os.environ["TRINO_RUNNING_PORT"] = str(port)
