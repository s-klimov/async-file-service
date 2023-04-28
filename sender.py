import asyncio
import logging.config
import os
from typing import Generator
from urllib.parse import urljoin

import aiohttp
import configargparse as configargparse
from aiofile import async_open
from aiologger.loggers.json import JsonLogger
from dotenv import load_dotenv


CHUNK_SIZE = 2 ** 16  # Размер порции файла для считывания в ОЗУ, в байтах


def get_args() -> configargparse.Namespace:
    """Получаем аргументы из командной строки"""

    load_dotenv()

    parser = configargparse.ArgParser()

    parser.add('--protocol', type=str, required=False, choices=['http', 'https'], default='http',
               help='Протокол файлового сервера (default: %(default)s)')
    parser.add('--host', type=str, required=False, default=os.getenv('FILE_SERVICE_HOST'),
               help='Хост файлового сервера (default: %(default)s)')
    parser.add('--port', type=int, required=False, default=os.getenv('FILE_SERVICE_PORT'),
               help='Порт файлового сервера (default: %(default)s)')
    parser.add('--url', type=str, required=False, default='files/',
               help='Урл для доступа к методу сохранения файла (default: %(default)s)')
    parser.add('--chunk_size', type=int, required=False, default=os.getenv('FILE_SERVICE_CHUNK'),
               help='Размер порции файла для считывания в ОЗУ, в байтах (default: %(default)s)')
    parser.add('--path', type=str, required=True,
               help='Файл для сохранения в файловом сервисе')

    return parser.parse_args()


async def file_sender(file_name: str, chunk_size: int) -> Generator[bytes, None, None]:
    """
    Генератор считывания файла по частям

            Параметры:
                    file_name (str): имя файла, включая путь
                    chunk_size (int): размер порции для считывания файла в память
            Возвращаемое значение:
                    chunk (bytes): часть байтового потока файла
    """

    async with async_open(file_name, 'rb') as f:
        chunk = await f.read(chunk_size)

        while chunk:
            yield chunk
            chunk = await f.read(chunk_size)


async def main() -> None:
    """Функция генерации post-запроса в адрес файлового сервиса"""

    logger = JsonLogger.with_default_handlers(
        level=logging.DEBUG,
    )

    args = get_args()

    url = urljoin(f'{args.protocol}://{args.host}:{args.port}', args.url)
    headers = {
        'CONTENT-DISPOSITION': f'attachment;filename={os.path.basename(args.path)}',
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(
                url,
                headers=headers,
                data=file_sender(file_name=args.path, chunk_size=args.chunk_size)
        ) as resp:
            await logger.info(await resp.text())

    await logger.shutdown()


if __name__ == '__main__':

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
