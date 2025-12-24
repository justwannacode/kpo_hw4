# КПО ДЗ №4 — Межсервисное асинхронное взаимодействие

Задание выполнено в рамках курса "Конструирование программного обеспечения".

В проекте реализованы микросервисы:
- **API Gateway** (routing)
- **Orders Service** (заказы + WebSocket-уведомления)
- **Payments Service** (счета + списание денег)
- **Frontend** (минимальный веб-интерфейс)

## Архитектура

Сервисы:

API Gateway (api-gateway, порт 8000)

Единая точка входа для клиента.
- проксирует запросы в orders-service и payments-service;
- используется заголовок X-User-Id для “авторизации”


Orders Service (orders-service, порт 8001)

Сервис заказов.

- хранит заказы и их статусы в PostgreSQL;

- при создании заказа пишет событие order_created в outbox;

- outbox-публикатор отправляет событие в RabbitMQ;

- консьюмер принимает события платежей и обновляет статус заказа;

- отправляет уведомления клиентам по WebSocket.

Payments Service (payments-service, порт 8002)

Сервис платежей.

- хранит аккаунты и балансы пользователей в PostgreSQL;

- консьюмер принимает order_created, пытается списать деньги транзакционно;

- обеспечивает идемпотентность оплаты (повторное событие не приводит к повторному списанию);

- результат фиксирует в БД и пишет событие в outbox, затем публикует в RabbitMQ.

Frontend (frontend, порт 8080)

Минимальный UI:

- создание аккаунта, пополнение, создание заказа;

- подключение к WebSocket и отображение уведомлений (toast) при смене статуса заказа.

RabbitMQ

- AMQP: 5672 (для микросервисов)

- Management UI: 15672 (в браузере)


## Хранилища

orders-service: PostgreSQL (таблицы orders, outbox, inbox)

payments-service: PostgreSQL (таблицы accounts, payments, outbox, inbox)

Миграции: Alembic (выполняются при старте контейнеров через entrypoint.sh)

## Сценарий использования

1. Клиент создаёт аккаунт:

2. Клиент пополняет баланс:

3. Клиент создаёт заказ:

4. Orders Service создаёт заказ со статусом NEW, пишет событие order_created в outbox.

5. Outbox-паблишер публикует событие в RabbitMQ.

6. Payments Service получает order_created:

- если денег хватает, списывает и формирует payment_succeeded

- если не хватает, формирует payment_failed

- пишет событие в outbox и публикует в RabbitMQ.

7. Orders Service получает результат платежа:

- обновляет статус заказа на FINISHED или CANCELLED

- отправляет уведомление по WebSocket.

## Быстрый старт

Запустите docker:
```
docker compose up --build
```

Откройте:
- Frontend: http://localhost:8080
- API Gateway Swagger: http://localhost:8000/docs
- Orders Swagger: http://localhost:8001/docs
- Payments Swagger: http://localhost:8002/docs
- RabbitMQ UI: http://localhost:15672 (логин/пароль: gozon/gozon)

Frontend:

1) Введите `user_id` (целое число)
2) Создайте счет
3) Пополните счет
4) Создайте заказ  
   После создания заказ **асинхронно** уходит на оплату. Статус обновится автоматически в интерфейсе, также придёт push-уведомление.

API:

Создать аккаунт пользователя:

```
curl -sS -X POST http://localhost:8000/accounts \
  -H "X-User-Id: <id>"
```

Пополнить баланс:

``` 
curl -sS -X POST http://localhost:8000/accounts/topup \
  -H "Content-Type: application/json" \
  -H "X-User-Id: <id>" \
  -d '{"amount": <amount>}'
```

Проверить баланс:

``` 
curl -sS http://localhost:8000/accounts/balance \
  -H "X-User-Id: <id>"
```

Создать заказ:

```
curl -sS -X POST http://localhost:8000/orders \
  -H "Content-Type: application/json" \
  -H "X-User-Id: <id>" \
  -d '{"amount": <amount>, "description": "<description>"}'
```

Посмотреть заказ:

``` 
curl -sS http://localhost:8000/orders/<ORDER_ID> \
  -H "X-User-Id: <id>"
```

## Postman

В каталоге `postman/` лежит коллекция:

`postman/gozon.postman_collection.json`

Импортируйте в Postman и запускайте запросы к `http://localhost:8000`.

## Структура проекта

```
├── docker-compose.yml         - контейнеры, сети, порты, env, зависимости
├── postman
│   └── gozon.postman_collection.json - готовые запросы для ручного тестирования API (accounts/orders)
├── README.md                  - инструкция запуска/проверки
└── services
    ├── api-gateway
    │   ├── Dockerfile         - сборка контейнера gateway
    │   ├── requirements.txt   - зависимости gateway
    │   └── src
    │       └── gateway
    │           ├── config.py  - настройки gateway
    │           ├── __init__.py
    │           └── main.py    - FastAPI-приложение gateway
    ├── frontend
    │   ├── Dockerfile         - сборка контейнера фронтенда
    │   ├── requirements.txt   - зависимости фронтенда
    │   └── src
    │       └── frontend
    │           ├── config.py  - настройки фронтенда
    │           ├── __init__.py
    │           ├── main.py    - FastAPI-приложение фронтенда
    │           ├── static
    │           │   └── app.js - JS: запросы к API, обновление UI, подключение к WebSocket
    │           └── templates
    │               └── index.html - HTML-шаблон страницы
    ├── orders-service
    │   ├── alembic
    │   │   ├── env.py         - конфигурация запуска Alembic
    │   │   └── versions
    │   │       └── 20251224181040_init.py - стартовая миграция orders
    │   ├── alembic.ini        - настройки Alembic 
    │   ├── Dockerfile         - сборка контейнера
    │   ├── entrypoint.sh      - старт: ожидание Postgres -> alembic upgrade -> запуск приложения
    │   ├── requirements.txt   - зависимости orders
    │   └── src
    │       └── orders
    │           ├── api
    │           │   ├── deps.py - зависимости FastAPI
    │           │   ├── __init__.py 
    │           │   └── routes.py - REST-роуты orders
    │           ├── config.py   - конфиг orders
    │           ├── consumers.py - консьюмер RabbitMQ
    │           ├── db
    │           │   ├── base.py 
    │           │   └── session.py - создание async engine + sessionmaker
    │           ├── __init__.py 
    │           ├── main.py     - FastAPI app + startup/shutdown
    │           ├── messaging
    │           │   ├── __init__.py 
    │           │   └── rabbit.py - обвязка aio-pika
    │           ├── models
    │           │   ├── inbox.py
    │           │   ├── __init__.py 
    │           │   ├── order.py 
    │           │   └── outbox.py 
    │           ├── outbox.py   - фоново публикует в RabbitMQ
    │           ├── schemas.py  - Pydantic-схемы запросов/ответов orders 
    │           └── websocket_manager.py - хранит WS-клиентов
    └── payments-service
        ├── alembic
        │   ├── env.py         - конфигурация Alembic для payments (engine/metadata/миграции)
        │   └── versions
        │       └── 20251224181334_init.py - стартовая миграция payments
        ├── alembic.ini        - настройки Alembic payments
        ├── Dockerfile         - сборка контейнера
        ├── entrypoint.sh      - старт
        ├── requirements.txt   - зависимости payments 
        └── src
            └── payments
                ├── api
                │   ├── deps.py - зависимости FastAPI 
                │   ├── __init__.py
                │   └── routes.py - REST-роуты payments
                ├── config.py   - конфиг payments
                ├── consumers.py - консьюмер RabbitMQ
                ├── db
                │   ├── base.py - общие модели SQLAlchemy
                │   └── session.py - async engine + sessionmaker
                ├── __init__.py
                ├── main.py     - FastAPI app
                ├── messaging
                │   ├── __init__.py
                │   └── rabbit.py - aio-pika обвязка
                ├── models
                │   ├── account.py 
                │   ├── inbox.py   
                │   ├── __init__.py 
                │   ├── outbox.py  
                │   └── payment.py
                ├── outbox.py   - фоновая публикация событий в RabbitMQ
                └── schemas.py  - Pydantic-схемы payments 

```
