from nox import Session, options  # pyright: ignore[reportMissingImports]
from nox_uv import session  # pyright: ignore[reportMissingImports]


options.default_venv_backend = "uv"


@session(
    python=["3.12", "3.13", "3.14"],
    uv_extras=["all"],
    uv_groups=["dev"],
)
def test(s: Session) -> None:
    s.run("python", "-m", "pytest")


@session(uv_groups=["dev"])
def lint(s: Session) -> None:
    s.run("ruff", "check", "aiotrino")


@session(uv_groups=["dev"])
def format(s: Session) -> None:
    s.run("ruff", "format", "--check", "aiotrino")
