# Асинхронный микросервис хранения файлов

Микросервис помогает работе основного сайта и обслуживает запросы на сохранение и получение файлов. 

## Как установить

Для работы микросервиса нужен Python версии не ниже 3.10.  
Для настройки локального окружения нужно установить Poetry.
Скопируйте файл `.env.dist` с перечнем требуемых переменных окружения в `.env` и заполните его. Пример заполнения:  
```bash
FILE_SERVICE_PORT=8080
FILE_SERVICE_DIR=archive
FILE_SERVICE_DATABASE_URL=sqlite+aiosqlite:///:memory:
FILE_SERVICE_CHUNK=65_536
```

```bash
poetry install
```

## Как запустить web-сервер

Получить справку о параметрах запуска web-сервера:      
```bash
python server.py -h
```

Запустить web-сервер:   
```bash
poetry run python server.py [-h] [--port PORT] [--dir DIR] [--database_url DATABASE_URL] [--chunk CHUNK]
```
Параметры:
* port - порт файлового сервера.  
* dir - путь до папки, где микросервис будет хранить файлы. Путь должен быть существующим.
* database_url - адрес базы данных.  
* chunk - размер "порции", которыми сервис возвращает файлы. 

Значение параметров может быть предустановлено через переменные окружения, описанные в файле `.env`.


## Использование микросервиса

В микросервисе реализованы два метода:
### 1. Сохранение файла в сервисе
```
POST http://localhost:8080/files/
```
Пример заголовка запроса:
```
    'Host': 'localhost:8080',
    'Content-Disposition': 'attachment;filename=2.jpg',
    'Accept': '*/*',
    'Accept-Encoding': 'gzip, deflate',
    'User-Agent': 'Python/3.10 aiohttp/3.8.4',
    'Content-Type': 'application/octet-stream',
    'Transfer-Encoding': 'chunked'
```
Тело запроса - байты файла, разбитые на порции ("чанки").
Полный скрипт формирования запроса находится в модуле `sender.py`.  
Метод возвращает id, под которым был сохранен файл.
### 2. Получение файла из сервиса
```
GET http://localhost:8080/files/<id файла>/
```
Метод возвращает байтовый поток, который клиент созраняет в файл.

## Консольный скрипт sender.py
Скрипт формирует post-запрос в адрес микросервиса для сохранения в нём файла.  
### Интерфейс командной строки
```bash
python sender.py [-h] [--protocol {http,https}] [--host HOST] [--port PORT] [--url URL] [--chunk_size CHUNK_SIZE] --path PATH
```
* protocol - Протокол файлового сервера
* host - Хост файлового сервера
* port - Порт файлового сервера
* url - Урл для доступа к методу сохранения файла
* chunk_size - Размер порции файла для считывания в ОЗУ, в байтах
* path - Пусть до файла сохраняемого в файловом сервисе

Получить справку о параметрах:  
```bash
python sender.py -h
```

# Цели проекта
Код написан в учебных целях.
