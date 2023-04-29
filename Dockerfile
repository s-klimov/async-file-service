# Версия Docker образа Python.
ARG PYTHON=3.10.9

# Загружаем образ, в котором будем собирать необходимое нам окружение.
FROM python:${PYTHON} AS poetry-base

# Определяем необходимые переменные окружения,
# python пакеты будем ставить в папку /app/.local с использованием флага --user
ENV PYTHONUSERBASE="/app/.local" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Устанавливаем необходимые библиотеки для сборки python пакетов и поддержки клиента БД Oracle.
RUN apt-get update && \
    apt-get install --yes --no-install-recommends python3-dev libpq-dev libaio1 zip unzip && \
    rm -rf /var/lib/apt/lists/*

# Устанавливаем временную рабочую директорию.
WORKDIR /tmp

# https://python-poetry.org/docs#ci-recommendations
ENV POETRY_VERSION=1.3.2
ENV POETRY_HOME=/opt/poetry
ENV POETRY_VENV=/opt/poetry-venv

# Tell Poetry where to place its cache and virtual environment
ENV POETRY_CACHE_DIR=/opt/.cache

# Creating a virtual environment just for poetry and install it with pip
RUN python3 -m venv $POETRY_VENV \
    && $POETRY_VENV/bin/pip install -U pip setuptools==58.2.0 \
    && $POETRY_VENV/bin/pip install poetry==${POETRY_VERSION}

# Загружаем образ, в котором будем собирать наш сервис.
FROM poetry-base

# Copy Poetry to app image
COPY --from=poetry-base ${POETRY_VENV} ${POETRY_VENV}

# Add Poetry to PATH
ENV PATH="${PATH}:/opt/poetry-venv/bin"

# Устанавливаем рабочую директорию.
WORKDIR /app

# Copy Dependencies
COPY poetry.lock pyproject.toml ./

# [OPTIONAL] Validate the project is properly configured
RUN poetry check

# [OPTIONAL] disable Poetry to manage my virtual environments
RUN poetry config virtualenvs.create false

# Install Dependencies
RUN poetry install --no-interaction

# Copy Application
COPY . /app
