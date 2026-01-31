import nox


nox.options.default_venv_backend = "uv"

PYTHON_VERSIONS = ["3.12", "3.13", "3.14"]


@nox.session(python=PYTHON_VERSIONS)
def tests(session: nox.Session) -> None:
    """Run the test suite."""
    session.install(".[all]", "pytest", "pytest-asyncio", "pytest-aiohttp")
    session.install(
        "aioresponses",
        "boto3",
        "httpretty<1.1",
        "mocket[speedups]",
        "mock",
        "pytz",
        "testcontainers",
    )
    session.run("pytest", "-sv", "tests/", *session.posargs)


@nox.session
def lint(session: nox.Session) -> None:
    """Run linting checks."""
    session.install("ruff")
    session.run("ruff", "check", ".")


@nox.session
def format(session: nox.Session) -> None:
    """Check code formatting."""
    session.install("ruff")
    session.run("ruff", "format", "--check", ".")
