import os

from nox import Session, options, parametrize  # pyright: ignore[reportMissingImports]
from nox_uv import session  # pyright: ignore[reportMissingImports]


options.default_venv_backend = "uv"

SQLALCHEMY_VERSIONS = {
    "2.0": "sqlalchemy[asyncio]>=2.0,<2.1",
    "2.1": "sqlalchemy[asyncio]>=2.1,<2.2",
}
FULL_SUITE_SQLALCHEMY = "2.1"
SQLALCHEMY_TESTS = ["tests/unit/sqlalchemy", "tests/integration/test_sqlalchemy_integration.py"]
# Branch coverage via sys.monitoring needs 3.14+; the ctrace fallback makes 3.13 runs ~3x slower.
COVERAGE_PYTHON = "3.14"


@session(python=["3.13", "3.14", "3.15"], uv_extras=["all"], uv_groups=["dev"])
@parametrize("sqlalchemy", list(SQLALCHEMY_VERSIONS))
def test(s: Session, sqlalchemy: str) -> None:
    s.install(SQLALCHEMY_VERSIONS[sqlalchemy])
    py = s.python
    suffix = f"{py}-sqlalchemy{sqlalchemy}"
    paths = [] if sqlalchemy == FULL_SUITE_SQLALCHEMY else SQLALCHEMY_TESTS
    coverage = py == COVERAGE_PYTHON and sqlalchemy == FULL_SUITE_SQLALCHEMY
    cov_args = (
        ["--cov=aiotrino", "--cov-report=term-missing", f"--cov-report=xml:coverage-{suffix}.xml"] if coverage else []
    )
    s.run("python", "-m", "pytest", *cov_args, f"--junitxml=junit-{suffix}.xml", *paths, *s.posargs)
    # Publish the coverage table to the GitHub Actions run summary when in CI.
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if coverage and summary:
        heading = f"## Coverage (Python {py}, SQLAlchemy {sqlalchemy})"
        s.run("bash", "-c", f'{{ echo "{heading}"; coverage report --format=markdown; }} >> "{summary}"')


@session(uv_groups=["dev"])
def lint(s: Session) -> None:
    s.run("ruff", "check", "aiotrino")


@session(uv_groups=["dev"])
def format(s: Session) -> None:
    s.run("ruff", "format", "--check", "aiotrino")
