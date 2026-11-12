# Changelog

All notable changes to aiotrino-patched since it was forked from
[mvanderlee/aiotrino](https://github.com/mvanderlee/aiotrino).

## [0.8.0] - 2026-11-12

### Breaking Changes

- **sqlalchemy:** `dialect.name` is "trino" instead of "default".

### Features

- **sqlalchemy:** Enable SQL compilation caching
- **sqlalchemy:** Name the dialect "trino"

## [0.7.0] - 2026-10-26

### Breaking Changes

- Python 3.12 is no longer supported.

### Features

- Support Python 3.13-3.15, drop 3.12

## [0.6.0] - 2026-10-26

### Features

- **sqlalchemy:** Support SQLAlchemy 2.1 alongside 2.0

## [0.5.1] - 2026-10-01

No user-facing changes.

## [0.5.0] - 2026-10-01

### Features

- **client:** Catch up with trino-python-client 0.340.0

## [0.4.0] - 2026-09-14

### Features

- **client:** Catch up with trino-python-client 0.338.0
- **client:** Lazily load spooled result set segments ([#6](https://github.com/gledi-ai/aiotrino/pull/6))
- **client:** Catch up with trino-python-client 0.339.0
- **client:** Retry empty HTTP 200 statement responses

### Bug Fixes

- **client:** Surface empty 200 with JSON content type as TrinoConnectionError

## [0.3.5] - 2026-05-15

### Features

- **sqlalchemy:** Warn and drop unsupported PK/FK/UNIQUE constraints
- **client:** Tolerate missing lz4 / zstandard at runtime

### Bug Fixes

- **client:** Use default TLS port (443) when scheme is https
- **client:** Infer http_scheme from port when not given explicitly
- **client:** Send original user via X-Trino-Original-User on impersonation
- **sqlalchemy:** Forward kwargs through compile_ignore_nulls

### Performance

- **client:** Defer tzlocal import until needed

## [0.3.4] - 2026-05-15

### Features

- Add release action

## [0.3.3] - 2026-05-14

No user-facing changes.

## [0.3.2] - 2026-05-14

No user-facing changes.

## [0.3.1] - 2026-02-01

### Bug Fixes

- Fix/sqlalchemy upgrade soft close ([#2](https://github.com/gledi-ai/aiotrino/pull/2))
