FROM python:3.13-slim

WORKDIR /app

# System deps:
# - ffmpeg: used by fallback audio extraction flow
# - ca-certificates/curl: common runtime/network utilities
RUN apt-get update \
  && apt-get install -y --no-install-recommends ffmpeg ca-certificates curl \
  && rm -rf /var/lib/apt/lists/*

# Install uv (fast, deterministic install via uv.lock)
RUN pip install --no-cache-dir uv

# Create venv in a fixed path so PATH can be set predictably
ENV UV_PROJECT_ENVIRONMENT=/app/.venv
ENV PATH="/app/.venv/bin:${PATH}"
ENV PYTHONUNBUFFERED=1

# Install dependencies first (better layer caching)
# `uv sync` builds the local project; include README.md because it's referenced by `pyproject.toml`.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev

# Copy app
COPY . .

EXPOSE 5000

# Default: run the API server (bind to all interfaces; debug off)
ENV FLASK_HOST=0.0.0.0
ENV FLASK_PORT=5000
ENV FLASK_DEBUG=False

CMD ["python", "web_app.py"]
