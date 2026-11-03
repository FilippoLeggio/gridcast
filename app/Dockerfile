# syntax=docker/dockerfile:1

# ---------- shared stages ----------

# uv binary, pinned to the version used on the developer machine.
FROM ghcr.io/astral-sh/uv:0.13.6 AS uv

# Runtime base shared by every image: Python, a non-root user, the virtualenv on PATH.
FROM python:3.12-slim AS base
# Fixed numeric IDs: Kubernetes can verify runAsNonRoot only with a numeric user.
RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --no-create-home app
WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

# Build tools and dependency manifests, never shipped in the final images.
FROM base AS builder
COPY --from=uv /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0
COPY pyproject.toml uv.lock README.md ./

# ---------- one dependency set per component ----------
# Dependencies first, code second: editing the code does not reinstall dependencies.

FROM builder AS build-ingest
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev

FROM builder AS build-trainer
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project --extra trainer
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --extra trainer

FROM builder AS build-api
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project --extra api
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --extra api

# ---------- final images ----------

# Ingest also carries the migrations: a Kubernetes Job will run them with this image.
FROM base AS ingest
COPY --from=build-ingest --chown=10001:10001 /app /app
COPY --chown=10001:10001 migrations ./migrations
COPY --chown=10001:10001 alembic.ini ./
ARG GIT_COMMIT=unknown
ENV GRIDCAST_GIT_COMMIT=${GIT_COMMIT}
USER 10001:10001
ENTRYPOINT ["gridcast-ingest"]
CMD ["energy"]

FROM base AS trainer
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=build-trainer --chown=10001:10001 /app /app
ARG GIT_COMMIT=unknown
ENV GRIDCAST_GIT_COMMIT=${GIT_COMMIT}
USER 10001:10001
ENTRYPOINT ["gridcast-train"]
CMD ["train"]

FROM base AS api
COPY --from=build-api --chown=10001:10001 /app /app
ARG GIT_COMMIT=unknown
ENV GRIDCAST_GIT_COMMIT=${GIT_COMMIT}
USER 10001:10001
EXPOSE 8000
CMD ["uvicorn", "gridcast.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
