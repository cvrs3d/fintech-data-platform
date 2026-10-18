FROM ghcr.io/astral-sh/uv:0.12.23 AS uv

FROM apache/airflow:3.3.2-python3.13

USER root

COPY --from=uv /uv /usr/local/bin/uv

RUN mkdir -p /opt/fintech /opt/airflow/config \
    && chown airflow:root /opt/fintech /opt/airflow/config

USER airflow

WORKDIR /opt/fintech

ENV UV_PROJECT_ENVIRONMENT=/opt/fintech/.venv \
    UV_PYTHON_DOWNLOADS=never \
    UV_LINK_MODE=copy

COPY --chown=airflow:root pyproject.toml uv.lock .python-version ./

RUN uv sync \
    --locked \
    --no-dev \
    --no-install-project \
    --python /usr/local/bin/python

COPY --chown=airflow:root ingestion/ ./ingestion/
COPY --chown=airflow:root dbt/ ./dbt/

WORKDIR /opt/airflow
