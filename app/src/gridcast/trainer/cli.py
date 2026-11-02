"""Command line entry point for model training."""

from datetime import UTC, datetime
from typing import Annotated

import typer

from gridcast.common.config import Settings
from gridcast.common.db import create_db_engine
from gridcast.trainer.dataset import load_dataset
from gridcast.trainer.train import train_and_register

# Start of the ingested history.
DEFAULT_START = datetime(2024, 1, 1)
app = typer.Typer(help="GridCast model training.", no_args_is_help=True)

DateOption = Annotated[datetime, typer.Option(formats=["%Y-%m-%d"])]


@app.callback()
def main() -> None:
    """GridCast model training."""


@app.command()
def inspect(
    start: Annotated[datetime, typer.Option(formats=["%Y-%m-%d"], help="First day (UTC).")],
    end: Annotated[datetime, typer.Option(formats=["%Y-%m-%d"], help="Day after the last (UTC).")],
) -> None:
    """Print a summary of the dataset: period, size and missing values per column."""
    engine = create_db_engine(Settings().database_url)
    data = load_dataset(engine, start.replace(tzinfo=UTC), end.replace(tzinfo=UTC))

    typer.echo(f"{len(data)} hours, from {data.index.min()} to {data.index.max()}\n")
    typer.echo("Missing values per column:")
    typer.echo(data.isna().sum().to_string())
    typer.echo("\nValue ranges:")
    typer.echo(data.describe().T[["mean", "min", "max"]].round(1).to_string())


@app.command()
def train(
    start: Annotated[
        datetime, typer.Option(formats=["%Y-%m-%d"], help="First day of history (UTC).")
    ] = DEFAULT_START,
    folds: Annotated[int, typer.Option(help="Monthly walk-forward folds.")] = 6,
) -> None:
    """Validate with walk-forward, train on all history and register the model in MLflow."""
    engine = create_db_engine(Settings().database_url)
    data = load_dataset(engine, start.replace(tzinfo=UTC), datetime.now(UTC))
    result = train_and_register(data, engine.url.render_as_string(hide_password=True), folds)

    typer.echo(result["folds"].round(2).to_string(index=False))
    typer.echo(
        f"\nCV MAPE {result['cv_mape']:.2f}% vs baseline {result['baseline_mape']:.2f}%"
        f" | model version {result['version']} | promoted: {result['promoted']}"
    )
