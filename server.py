import asyncio
import cgi
import logging
import os
import sys
import uuid

import aiofiles

import configargparse

from aiohttp import web
from aiohttp.web_request import Request

import sqlalchemy
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
from sqlalchemy import select


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

    parser = configargparse.ArgParser(default_config_files=['.env'])

    parser.add('--host', type=str, required=False, default='localhost',
               help='Хост файлового сервера')
    parser.add('--port', type=int, required=False, default='8080',
               help='Порт файлового сервера')
    parser.add('--level', type=str, required=False, choices=['debug', 'info', 'warning'], default='debug',
               help='Уровень логирования сообщений в консоль')
    parser.add('--archive_dir', type=str, required=True,
               help='Папка для хранения файлов в сервисе')
    parser.add('--database_url', type=str, required=True,
               help='адрес базы данных сервиса')
    parser.add('--chunk', type=str, required=True,
               help='размер порции файла для выгрузки из сервиса')

    return parser.parse_args()


async def save_file(request: Request) -> web.Response:
    """Хендлер сохранения байтового потока из запроса в файл"""

    logger.info(request.headers)

    _, params = cgi.parse_header(request.headers['CONTENT-DISPOSITION'])
    file_name = params['filename']
    file_id = str(uuid.uuid4())
    file_path = os.path.join(app['archive_dir'], file_id)

    # https://github.com/aio-libs/aiohttp-demos
    content = await request.content.read()

    async with aiofiles.open(file_path, 'bw') as fh:
        await fh.write(content)
        await fh.flush()
    logger.debug(f'Файл принят {file_name} и записан на диск')

    async with engine.begin() as conn:
        response = await conn.execute(files.insert().values(id=file_id, name=file_name))
        logger.debug(f'Файл сохранен под id={response.inserted_primary_key[0]}')

    return web.Response(status=201, reason='OK', text=response.inserted_primary_key[0])


async def get_file(request: Request) -> web.StreamResponse:
    """Хендлер формирования архива и скачивания его в файл"""

    file_id = request.match_info['id']
    folder_path = os.path.join(os.getcwd(), app['archive_dir'])

    if not (os.path.exists(folder_path) and os.path.isdir(folder_path)):
        logger.warning(f'Запрошена несуществующая папка {folder_path}')
        raise web.HTTPNotFound(text='Архив не существует или был удален')

    async with engine.connect() as conn:
        file_rows = await conn.execute(select(files).where(files.id == file_id))  # FIXME
        if file_rows is None:
            raise web.HTTPNotFound(text='Файла по указанному id не существует')
        file_name = file_rows[0].name
        file_path = os.path.join(app['archive_dir'], file_rows[0].id)

    response = web.StreamResponse(
        status=200,
        reason='OK',
        headers={
            'Content-Type': 'multipart/x-mixed-replace',
            'CONTENT-DISPOSITION': f'attachment;filename={file_name}'
        }
    )

    # Отправляет клиенту HTTP заголовки
    await response.prepare(request)

    chunk_size = 65_536
    try:
        async with aiofiles.open(file_path, 'rb') as f:
            chunk = await f.read(chunk_size)

            while chunk:
                await response.write(chunk)
                chunk = await f.read(chunk_size)

    except asyncio.CancelledError:
        logger.error("Download was interrupted ")

        # отпускаем перехваченный CancelledError
        raise

    return response


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

    app['archive_dir'] = args.archive_dir
    app['database_url'] = args.database_url

    logger.setLevel(getattr(logging, args.level.upper()))
    app.add_routes([
        web.get('/files/{id}/', get_file),
        web.post('/files/', save_file)
    ])
    web.run_app(app)
