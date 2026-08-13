FROM python:3.11.15-slim-trixie@sha256:db3ff2e1800a8581e2c48a27c3995339d47bdf046da21c7627accd3d51053a93

ARG CROW_SOURCE_SHA=unknown

LABEL org.opencontainers.image.revision="${CROW_SOURCE_SHA}"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml MANIFEST.in ./
COPY src ./src
COPY modules ./modules

RUN python -m pip install --no-cache-dir ".[export]" \
    && crow-install-modules --root /app \
    && python -m pip freeze --all | LC_ALL=C sort > /app/crow-runtime-dependencies.txt \
    && printf '%s\n' "$CROW_SOURCE_SHA" > /app/crow-source-sha

ENV CROW_PLATFORM_BIND_ADDRESS=0.0.0.0 \
    CROW_PLATFORM_PORT=8080 \
    CROW_PLATFORM_DATA_ROOT=/srv/crow-data/platform \
    CROW_PLATFORM_CONFIG_ROOT=/srv/crow-config/platform

EXPOSE 8080

CMD ["crow-workbench"]
