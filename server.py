import asyncio
import cgi
import logging.config
import os
import sys
import uuid

import configargparse
import sqlalchemy
from aiofile import async_open
from aiohttp import web
from aiohttp.web_request import Request
from dotenv import load_dotenv
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine

logging.config.fileConfig('logging.ini', disable_existing_loggers=False)
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

    load_dotenv()

    parser = configargparse.ArgParser()

    parser.add('--host', type=str, required=False, default=os.getenv('FILE_SERVICE_HOST'),
               help='Хост файлового сервера (default: %(default)s)')
    parser.add('--port', type=int, required=False, default=os.getenv('FILE_SERVICE_PORT'),
               help='Порт файлового сервера (default: %(default)s)')
    parser.add('--dir', type=str, required=False, default=os.getenv('FILE_SERVICE_DIR'),
               help='Папка для хранения файлов в сервисе')
    parser.add('--database_url', type=str, required=False, default=os.getenv('FILE_SERVICE_DATABASE_URL'),
               help='адрес базы данных сервиса')
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

    logger.info(request.headers)

    _, params = cgi.parse_header(request.headers['CONTENT-DISPOSITION'])
    file_name = params['filename']
    file_id = str(uuid.uuid4())
    file_path = os.path.join(app['folder'], file_id)

    # https://github.com/aio-libs/aiohttp-demos
    content = await request.content.read()

    async with async_open(file_path, 'bw') as afp:
        await afp.write(content)
    logger.debug(f'Файл принят {file_name} и записан на диск')

    async with engine.begin() as conn:
        response = await conn.execute(files.insert().values(id=file_id, name=file_name))
        logger.debug(f'Файл сохранен под id={response.inserted_primary_key[0]}')

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
        logger.warning(f'Запрошена несуществующая папка {folder_path}')
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
        logger.error("Download was interrupted ")

        # отпускаем перехваченный CancelledError
        raise

    return response


async def get_db_engine(database_url: str):
    """
    Подключает движок базы данных и создает таблицу для хранения информации о файлах

            Параметры:
                    database_url (str): адрес базы данных
            Возвращаемое значение:
                    None
    """

    global engine
    engine = create_async_engine(database_url, echo=True)
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)


if __name__ == "__main__":

    args = get_args()

    if not os.path.isdir(args.dir):
        logger.critical(f"папка {args.dir!r} для хранения файлов не существует")
        sys.exit(1)

    app = web.Application()
    app['folder'] = args.dir
    app['chunk_size'] = args.chunk
    app.add_routes([
        web.get('/files/{id}/', get_file),
        web.post('/files/', save_file)
    ])

    try:
        asyncio.run(get_db_engine(args.database_url))
        web.run_app(app, host=args.host, port=args.port)

    except KeyboardInterrupt:
        pass
    except ValueError as e:
        logger.error(str(e))
    finally:
        logger.info('Работа сервера остановлена')
