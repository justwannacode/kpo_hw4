from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from orders.api.routes import router as orders_router, ws_router, manager
from orders.consumers import payment_result_consumer, ws_broadcast_consumer
from orders.db.session import SessionLocal
from orders.messaging.rabbit import Rabbit
from orders.outbox import outbox_publisher_loop

rabbit = Rabbit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await rabbit.connect()

    stop = asyncio.Event()
    tasks = [
        asyncio.create_task(outbox_publisher_loop(SessionLocal, rabbit, stop)),
        asyncio.create_task(payment_result_consumer(SessionLocal, rabbit, stop)),
        asyncio.create_task(ws_broadcast_consumer(rabbit, manager, stop)),
    ]
    try:
        yield
    finally:
        stop.set()
        for t in tasks:
            t.cancel()
        await rabbit.close()


app = FastAPI(title="Orders Service", version="1.0.0", lifespan=lifespan)
app.include_router(orders_router)
app.include_router(ws_router)
