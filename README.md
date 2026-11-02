# GridCast

Day-ahead forecasting of Italian electricity load, built on a complete Cloud/DevOps platform: Kubernetes, GitOps with Argo CD, Terraform, Ansible and observability.

> Work in progress.

## Forecasting setup

- Every day D at 10:00 Italian time, the model forecasts hourly load for day D+1, from local midnight to local midnight.
- Load lags are limited to 48 h and 168 h. A 24 h lag would leak information: at 10:00 on day D, load data is published only up to about 07:00, so most of day D is still unknown.
- Baseline: the same hour one week earlier (168 h lag). The model is only useful if it beats it.

## Data

### Electricity: Energy-Charts

- Source: the public API of [Energy-Charts](https://energy-charts.info) by Fraunhofer ISE, endpoint `/public_power`, country `it`. No API key is required.
- License: CC BY 4.0. Attribution: data from Energy-Charts.info.
- History: from 1 January 2024 (Italian time). Updated every hour, re-reading the last 3 days to pick up revised values.
- Timestamps are stored in UTC (`timestamptz`). The API interprets `start` and `end` as local Italian days.
- Resolution: hourly until 31 December 2025, 15 minutes from 1 January 2026. Features aggregate load to hourly means, so both periods are handled the same way.
- Publication delay: the latest values are about 2–3 hours behind real time.
- Percentage series (`Renewable share of load`, `Renewable share of generation`) are not stored: they can be derived from the power series.
- Missing values are kept as `NULL` and never replaced with zero.

#### Series availability

| Series | Available | Notes |
| --- | --- | --- |
| `Load` (target) | whole period | complete |
| `Battery`, `Battery Consumption` | from late December 2024 | |
| `Other renewables` | late December 2024 – August 2025 | discontinued |
| `Waste` | until June 2026 | discontinued |
| `Fossil coal-derived gas` | until mid-October 2026 | discontinued |
| `Geothermal` | whole period | about one month missing in <MONTH YEAR> |

All other series cover the whole period. The number of published series therefore changes over time (18, 21, 20, 19, then 18). Storing one row per country, series and timestamp absorbs these changes without schema migrations.

### Weather: Open-Meteo

- Source: [Open-Meteo](https://open-meteo.com), no API key required. License: CC BY 4.0. Attribution: weather data by Open-Meteo.com.
- Variables: hourly `temperature_2m` and `shortwave_radiation` for six cities: Milano, Torino, Bologna, Roma, Napoli, Palermo.
- History comes from the archive API, published with a delay of a few days. Recent and upcoming days come from the forecast API (`past_days=3`, `forecast_days=2`).
- Archive values replace forecasts once available. Archive hours not yet published (nulls) never overwrite a forecast.
- National averages are weighted by approximate regional electricity demand:

| City | Weight |
| --- | --- |
| Milano | 0.30 |
| Roma | 0.20 |
| Torino | 0.15 |
| Bologna | 0.15 |
| Napoli | 0.12 |
| Palermo | 0.08 |

## Known limitations

- Training uses observed (archive) weather, while daily forecasts use forecast weather, which is less accurate. Offline metrics are therefore optimistic. Planned fix: Open-Meteo historical forecast API.
- City weights are a heuristic, not estimated from data.
