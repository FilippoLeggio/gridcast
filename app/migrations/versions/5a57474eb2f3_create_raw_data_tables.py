from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Revision identifiers, used by Alembic to order migrations.
revision: str = "5a57474eb2f3"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Raw power series from Energy-Charts, native 15-minute resolution, UTC timestamps.
    op.create_table(
        "energy_power",
        sa.Column("country", sa.Text, nullable=False),
        sa.Column("series", sa.Text, nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("value_mw", sa.Double, nullable=True),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("country", "series", "ts"),
    )

    # Hourly weather per location from Open-Meteo, UTC timestamps.
    op.create_table(
        "weather_hourly",
        sa.Column("location", sa.Text, nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("temperature_c", sa.Double, nullable=True),
        sa.Column("shortwave_radiation_wm2", sa.Double, nullable=True),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("location", "ts"),
    )

    # One row per ingest execution: the source for data freshness metrics.
    op.create_table(
        "ingest_runs",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("source", sa.Text, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rows_upserted", sa.Integer, nullable=True),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("error", sa.Text, nullable=True),
    )
    op.create_index("ix_ingest_runs_source_started", "ingest_runs", ["source", "started_at"])


def downgrade() -> None:
    op.drop_index("ix_ingest_runs_source_started", table_name="ingest_runs")
    op.drop_table("ingest_runs")
    op.drop_table("weather_hourly")
    op.drop_table("energy_power")
