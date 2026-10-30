"""Database access: engine creation, idempotent upserts and ingest run tracking."""

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert

from gridcast.common.tables import energy_power, ingest_runs

# Postgres accepts at most 65535 bind parameters per statement:
# 5000 rows x 4 columns stays well below.
BATCH_SIZE = 5_000


def create_db_engine(url: str) -> sa.Engine:
    return sa.create_engine(url, pool_pre_ping=True)


def upsert_power(conn: sa.Connection, rows: Sequence[dict]) -> int:
    """Insert new points and update values revised upstream. Returns rows actually written."""
    written = 0
    for i in range(0, len(rows), BATCH_SIZE):
        stmt = insert(energy_power).values(rows[i : i + BATCH_SIZE])
        stmt = stmt.on_conflict_do_update(
            index_elements=["country", "series", "ts"],
            set_={"value_mw": stmt.excluded.value_mw, "ingested_at": sa.func.now()},
            # Skip rows whose value did not change: unchanged data is not rewritten.
            where=energy_power.c.value_mw.is_distinct_from(stmt.excluded.value_mw),
        ).returning(energy_power.c.ts)
        # RETURNING lists only the rows actually inserted or updated.
        written += conn.execute(stmt).rowcount
    return written


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
        _finish_run(engine, run_id, status="failed", rows=run["rows"], error=str(exc)[:2000])
        raise
    _finish_run(engine, run_id, status="success", rows=run["rows"], error=None)


def _finish_run(engine: sa.Engine, run_id: int, status: str, rows: int, error: str | None) -> None:
    with engine.begin() as conn:
        conn.execute(
            sa.update(ingest_runs)
            .where(ingest_runs.c.id == run_id)
            .values(finished_at=datetime.now(UTC), status=status, rows_upserted=rows, error=error)
        )
