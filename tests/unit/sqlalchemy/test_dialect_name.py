import pytest
from alembic.ddl import impl as alembic_impl
from sqlalchemy import Integer, String, select
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.expression import ColumnClause

from aiotrino.sqlalchemy import dialect as dialect_module
from aiotrino.sqlalchemy.dialect import AIOTrinoDialect


@pytest.fixture
def dialect():
    return AIOTrinoDialect()


@pytest.fixture
def restore_alembic_impls():
    saved = dict(alembic_impl._impls)
    yield
    alembic_impl._impls.clear()
    alembic_impl._impls.update(saved)


def test_dialect_is_named_trino_with_aiotrino_driver(dialect):
    assert (dialect.name, dialect.driver) == ("trino", "aiotrino")


def test_compiles_can_target_the_dialect_by_name(dialect):
    class Marker(ColumnClause):
        inherit_cache = True

    @compiles(Marker)
    def _default(element, compiler, **kw):
        return "generic"

    @compiles(Marker, "trino")
    def _trino(element, compiler, **kw):
        return "trino"

    assert str(select(Marker("x")).compile(dialect=dialect)) == "SELECT trino"


def test_type_variants_can_target_the_dialect_by_name(dialect):
    type_ = String().with_variant(Integer(), "trino")

    assert isinstance(type_.dialect_impl(dialect), Integer)


def test_alembic_resolves_an_impl_for_the_dialect(dialect):
    assert issubclass(alembic_impl.DefaultImpl.get_by_dialect(dialect), alembic_impl.DefaultImpl)


@pytest.mark.usefixtures("restore_alembic_impls")
def test_alembic_impl_registered_by_the_user_is_kept(dialect):
    class UserTrinoImpl(alembic_impl.DefaultImpl):
        __dialect__ = "trino"

    dialect_module._register_alembic_impl()

    assert alembic_impl.DefaultImpl.get_by_dialect(dialect) is UserTrinoImpl
