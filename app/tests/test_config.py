import pytest

from gridcast.common.config import Settings


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://u:p@db:5432/x",
        "postgres://u:p@db:5432/x",
        "postgresql+psycopg://u:p@db:5432/x",
    ],
)
def test_database_url_always_uses_psycopg(url: str) -> None:
    assert Settings(database_url=url).database_url == "postgresql+psycopg://u:p@db:5432/x"
