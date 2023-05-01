import pytest
from aiohttp import web

from server import get_file, save_file


TEST_FOLDER = 'archive'
TEST_CHUNK_SIZE = 1000


@pytest.fixture
def cli(loop, aiohttp_client):
    app = web.Application()
    app['folder'] = TEST_FOLDER
    app['chunk_size'] = TEST_CHUNK_SIZE
    app.add_routes([
        web.get('/files/{id}/', get_file),
        web.post('/files/', save_file)
    ])
    return loop.run_until_complete(aiohttp_client(app))


async def test_method_not_allowed(cli):

    resp = await cli.get('/files/')
    assert resp.status == 405
