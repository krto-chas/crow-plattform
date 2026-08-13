FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml MANIFEST.in ./
COPY src ./src
COPY modules ./modules

RUN python -m pip install --no-cache-dir ".[export]" \
    && crow-install-modules --root /app

ENV CROW_PLATFORM_BIND_ADDRESS=0.0.0.0 \
    CROW_PLATFORM_PORT=8080 \
    CROW_PLATFORM_DATA_ROOT=/srv/crow-data/platform \
    CROW_PLATFORM_CONFIG_ROOT=/srv/crow-config/platform

EXPOSE 8080

CMD ["crow-workbench"]
