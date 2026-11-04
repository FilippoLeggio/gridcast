# MLflow tracking server, built on the same up-to-date base image as the GridCast images.
FROM python:3.12-slim

# Fixed numeric non-root user, like the GridCast images.
RUN groupadd --system --gid 10001 mlflow \
    && useradd --system --uid 10001 --gid mlflow --no-create-home mlflow

# Server, PostgreSQL driver for the backend store, S3 client for the artifact store.
RUN pip install --no-cache-dir mlflow==3.18.0 "psycopg[binary]==3.3.8" boto3==1.43.121

# MLflow writes small caches under HOME: the user has no home, so use /tmp.
ENV HOME=/tmp
USER 10001:10001
EXPOSE 5000
