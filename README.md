[![Build Status](https://github.com/gledi-ai/aiotrino/workflows/ci/badge.svg)](https://github.com/gledi-ai/aiotrino/actions?query=workflow%3Aci+event%3Apush+branch%3Apy3-async)
[![Trino Slack](https://img.shields.io/static/v1?logo=slack&logoColor=959DA5&label=Slack&labelColor=333a41&message=join%20conversation&color=3AC358)](https://trino.io/slack.html)
[![Trino: The Definitive Guide book download](https://img.shields.io/badge/Trino%3A%20The%20Definitive%20Guide-download-brightgreen)](https://www.starburst.io/info/oreilly-trino-guide/)

> A fork of [aiotrino](https://github.com/mvanderlee/aiotrino) to work around some problems I was facing my environment.
> This is not an official fork and is not affiliated with the original author in any way and is supposed to be temporary until the original package fixes the issues I was facing.


# Introduction

This package provides a asyncio client interface to query [Trino](https://trino.io/)
a distributed SQL engine. It supports Python 3.12, 3.13, 3.14.

# Installation

```
$ pip install aiotrino-patched
```

# Quick Start

Use the DBAPI interface to query Trino:

```python
import aiotrino

conn = aiotrino.dbapi.connect(
    host='localhost',
    port=8080,
    user='the-user',
    catalog='the-catalog',
    schema='the-schema',
)
cur = await conn.cursor()
await cur.execute('SELECT * FROM system.runtime.nodes')
rows = await cur.fetchall()
await conn.close()
```
Or with context manager
```python
import aiotrino

async with aiotrino.dbapi.connect(
    host='localhost',
    port=8080,
    user='the-user',
    catalog='the-catalog',
    schema='the-schema',
) as conn:
    cur = await conn.cursor()
    await cur.execute('SELECT * FROM system.runtime.nodes')
    rows = await cur.fetchall()
```

This will query the `system.runtime.nodes` system tables that shows the nodes
in the Trino cluster.

The DBAPI implementation in `aiotrino.dbapi` provides methods to retrieve fewer
rows for example `Cursorfetchone()` or `Cursor.fetchmany()`. By default
`Cursor.fetchmany()` fetches one row. Please set
`trino.dbapi.Cursor.arraysize` accordingly.

For backwards compatibility with PrestoSQL, override the headers at the start of your application
```python
import aiotrino
aiotrino.constants.HEADERS = aiotrino.constants.PrestoHeaders
```

# Basic Authentication
The `BasicAuthentication` class can be used to connect to a LDAP-configured Trino
cluster:
```python
import aiotrino
conn = aiotrino.dbapi.connect(
    host='coordinator url',
    port=8443,
    user='the-user',
    catalog='the-catalog',
    schema='the-schema',
    http_scheme='https',
    auth=aiotrino.auth.BasicAuthentication("principal id", "password"),
)
cur = await conn.cursor()
await cur.execute('SELECT * FROM system.runtime.nodes')
rows = await cur.fetchall()
await conn.close()
```

# JWT Token Authentication
The `JWTAuthentication` class can be used to connect to a configured Trino cluster:
```python
import aiotrino
conn = aiotrino.dbapi.connect(
    host='coordinator url',
    port=8443,
    catalog='the-catalog',
    schema='the-schema',
    http_scheme='https',
    auth=aiotrino.auth.JWTAuthentication(token="jwt-token"),
)
cur = await conn.cursor()
await cur.execute('SELECT * FROM system.runtime.nodes')
rows = await cur.fetchall()
await conn.close()
```

# Transactions
The client runs by default in *autocommit* mode. To enable transactions, set
*isolation_level* to a value different than `IsolationLevel.AUTOCOMMIT`:

```python
import aiotrino
from aiotrino import transaction
async with aiotrino.dbapi.connect(
    host='localhost',
    port=8080,
    user='the-user',
    catalog='the-catalog',
    schema='the-schema',
    isolation_level=transaction.IsolationLevel.REPEATABLE_READ,
) as conn:
  cur = await conn.cursor()
  await cur.execute('INSERT INTO sometable VALUES (1, 2, 3)')
  await cur.fetchone()
  await cur.execute('INSERT INTO sometable VALUES (4, 5, 6)')
  await cur.fetchone()
```

The transaction is created when the first SQL statement is executed.
`trino.dbapi.Connection.commit()` will be automatically called when the code
exits the *with* context and the queries succeed, otherwise
`trino.dbapi.Connection.rollback()' will be called.

# Development

This project uses [uv](https://docs.astral.sh/uv/) for environment and
dependency management. Install it once, then everything else flows from
`uv sync` / `uv run`.

## Getting Started With Development

Fork the repository, clone your fork, and `cd` into it.

1. Install `uv` (see [the install docs](https://docs.astral.sh/uv/getting-started/installation/)).
2. Create the dev environment:

    ```shell
    uv sync --extra all   # installs runtime deps, the SQLAlchemy extra, and the dev group
    ```

    `uv` reads `.python-version` and `pyproject.toml`, downloads the right Python
    if needed, and creates `.venv/` automatically. The project is installed in
    editable mode, so source edits take effect without a reinstall.

3. Run anything inside the environment with `uv run`:

    ```shell
    uv run python -c "import aiotrino; print(aiotrino.__version__)"
    uv run ruff check aiotrino
    ```

You can also activate the venv directly (`. .venv/bin/activate`) if you prefer.

When the code is ready, submit a Pull Request.

## Code Style

- For Python code, adhere to PEP 8 (enforced by `ruff`).
- Prefer code that is readable over one that is "clever".
- When writing a Git commit message, follow these [guidelines](https://chris.beams.io/posts/git-commit/).

Lint and format:

```shell
uv run ruff check aiotrino
uv run ruff format aiotrino        # write changes
uv run ruff format --check aiotrino  # CI-style check
```

## Running Tests

`aiotrino` uses [pytest](https://pytest.org/). Unit tests are fully mocked and
run without Docker:

```shell
uv run --frozen pytest tests/unit
uv run --frozen pytest tests/unit/test_client.py::test_name  # single test
```

Pass any pytest option through, e.g. `--pdb`.

To run the test suite across every supported Python version (3.12 / 3.13 / 3.14),
use [`nox`](https://nox.thea.codes/). `noxfile.py` also imports `nox-uv`, and
the venv backend is set to `uv`, so the matrix is provisioned via uv. `nox`
itself lives **outside** the project venv — invoke it with `uvx` (ephemeral,
recommended) or install it globally:

```shell
# ephemeral via uvx (no install needed)
uvx --with nox-uv nox                            # all sessions
uvx --with nox-uv nox --session=test --python 3.13
uvx --with nox-uv nox --session=lint
uvx --with nox-uv nox --session=format

# or install once and call `nox` directly
uv tool install --with nox-uv nox
nox
```

### Integration tests

Integration tests spin up a real Trino server (and a Garage container as
the S3-compatible store for the spooling protocol) via
[`testcontainers`](https://testcontainers-python.readthedocs.io/) — Docker
must be running locally.

```shell
uv run --frozen pytest tests/integration
TRINO_VERSION=466 uv run --frozen pytest tests/integration   # pin Trino version
```

Containers used:
- `trinodb/trino:${TRINO_VERSION:-latest}` — Trino coordinator on port 8080
- `dxflrs/garage:v2.3.0` — S3-compatible storage on port 3900 (only for
  Trino ≥ 466, where the spooling protocol is enabled)

If you already have a Trino instance running, the integration suite will
reuse it instead of starting one:

```shell
TRINO_RUNNING_HOST=localhost TRINO_RUNNING_PORT=8080 uv run --frozen pytest tests/integration
```

You can also bring the test stack up by hand (useful for poking at it with `trino-cli` or `psql`-style clients):

```shell
uv run python tests/development_server.py
```

## Versioning

The package version is derived from git tags by [hatch-vcs](https://github.com/ofek/hatch-vcs).
There is no `version` field in `pyproject.toml` and no hand-maintained
`_version.py` — both are produced at build/install time from the most recent
`vX.Y.Z` tag.

- On a tagged commit: version is exactly `X.Y.Z` (e.g. tag `v0.3.2` → `0.3.2`).
- Between tags: a development version like `0.3.3.dev4+g<shorthash>` is generated
  (next-minor `.devN+g<commit>`), with a `.dYYYYMMDD` suffix appended when the
  working tree is dirty.
- The generated file `aiotrino/_version.py` is git-ignored and regenerated by
  `uv sync` / `uv build`. Don't commit it.

CI must check out the full history so tags are visible (`fetch-depth: 0` on
`actions/checkout`); this repo's workflow already does so.

## Releasing

- [Set up your development environment](#Getting-Started-With-Development).
- Make sure `main` is clean and contains everything you want to ship.
- Create an annotated tag matching the version you want to publish, then push it.
  The tag IS the version — there is no separate bump step:
  ```bash
  git tag -a vX.Y.Z -m "Release X.Y.Z"
  git push origin vX.Y.Z
  ```
- Build and publish (assuming you have `uv` installed and the environment
  variable `UV_PUBLISH_TOKEN` has been set to your PyPI token):
  ```bash
  rm -rf dist
  uv build       # derives version from the tag you just pushed
  uv publish
  ```
  Verify the produced filenames in `dist/` contain `X.Y.Z` (and no `.devN` /
  `.dYYYYMMDD` suffix) before publishing — those suffixes mean the tag wasn't
  picked up or the tree was dirty.
- If you want to release to TestPyPI first (requires `UV_TEST_PUBLISH_TOKEN`
  set to your TestPyPI token):
  ```bash
  rm -rf dist
  uv build
  uv publish --publish-url https://test.pypi.org/legacy/ --token $UV_TEST_PUBLISH_TOKEN
  ```
- Send release announcement.

# Need Help?

Feel free to create an issue as it make your request visible to other users and contributors.

If an interactive discussion would be better or if you just want to hangout and chat about
the Trino Python client, you can join us on the *#python-client* channel on
[Trino Slack](https://trino.io/slack.html).
