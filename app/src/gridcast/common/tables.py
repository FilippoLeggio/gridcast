"""Table definitions mirroring the Alembic migrations, used for queries and upserts."""

import sqlalchemy as sa

metadata = sa.MetaData()

energy_power = sa.Table(
    "energy_power",
    metadata,
    sa.Column("country", sa.Text, primary_key=True),
    sa.Column("series", sa.Text, primary_key=True),
    sa.Column("ts", sa.DateTime(timezone=True), primary_key=True),
    sa.Column("value_mw", sa.Double, nullable=True),
    sa.Column("ingested_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
)

weather_hourly = sa.Table(
    "weather_hourly",
    metadata,
    sa.Column("location", sa.Text, primary_key=True),
    sa.Column("ts", sa.DateTime(timezone=True), primary_key=True),
    sa.Column("temperature_c", sa.Double, nullable=True),
    sa.Column("shortwave_radiation_wm2", sa.Double, nullable=True),
    sa.Column("ingested_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
)

ingest_runs = sa.Table(
    "ingest_runs",
    metadata,
    sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
    sa.Column("source", sa.Text, nullable=False),
    sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("rows_upserted", sa.Integer, nullable=True),
    sa.Column("status", sa.Text, nullable=False),
    sa.Column("error", sa.Text, nullable=True),
)
