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
import copy

import pytest
from sqlalchemy import Column, Integer, LargeBinary, MetaData, String, Table, cast, func, insert, literal, select
from sqlalchemy.exc import CompileError
from sqlalchemy.schema import CreateTable
from sqlalchemy.sql import column, table
from sqlalchemy.sql.sqltypes import VARBINARY as GenericVARBINARY

from aiotrino.sqlalchemy.datatype import JSON, MAP, ROW, VARBINARY
from aiotrino.sqlalchemy.dialect import AIOTrinoDialect
from tests.unit.conftest import sqlalchemy_version


metadata = MetaData()
table_without_catalog = Table(
    "table",
    metadata,
    Column("id", Integer),
    Column("name", String),
)
table_with_catalog = Table("table", metadata, Column("id", Integer), schema="default", aiotrino_catalog="other")


@pytest.fixture
def dialect():
    return AIOTrinoDialect()


@pytest.mark.skipif(
    sqlalchemy_version() < "1.4", reason="columns argument to select() must be a Python list or other iterable"
)
def test_limit_offset(dialect):
    statement = select(table_without_catalog).limit(10).offset(0)
    query = statement.compile(dialect=dialect)
    assert str(query) == 'SELECT "table".id, "table".name \nFROM "table"\nOFFSET :param_1\nLIMIT :param_2'


@pytest.mark.skipif(
    sqlalchemy_version() < "1.4", reason="columns argument to select() must be a Python list or other iterable"
)
def test_limit(dialect):
    statement = select(table_without_catalog).limit(10)
    query = statement.compile(dialect=dialect)
    assert str(query) == 'SELECT "table".id, "table".name \nFROM "table"\nLIMIT :param_1'


@pytest.mark.skipif(
    sqlalchemy_version() < "1.4", reason="columns argument to select() must be a Python list or other iterable"
)
def test_offset(dialect):
    statement = select(table_without_catalog).offset(0)
    query = statement.compile(dialect=dialect)
    assert str(query) == 'SELECT "table".id, "table".name \nFROM "table"\nOFFSET :param_1'


@pytest.mark.skipif(
    sqlalchemy_version() < "1.4", reason="columns argument to select() must be a Python list or other iterable"
)
def test_cte_insert_order(dialect):
    cte = select(table_without_catalog).cte("cte")
    statement = insert(table_without_catalog).from_select(table_without_catalog.columns, cte)
    query = statement.compile(dialect=dialect)
    assert (
        str(query) == 'INSERT INTO "table" (id, name) WITH cte AS \n'
        '(SELECT "table".id AS id, "table".name AS name \n'
        'FROM "table")\n'
        " SELECT cte.id, cte.name \n"
        "FROM cte"
    )


@pytest.mark.skipif(
    sqlalchemy_version() < "1.4", reason="columns argument to select() must be a Python list or other iterable"
)
def test_catalogs_argument(dialect):
    statement = select(table_with_catalog)
    query = statement.compile(dialect=dialect)
    assert str(query) == 'SELECT default."table".id \nFROM "other".default."table"'


def test_catalogs_create_table(dialect):
    statement = CreateTable(table_with_catalog)
    query = statement.compile(dialect=dialect)
    assert str(query) == '\nCREATE TABLE "other".default."table" (\n\tid INTEGER\n)\n\n'


@pytest.mark.skipif(
    sqlalchemy_version() < "1.4", reason="columns argument to select() must be a Python list or other iterable"
)
def test_table_clause(dialect):
    statement = select(table("user", column("id"), column("name"), column("description")))
    query = statement.compile(dialect=dialect)
    assert str(query) == "SELECT user.id, user.name, user.description \nFROM user"


@pytest.mark.skipif(
    sqlalchemy_version() < "1.4", reason="columns argument to select() must be a Python list or other iterable"
)
@pytest.mark.parametrize(
    "function,element",
    [
        ("first_value", func.first_value),
        ("last_value", func.last_value),
        ("nth_value", func.nth_value),
        ("lead", func.lead),
        ("lag", func.lag),
    ],
)
def test_ignore_nulls(dialect, function, element):
    statement = select(
        element(
            table_without_catalog.c.id,
            ignore_nulls=True,
        )
        .over(partition_by=table_without_catalog.c.name)
        .label("window")
    )
    query = statement.compile(dialect=dialect)
    assert (
        str(query) == f'SELECT {function}("table".id) IGNORE NULLS OVER (PARTITION BY "table".name) AS window '
        f'\nFROM "table"'
    )

    statement = select(
        element(
            table_without_catalog.c.id,
            ignore_nulls=False,
        )
        .over(partition_by=table_without_catalog.c.name)
        .label("window")
    )
    query = statement.compile(dialect=dialect)
    assert str(query) == f'SELECT {function}("table".id) OVER (PARTITION BY "table".name) AS window \nFROM "table"'


@pytest.mark.skipif(sqlalchemy_version() < "2.0", reason="ImportError: cannot import name 'try_cast' from 'sqlalchemy'")
def test_try_cast(dialect):
    from sqlalchemy import try_cast

    statement = select(try_cast(table_without_catalog.c.id, String))
    query = statement.compile(dialect=dialect)
    assert str(query) == 'SELECT try_cast("table".id as VARCHAR) AS id \nFROM "table"'


@pytest.mark.parametrize(
    "value,expected",
    [
        (b"", "X''"),
        (b"hello", "X'68656c6c6f'"),
        (b"\xca\xfe\xba\xbe", "X'cafebabe'"),
        (b"\xff\xfe\x00\x01", "X'fffe0001'"),
        (bytearray(b"abc"), "X'616263'"),
        (memoryview(b"abc"), "X'616263'"),
    ],
)
@pytest.mark.parametrize("type_", [VARBINARY(), GenericVARBINARY(), LargeBinary()])
def test_varbinary_literal_binds(dialect, value, expected, type_):
    expression = literal(value, type_=type_)
    query = expression.compile(dialect=dialect, compile_kwargs={"literal_binds": True})
    assert str(query) == expected


def test_varbinary_literal_binds_rejects_non_bytes(dialect):
    expression = literal("not-bytes", type_=VARBINARY())
    with pytest.raises(CompileError):
        expression.compile(dialect=dialect, compile_kwargs={"literal_binds": True})


@pytest.mark.filterwarnings("error")
@pytest.mark.parametrize("type_", [MAP(String, Integer), ROW([("a", Integer)])])
def test_composite_types_support_comparison(dialect, type_):
    left = column("l", type_)
    right = column("r", type_)

    assert str(left.is_(None).compile(dialect=dialect)) == "l IS NULL"
    assert str((left == right).compile(dialect=dialect)) == "l = r"
    assert str(left.in_([right]).compile(dialect=dialect)) == "l IN (r)"


def test_varbinary_create_table(dialect):
    table_with_binary = Table("table_with_binary", MetaData(), Column("data", LargeBinary))
    query = CreateTable(table_with_binary).compile(dialect=dialect)
    assert "data VARBINARY" in str(query)


def _compile_cached(statement, dialect, cache):
    result = statement._compile_w_cache(dialect, compiled_cache=cache, column_keys=[])
    return str(result[0]), result[-1]


@pytest.mark.filterwarnings("error")
def test_statement_cache_is_used(dialect):
    cache = {}
    statement = select(table_without_catalog).where(table_without_catalog.c.id == 1)

    _, first = _compile_cached(statement, dialect, cache)
    _, second = _compile_cached(select(table_without_catalog).where(table_without_catalog.c.id == 2), dialect, cache)

    assert (first, second) == (dialect.CACHE_MISS, dialect.CACHE_HIT)


@pytest.mark.filterwarnings("error")
@pytest.mark.parametrize("element", [func.first_value, func.last_value, func.nth_value, func.lead, func.lag])
def test_ignore_nulls_is_part_of_the_cache_key(dialect, element):
    cache = {}
    respect_nulls = select(element(table_without_catalog.c.id).over())
    ignore_nulls = select(element(table_without_catalog.c.id, ignore_nulls=True).over())

    respect_sql, _ = _compile_cached(respect_nulls, dialect, cache)
    ignore_sql, _ = _compile_cached(ignore_nulls, dialect, cache)

    assert "IGNORE NULLS" not in respect_sql
    assert "IGNORE NULLS" in ignore_sql


@pytest.mark.filterwarnings("error")
def test_catalog_is_part_of_the_cache_key(dialect):
    cache = {}
    iceberg = Table("orders", MetaData(), Column("id", Integer), schema="sales", aiotrino_catalog="iceberg")
    hive = Table("orders", MetaData(), Column("id", Integer), schema="sales", aiotrino_catalog="hive")

    iceberg_sql, _ = _compile_cached(select(iceberg), dialect, cache)
    hive_sql, _ = _compile_cached(select(hive), dialect, cache)

    assert 'FROM "iceberg".sales.orders' in iceberg_sql
    assert 'FROM "hive".sales.orders' in hive_sql


@pytest.mark.filterwarnings("error")
@pytest.mark.parametrize(
    "type_",
    [
        ROW([("a", Integer), ("b", ROW([("c", String)]))]),
        MAP(String, ROW([("a", Integer)])),
        JSON(),
    ],
)
def test_equal_types_hit_the_statement_cache(dialect, type_):
    cache = {}
    _compile_cached(select(cast(column("x"), type_)), dialect, cache)
    _, stats = _compile_cached(select(cast(column("x"), copy.deepcopy(type_))), dialect, cache)

    assert stats == dialect.CACHE_HIT


@pytest.mark.filterwarnings("error")
@pytest.mark.parametrize(
    "first,second",
    [
        (ROW([("a", Integer)]), ROW([("a", String)])),
        (ROW([("a", Integer)]), ROW([("b", Integer)])),
        (ROW([("a", ROW([("b", Integer)]))]), ROW([("a", ROW([("b", String)]))])),
        (MAP(String, ROW([("a", Integer)])), MAP(String, ROW([("a", String)]))),
    ],
)
def test_types_are_part_of_the_cache_key(dialect, first, second):
    cache = {}
    first_sql, _ = _compile_cached(select(cast(column("x"), first)), dialect, cache)
    second_sql, _ = _compile_cached(select(cast(column("x"), second)), dialect, cache)

    assert first_sql != second_sql
