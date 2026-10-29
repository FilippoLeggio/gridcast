from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GRIDCAST_", extra="ignore")

    # Required: there is no safe default for credentials.
    database_url: str
    energy_charts_url: str = "https://api.energy-charts.info"
    open_meteo_archive_url: str = "https://archive-api.open-meteo.com/v1"
    open_meteo_forecast_url: str = "https://api.open-meteo.com/v1"
    http_timeout_seconds: float = 30.0
