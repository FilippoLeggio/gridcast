"""Database access: engine creation, idempotent upserts and ingest run tracking."""

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert

from gridcast.common.signals import Terminated
from gridcast.common.tables import energy_power, forecasts, ingest_runs, weather_hourly

# Postgres accepts at most 65535 bind parameters per statement:
# 5000 rows x 4 columns stays well below.
BATCH_SIZE = 5_000


def create_db_engine(url: str) -> sa.Engine:
    return sa.create_engine(url, pool_pre_ping=True)


def _upsert(
    conn: sa.Connection,
    table: sa.Table,
    rows: Sequence[dict],
    keys: list[str],
    values: list[str],
) -> int:
    """Insert new rows and update those whose values changed upstream. Returns rows written."""
    written = 0
    for i in range(0, len(rows), BATCH_SIZE):
        stmt = insert(table).values(rows[i : i + BATCH_SIZE])
        # Update only if at least one value changed: unchanged rows are not rewritten.
        changed = sa.or_(*(table.c[col].is_distinct_from(stmt.excluded[col]) for col in values))
        set_ = {col: stmt.excluded[col] for col in values}
        if "ingested_at" in table.c:
            set_["ingested_at"] = sa.func.now()
        stmt = stmt.on_conflict_do_update(
            index_elements=keys,
            set_=set_,
            where=changed,
        ).returning(table.c[keys[0]])
        # RETURNING lists only the rows actually inserted or updated.
        written += len(conn.execute(stmt).all())
    return written


def upsert_power(conn: sa.Connection, rows: Sequence[dict]) -> int:
    return _upsert(conn, energy_power, rows, keys=["country", "series", "ts"], values=["value_mw"])


def upsert_weather(conn: sa.Connection, rows: Sequence[dict]) -> int:
    return _upsert(
        conn,
        weather_hourly,
        rows,
        keys=["location", "ts"],
        values=["temperature_c", "shortwave_radiation_wm2"],
    )


def upsert_forecasts(conn: sa.Connection, rows: Sequence[dict]) -> int:
    return _upsert(
        conn,
        forecasts,
        rows,
        keys=["target_ts"],
        values=["forecast_mw", "baseline_mw", "model_name", "model_version", "issued_at"],
    )


@contextmanager
def track_run(engine: sa.Engine, source: str) -> Iterator[dict]:
    """Record an ingest execution in its own transaction, so failures are recorded too."""
    with engine.begin() as conn:
        run_id = conn.execute(
            insert(ingest_runs)
            .values(source=source, started_at=datetime.now(UTC), status="running")
            .returning(ingest_runs.c.id)
        ).scalar_one()

    run = {"rows": 0}
    try:
        yield run
    except Exception as exc:
        status = "interrupted" if isinstance(exc, (KeyboardInterrupt, Terminated)) else "failed"
        _finish_run(engine, run_id, status=status, rows=run["rows"], error=str(exc)[:2000])
        raise
    _finish_run(engine, run_id, status="success", rows=run["rows"], error=None)


def _finish_run(engine: sa.Engine, run_id: int, status: str, rows: int, error: str | None) -> None:
    with engine.begin() as conn:
        conn.execute(
            sa.update(ingest_runs)
            .where(ingest_runs.c.id == run_id)
            .values(finished_at=datetime.now(UTC), status=status, rows_upserted=rows, error=error)
        )
