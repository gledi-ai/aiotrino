import os

from nox import Session, options  # pyright: ignore[reportMissingImports]
from nox_uv import session  # pyright: ignore[reportMissingImports]


options.default_venv_backend = "uv"


@session(python=["3.12", "3.13", "3.14"], uv_extras=["all"], uv_groups=["dev"])
def test(s: Session) -> None:
    py = s.python
    s.run(
        "python",
        "-m",
        "pytest",
        "--cov=aiotrino",
        "--cov-report=term-missing",
        f"--cov-report=xml:coverage-{py}.xml",
        f"--junitxml=junit-{py}.xml",
    )
    # Publish the coverage table to the GitHub Actions run summary when in CI.
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        s.run(
            "bash",
            "-c",
            f'{{ echo "## Coverage (Python {py})"; coverage report --format=markdown; }} >> "{summary}"',
        )


@session(uv_groups=["dev"])
def lint(s: Session) -> None:
    s.run("ruff", "check", "aiotrino")


@session(uv_groups=["dev"])
def format(s: Session) -> None:
    s.run("ruff", "format", "--check", "aiotrino")
