# syntax=docker/dockerfile:1.7

FROM mcr.microsoft.com/playwright/python:v1.49.1-noble AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_HOME=/app \
    QA_SANDBOX_ARTIFACT_ROOT=/app/outputs/qa_sandbox

WORKDIR ${APP_HOME}

RUN groupadd --system sandbox && useradd --system --gid sandbox --home-dir ${APP_HOME} sandbox \
    && apt-get update \
    && apt-get install -y --no-install-recommends git curl chromium-driver \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements.txt

COPY core ./core
COPY agents ./agents
COPY repository ./repository
COPY tests ./tests

RUN mkdir -p ${QA_SANDBOX_ARTIFACT_ROOT} /app/logs \
    && chown -R sandbox:sandbox /app

USER sandbox

VOLUME ["/app/outputs/qa_sandbox"]

CMD ["python", "-m", "pytest", "-p", "no:cacheprovider", "tests/test_qa_sandbox.py"]

