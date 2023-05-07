import shutil
from pathlib import Path

from aiohttp import web

import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from server import get_file, save_file, metadata


TEST_FOLDER = 'test_archive'
TEST_CHUNK_SIZE = 3
TEST_DATABASE_URL = 'sqlite+aiosqlite:///:memory:'


def pytest_sessionstart(session) -> None:
    """Создает директорию для хранения файлов в сервисе на время тестирования"""

    Path(TEST_FOLDER).mkdir(parents=True, exist_ok=True)


def pytest_sessionfinish(session) -> None:
    """Удаляет директорию, созданную для хранения файлов в сервисе на время тестирования"""

    shutil.rmtree(TEST_FOLDER)


@pytest.fixture
def cli(loop, aiohttp_client):
    app = web.Application()
    app.add_routes([
        web.get('/files/{id}/', get_file),
        web.post('/files/', save_file)
    ])
    return loop.run_until_complete(aiohttp_client(app))


# https://smirnov-am.github.io/pytest-testing_database/
@pytest.fixture
async def db_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=True)
    yield engine


@pytest.fixture
async def setup_db(db_engine):
    async with db_engine.begin() as conn:
        await conn.run_sync(metadata.create_all)
