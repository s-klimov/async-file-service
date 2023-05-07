import hashlib
import io
import os
import uuid

import pytest
from aiofile import async_open

import server
from server import app
from tests.conftest import TEST_FOLDER, TEST_CHUNK_SIZE


@pytest.mark.usefixtures("setup_db")
async def test_save_file_success(monkeypatch, cli, db_engine):
    """Проверяем сохранение файла. Контрольные суммы сохраняемого файла и сохраненного файла должны совпасть."""

    monkeypatch.setitem(app, 'folder', TEST_FOLDER)
    monkeypatch.setitem(app, 'chunk_size', TEST_CHUNK_SIZE)

    monkeypatch.setattr(server, "engine", db_engine)

    data = io.BytesIO(b"some random data")
    md5_hash = hashlib.md5(data.read()).hexdigest()

    headers = {
        # "Transfer-Encoding": "chunked",
        'CONTENT-DISPOSITION': 'attachment;filename=random.txt'
    }

    data.seek(0)
    resp = await cli.post('/files/', data=data.read(), headers=headers, chunked=TEST_CHUNK_SIZE)
    file_id = await resp.text()

    assert resp.status == 201
    assert uuid.UUID(file_id)

    async with async_open(os.path.join(TEST_FOLDER, file_id), 'rb') as afp:
        new_md5_hash = hashlib.md5(await afp.read()).hexdigest()
    assert md5_hash == new_md5_hash


@pytest.mark.usefixtures("setup_db")
async def test_save_and_get_file_success(monkeypatch, cli, db_engine):
    """Проверяем сохранение и получение одного и того же файла. Контрольные суммы сохраняемого файла и
    полученного файла должны совпасть"""

    monkeypatch.setitem(app, 'folder', TEST_FOLDER)
    monkeypatch.setitem(app, 'chunk_size', TEST_CHUNK_SIZE)

    monkeypatch.setattr(server, "engine", db_engine)

    data = io.BytesIO(b"some random data")
    md5_hash = hashlib.md5(data.read()).hexdigest()

    headers = {
        # "Transfer-Encoding": "chunked",
        'CONTENT-DISPOSITION': 'attachment;filename=random.txt'
    }

    data.seek(0)
    resp = await cli.post('/files/', data=data.read(), headers=headers, chunked=TEST_CHUNK_SIZE)
    file_id = await resp.text()

    assert resp.status == 201
    assert uuid.UUID(file_id)

    resp = await cli.get(f'/files/{file_id}/')
    content = await resp.text()
    new_md5_hash = hashlib.md5(str.encode(content)).hexdigest()
    assert md5_hash == new_md5_hash


async def test_method_not_allowed(cli):
    """Проверяем проект на ожидаемое отсутствие метода get по урлу для сохранения файла"""

    resp = await cli.get('/files/')
    assert resp.status == 405


@pytest.mark.usefixtures("setup_db")
async def test_404(monkeypatch, cli, db_engine):
    """Проверяем проект на ожидаемое отсутствие файла при попытке запросить его по случайному id."""

    monkeypatch.setitem(app, 'folder', TEST_FOLDER)
    monkeypatch.setitem(app, 'chunk_size', TEST_CHUNK_SIZE)

    monkeypatch.setattr(server, "engine", db_engine)

    resp = await cli.get(f'/files/{uuid.uuid4()}/')
    assert resp.status == 404
