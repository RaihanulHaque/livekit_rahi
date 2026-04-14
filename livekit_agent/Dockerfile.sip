# syntax=docker/dockerfile:1

ARG PYTHON_VERSION=3.12
FROM python:${PYTHON_VERSION}-slim-bookworm

ENV PYTHONUNBUFFERED=1 HOME=/app

ARG UID=10001
RUN adduser \
    --disabled-password \
    --gecos "" \
    --home "/app" \
    --shell "/sbin/nologin" \
    --uid "${UID}" \
    appuser

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --timeout 120 --retries 5 -r requirements.txt

RUN mkdir -p /app/.cache && chown -R appuser:appuser /app
USER appuser

COPY --chown=appuser:appuser src/sip_api.py /app/src/
COPY --chown=appuser:appuser src/sip_manager.py /app/src/
COPY --chown=appuser:appuser src/sip_api_server.py /app/src/
COPY --chown=appuser:appuser src/webhook_api.py /app/src/

WORKDIR /app/src

EXPOSE 8089

CMD ["python", "sip_api_server.py"]
