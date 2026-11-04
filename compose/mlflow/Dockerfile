# MLflow tracking server with the drivers it needs for Postgres and S3.
FROM ghcr.io/mlflow/mlflow:v3.1.0
# Drivers for the PostgreSQL backend store and the S3 artifact store, pinned for reproducible builds.
RUN pip install --no-cache-dir psycopg2-binary==2.9.13 boto3==1.43.121
