import io
import logging
import os
import uuid

import pytest
from aiohttp import web
from aiologger.loggers.json import JsonLogger
from sqlalchemy.ext.asyncio import create_async_engine

import server
from server import get_file, save_file, metadata, app

TEST_FOLDER = 'archive'
TEST_CHUNK_SIZE = 3


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
    engine = create_async_engine(os.environ["FILE_SERVICE_DATABASE_URL"], echo=True)
    yield engine


@pytest.fixture
async def setup_db(db_engine):
    async with db_engine.begin() as conn:
        await conn.run_sync(metadata.create_all)


async def test_method_not_allowed(cli):

    resp = await cli.get('/files/')
    assert resp.status == 405


@pytest.mark.usefixtures("setup_db")
async def test_404(monkeypatch, cli, db_engine):

    monkeypatch.setitem(app, 'folder', TEST_FOLDER)
    monkeypatch.setitem(app, 'chunk_size', TEST_CHUNK_SIZE)

    monkeypatch.setattr(server, "engine", db_engine)

    resp = await cli.get(f'/files/{uuid.uuid4()}/')
    assert resp.status == 404


@pytest.mark.usefixtures("setup_db")
async def test_save_file_success(monkeypatch, cli, db_engine):

    monkeypatch.setitem(app, 'folder', TEST_FOLDER)
    monkeypatch.setitem(app, 'chunk_size', TEST_CHUNK_SIZE)

    monkeypatch.setattr(server, "engine", db_engine)

    data = io.BytesIO(b"some random data")

    headers = {
        # "Transfer-Encoding": "chunked",
        'CONTENT-DISPOSITION': 'attachment;filename=random.txt'
    }

    resp = await cli.post('/files/', data=data, headers=headers, chunked=TEST_CHUNK_SIZE)
    file_id = await resp.text()

    assert resp.status == 201
    assert uuid.UUID(file_id)
