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

RUN apt-get update && apt-get install -y \
    curl \
    gcc \
    g++ \
    libglib2.0-0 \
    python3-dev \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --timeout 120 --retries 5 -r requirements.txt

# Copy only src/ and run download-files as appuser.
# This layer is cached unless src/ changes — models won't re-download on unrelated file edits.
RUN mkdir -p /app/.cache && chown -R appuser:appuser /app
USER appuser
COPY --chown=appuser:appuser src/ /app/src/
RUN python src/agent.py download-files

# Copy remaining files (start.sh, etc.) — won't invalidate the model cache layer above.
USER root
COPY . .
RUN chmod +x /app/start.sh && chown -R appuser:appuser /app
USER appuser

CMD ["/app/start.sh"]