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
"""

This module defines exceptions for Trino operations. It follows the structure
defined in pep-0249.
"""

from typing import Any

import aiotrino.logging


logger = aiotrino.logging.get_logger(__name__)


# PEP 249 Errors
class Error(Exception):
    pass


class Warning(Exception):
    pass


class InterfaceError(Error):
    pass


class DatabaseError(Error):
    pass


class InternalError(DatabaseError):
    pass


class OperationalError(DatabaseError):
    pass


class ProgrammingError(DatabaseError):
    pass


class IntegrityError(DatabaseError):
    pass


class DataError(DatabaseError):
    pass


class NotSupportedError(DatabaseError):
    pass


# dbapi module errors (extending PEP 249 errors)
class TrinoAuthError(OperationalError):
    pass


class TrinoConnectionError(OperationalError):
    pass


class TrinoDataError(NotSupportedError):
    pass


class TrinoQueryError(Error):
    def __init__(self, error: dict[str, Any], query_id: str | None = None) -> None:
        self._error = error
        self._query_id = query_id

    @property
    def error_code(self) -> int | None:
        return self._error.get("errorCode", None)

    @property
    def error_name(self) -> str | None:
        return self._error.get("errorName", None)

    @property
    def error_type(self) -> str | None:
        return self._error.get("errorType", None)

    @property
    def error_exception(self) -> str | None:
        return self.failure_info.get("type", None) if self.failure_info else None

    @property
    def failure_info(self) -> dict[str, Any] | None:
        return self._error.get("failureInfo", None)

    @property
    def message(self) -> str:
        return self._error.get("message", "Trino did not return an error message")

    @property
    def error_location(self) -> tuple[int, int] | None:
        location = self._error.get("errorLocation", None)
        if location is None:
            return None
        line_number = location.get("lineNumber", None)
        column_number = location.get("columnNumber", None)
        if line_number is None or column_number is None:
            return None
        return (line_number, column_number)

    @property
    def query_id(self) -> str | None:
        return self._query_id

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}(type={self.error_type}, name={self.error_name}, "
            f'message="{self.message}", query_id={self.query_id})'
        )

    def __str__(self) -> str:
        return repr(self)


class TrinoExternalError(TrinoQueryError, OperationalError):
    pass


class TrinoInternalError(TrinoQueryError, InternalError):
    pass


class TrinoUserError(TrinoQueryError, ProgrammingError):
    pass


# client module errors
class HttpError(Exception):
    pass


class Http502Error(HttpError):
    pass


class Http503Error(HttpError):
    pass


class Http504Error(HttpError):
    pass
