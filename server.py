import asyncio
import cgi
import logging
import os
import sys
import uuid

import configargparse
import sqlalchemy
from aiofile import async_open
from aiohttp import web
from aiohttp.web_request import Request
from aiologger.loggers.json import JsonLogger
from dotenv import load_dotenv
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine

logger = JsonLogger.with_default_handlers(
    level=logging.DEBUG,
)

load_dotenv()

metadata = sqlalchemy.MetaData()
engine = create_async_engine(os.environ["FILE_SERVICE_DATABASE_URL"], echo=True)
files = sqlalchemy.Table(
    "file",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.String(38), primary_key=True),
    sqlalchemy.Column("name", sqlalchemy.String(255)),
)


app = web.Application()


def get_args() -> configargparse.Namespace:
    """Получаем аргументы из командной строки"""

    parser = configargparse.ArgParser()

    parser.add('--port', type=int, required=False, default=os.getenv('FILE_SERVICE_PORT'),
               help='Порт файлового сервера (default: %(default)s)')
    parser.add('--dir', type=str, required=False, default=os.getenv('FILE_SERVICE_DIR'),
               help='Папка для хранения файлов в сервисе')
    parser.add('--chunk', type=int, required=False, default=os.getenv('FILE_SERVICE_CHUNK'),
               help='размер порции файла для выгрузки из сервиса')

    return parser.parse_args()


async def save_file(request: Request) -> web.Response:
    """
    Хендлер сохранения байтового потока из http-запроса в файл

            Параметры:
                    request (aiohttp.web_request): объект http-запроса
            Возвращаемое значение:
                    response (aiohttp.Response): объект ответа
    """

    await logger.info(request.headers)

    _, params = cgi.parse_header(request.headers['CONTENT-DISPOSITION'])
    file_name = params['filename']
    file_id = str(uuid.uuid4())
    file_path = os.path.join(app['folder'], file_id)

    async with async_open(file_path, 'bw') as afp:
        # https://docs.aiohttp.org/en/stable/streams.html#asynchronous-iteration-support
        # Выполняет итерацию по блокам данных в порядке их ввода в поток
        async for data in request.content.iter_any():
            await afp.write(data)

    # вариант с чтением из потока всего файла целиком https://github.com/aio-libs/aiohttp-demos
    # content = await request.content.read()
    #
    # async with async_open(file_path, 'bw') as afp:
    #     await afp.write(content)

    await logger.debug(f'Файл принят {file_name} и записан на диск')

    async with engine.begin() as conn:
        response = await conn.execute(files.insert().values(id=file_id, name=file_name))
        await logger.debug(f'Файл сохранен под id={response.inserted_primary_key[0]}')

    return web.Response(status=201, reason='OK', text=response.inserted_primary_key[0])


async def get_file(request: Request) -> web.StreamResponse:
    """
    Хендлер формирования архива и скачивания его в файл

            Параметры:
                    request (aiohttp.web_request): объект http-запроса
            Возвращаемое значение:
                    response (aiohttp.StreamResponse): объект ответа в виде байтового потока
    """

    file_id = request.match_info['id']
    folder_path = os.path.join(os.getcwd(), app['folder'])

    if not (os.path.exists(folder_path) and os.path.isdir(folder_path)):
        await logger.warning(f'Запрошена несуществующая папка {folder_path}')
        raise web.HTTPNotFound(text='Архив не существует или был удален')

    async with engine.connect() as conn:
        statement = select(files.c.id, files.c.name).where(files.c.id == file_id)

        file_rows = await conn.execute(statement)
        file = file_rows.fetchone()

        if file is None:
            raise web.HTTPNotFound(text='Файла по указанному id не существует')
        file_path = os.path.join(app['folder'], file_id)

    response = web.StreamResponse(
        status=200,
        reason='OK',
        headers={
            'Content-Type': 'multipart/x-mixed-replace',
            'CONTENT-DISPOSITION': f'attachment;filename={file.name}'
        }
    )

    # Отправляет клиенту HTTP заголовки
    await response.prepare(request)

    try:
        async with async_open(file_path, 'rb') as f:
            chunk = await f.read(app['chunk_size'])

            while chunk:
                await response.write(chunk)
                chunk = await f.read(app['chunk_size'])

    except asyncio.CancelledError:
        await logger.error("Download was interrupted ")

        # отпускаем перехваченный CancelledError
        raise

    return response


async def init_db():
    """
    Cоздает таблицу для хранения информации о файлах

            Параметры:

            Возвращаемое значение:
                    None
    """

    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)


if __name__ == "__main__":

    args = get_args()

    if not os.path.isdir(args.dir):
        logger.critical(f"папка {args.dir!r} для хранения файлов не существует")
        sys.exit(1)

    app['folder'] = args.dir
    app['chunk_size'] = args.chunk
    app.add_routes([
        web.get('/files/{id}/', get_file),
        web.post('/files/', save_file)
    ])
    try:
        asyncio.run(init_db())
        web.run_app(app, port=args.port)

    except KeyboardInterrupt:
        pass
    except ValueError as e:
        logger.error(str(e))
    finally:
        logger.info('Работа сервера остановлена')

    logger.shutdown()
