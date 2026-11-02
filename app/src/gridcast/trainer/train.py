"""Walk-forward validation, final training and model registration with MLflow."""

import os
import subprocess
import tempfile
from pathlib import Path

import lightgbm as lgb
import mlflow
import numpy as np
import pandas as pd
from mlflow.exceptions import MlflowException
from mlflow.tracking import MlflowClient

from gridcast.common.features import FEATURE_COLUMNS

EXPERIMENT = "gridcast-load"
MODEL_NAME = "gridcast-load"
CHAMPION_ALIAS = "champion"
TARGET = "load_mw"
# Naive baseline: the same hour one week earlier.
BASELINE = "load_lag_168h"

PARAMS = {
    "n_estimators": 600,
    "learning_rate": 0.05,
    "num_leaves": 63,
    "min_child_samples": 20,
    "subsample": 0.8,
    "subsample_freq": 1,
    "colsample_bytree": 0.8,
    "random_state": 42,
    "verbose": -1,
}


def mape(actual: pd.Series, predicted: np.ndarray | pd.Series) -> float:
    """Mean absolute percentage error, in percent."""
    return float(np.mean(np.abs(actual - predicted) / actual) * 100)


def mae(actual: pd.Series, predicted: np.ndarray | pd.Series) -> float:
    """Mean absolute error, in MW."""
    return float(np.mean(np.abs(actual - predicted)))


def fold_starts(index: pd.DatetimeIndex, n_folds: int) -> list[pd.Timestamp]:
    """Starts of the last n_folds complete months before the month of the latest hour."""
    current_month = index.max().normalize().replace(day=1)
    return [current_month - pd.DateOffset(months=k) for k in range(n_folds, 0, -1)]


def walk_forward(data: pd.DataFrame, n_folds: int) -> pd.DataFrame:
    """Train on all hours before each test month, then predict that month. One row per fold."""
    rows = []
    for test_start in fold_starts(data.index, n_folds):
        test_end = test_start + pd.DateOffset(months=1)
        train = data[data.index < test_start]
        test = data[(data.index >= test_start) & (data.index < test_end)]

        model = lgb.LGBMRegressor(**PARAMS).fit(train[FEATURE_COLUMNS], train[TARGET])
        predicted = model.predict(test[FEATURE_COLUMNS])
        has_baseline = test[BASELINE].notna()

        rows.append(
            {
                "test_month": test_start.strftime("%Y-%m"),
                "model_mape": mape(test[TARGET], predicted),
                "baseline_mape": mape(
                    test.loc[has_baseline, TARGET], test.loc[has_baseline, BASELINE]
                ),
                "model_mae_mw": mae(test[TARGET], predicted),
                "baseline_mae_mw": mae(
                    test.loc[has_baseline, TARGET], test.loc[has_baseline, BASELINE]
                ),
            }
        )
    return pd.DataFrame(rows)


def _promote_if_better(version: str, cv_mape: float, baseline_mape: float) -> bool:
    """Give the champion alias to this version if it beats the baseline and the current champion."""
    if cv_mape >= baseline_mape:
        return False
    client = MlflowClient()
    try:
        champion = client.get_model_version_by_alias(MODEL_NAME, CHAMPION_ALIAS)
        champion_mape = client.get_run(champion.run_id).data.metrics["cv_mape"]
    except MlflowException:
        champion_mape = float(
            "inf"
        )  # no champion yet: the first model that beats the baseline wins
    if cv_mape > champion_mape:
        return False
    client.set_registered_model_alias(MODEL_NAME, CHAMPION_ALIAS, version)
    return True


def _git_commit() -> str:
    """Code version: from the environment in containers, from git when running locally."""
    if commit := os.environ.get("GRIDCAST_GIT_COMMIT"):
        return commit
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _log_training_data(data: pd.DataFrame) -> None:
    """Record exactly which data the model saw: a fingerprint and a full snapshot."""
    dataset = mlflow.data.from_pandas(
        data[[*FEATURE_COLUMNS, TARGET]], name="gridcast-hourly", targets=TARGET
    )
    mlflow.log_input(dataset, context="training")
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "training_data.parquet"
        data.to_parquet(path)
        mlflow.log_artifact(str(path), artifact_path="data")


def train_and_register(data: pd.DataFrame, data_source: str, n_folds: int = 6) -> dict:
    """Validate, train on all known hours, register the model and promote it if it is better."""
    data = data.dropna(subset=[TARGET])
    mlflow.set_experiment(EXPERIMENT)

    with mlflow.start_run() as run:
        mlflow.set_tags({"git_commit": _git_commit(), "data_source": data_source})
        _log_training_data(data)
        folds = walk_forward(data, n_folds)
        for step, fold in enumerate(folds.itertuples()):
            mlflow.log_metrics(
                {"fold_model_mape": fold.model_mape, "fold_baseline_mape": fold.baseline_mape},
                step=step,
            )
        cv_mape = float(folds["model_mape"].mean())
        baseline_mape = float(folds["baseline_mape"].mean())

        mlflow.log_params(
            {
                **PARAMS,
                "n_folds": n_folds,
                "data_start": str(data.index.min()),
                "data_end": str(data.index.max()),
            }
        )
        mlflow.log_metrics({"cv_mape": cv_mape, "cv_baseline_mape": baseline_mape})
        mlflow.log_table(folds, artifact_file="folds.json")

        # The final model learns from every known hour, test months included.
        model = lgb.LGBMRegressor(**PARAMS).fit(data[FEATURE_COLUMNS], data[TARGET])
        info = mlflow.lightgbm.log_model(
            model,
            name="model",
            input_example=data[FEATURE_COLUMNS].dropna().head(5),
            registered_model_name=MODEL_NAME,
        )
        promoted = _promote_if_better(str(info.registered_model_version), cv_mape, baseline_mape)
        mlflow.set_tag("promoted", str(promoted))

    return {
        "run_id": run.info.run_id,
        "cv_mape": cv_mape,
        "baseline_mape": baseline_mape,
        "version": info.registered_model_version,
        "promoted": promoted,
        "folds": folds,
    }
