import asyncio
import logging
import sys
import uuid

import aiofiles

import configargparse

from aiohttp import web
from aiohttp.web_request import Request

import sqlalchemy
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine

logging.basicConfig(
    level=logging.DEBUG,
    format="[%(asctime)s] %(levelname)s %(message)s",
    datefmt="%d/%b/%Y %H:%M:%S",
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

metadata = sqlalchemy.MetaData()
engine: AsyncEngine
files = sqlalchemy.Table(
    "file",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.String(38), primary_key=True),
    sqlalchemy.Column("name", sqlalchemy.String(255)),
)


def get_args() -> configargparse.Namespace:
    """Получаем аргументы из командной строки"""

    parser = configargparse.ArgParser()

    parser.add('--host', type=str, required=False, default='localhost',
               help='Хост файлового сервера')
    parser.add('--port', type=int, required=False, default='8080',
               help='Порт файлового сервера')
    parser.add('--level', type=str, required=False, choices=['debug', 'info', 'warning'], default='debug',
               help='Порт файлового сервера')

    return parser.parse_args()


async def save_file(request: Request) -> web.Response:
    """Хендлер сохранения байтового потока из запроса в файл"""

    logger.info(request.headers)

    # https://github.com/aio-libs/aiohttp-demos
    content = await request.content.read()

    async with aiofiles.open('step1.jpg', 'bw') as fh:
        await fh.write(content)
        await fh.flush()
    logger.debug('file accepted and write into disk')

    async with engine.begin() as conn:
        response = await conn.execute(files.insert().values(id=str(uuid.uuid4()), name='step1.jpg'))
        logger.debug(f'Файл сохранен под id={response.inserted_primary_key[0]}')

    return web.Response(status=201, reason='OK', text=response.inserted_primary_key[0])


async def main():

    # Запускаем базу данных
    global engine
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=True)
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)


if __name__ == "__main__":

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass

    args = get_args()
    app = web.Application()

    logger.setLevel(getattr(logging, args.level.upper()))
    app.add_routes([
        # web.get('/files/{file_uuid}/', get_file),
        web.post('/files/', save_file)
    ])
    web.run_app(app)
