FROM python:3.12-slim

WORKDIR /app

ARG INSTALL_LOCAL_ASR=false
ARG INSTALL_CHINESE_ASR=false

RUN python -c "from pathlib import Path; p=Path('/etc/apt/sources.list.d/debian.sources'); p.write_text(p.read_text().replace('http://deb.debian.org', 'https://deb.debian.org'))" \
  && apt-get -o Acquire::Retries=3 update \
  && apt-get -o Acquire::Retries=3 install -y --no-install-recommends ffmpeg ca-certificates curl \
  && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

ENV UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    FLASK_HOST=0.0.0.0 \
    FLASK_PORT=5000 \
    FLASK_DEBUG=false \
    WEB_CONFIG_ENABLED=false

# Install locked third-party dependencies before copying the application.
COPY pyproject.toml uv.lock README.md LICENSE ./
RUN uv sync --locked --no-dev --no-install-project

COPY . .

# Local recognition runtimes remain opt-in at image build time.
RUN set --; \
    if [ "$INSTALL_LOCAL_ASR" = "true" ]; then set -- "$@" --extra local; fi; \
    if [ "$INSTALL_CHINESE_ASR" = "true" ]; then set -- "$@" --extra local-chinese; fi; \
    uv sync --locked --no-dev "$@"

EXPOSE 5000

CMD ["douyin-web"]
