# region builder
FROM python:3.11-slim as Dockerfile
WORKDIR /app

# hadolint ignore=DL3008
RUN set -eux ; \
    export DEBIAN_FRONTEND=noninteractive && \
    apt-get update && \
    apt-get install -y --no-install-suggests --no-install-recommends \
    build-essential gcc libgdal-dev curl && \
    rm -rf /var/lib/apt/lists/*

# region builder-2
FROM python:3.11-slim as builder-2
WORKDIR /app

# hadolint ignore=DL3008
RUN set -eux ; \
    export DEBIAN_FRONTEND=noninteractive && \
    apt-get update && \
    apt-get install -y --no-install-suggests --no-install-recommends libgdal32 libmagic1 && \
    rm -rf /var/lib/apt/lists/*

COPY ./ /app/
# endregion


# region apple
FROM builder-2 as development
USER 0

RUN pip install uv

COPY pyproject.toml /app/
RUN uv pip install --system --no-cache '.[dev]'

COPY . /app/

ENTRYPOINT ["python", "-m", "debugpy", "--wait-for-client", "--listen", "0.0.0.0:4567", "-m", "uvicorn", "main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"]
# endregion

# region production
FROM builder-2 as production
USER 0

RUN pip install uv && uv sync

COPY pyproject.toml /app/
# Installer seulement les dépendances de production
RUN uv pip install --system --no-cache '.'

# Copier le reste de l'application APRES l'installation des dépendances
COPY . /app/

ENV ENVIRONMENT_MODE=production
ENTRYPOINT ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--workers", "10"]
# endregion
