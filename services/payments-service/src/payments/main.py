from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from payments.api.routes import router as accounts_router
from payments.consumers import payment_request_consumer
from payments.db.session import SessionLocal
from payments.messaging.rabbit import Rabbit
from payments.outbox import outbox_publisher_loop

rabbit = Rabbit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await rabbit.connect()
    stop = asyncio.Event()
    tasks = [
        asyncio.create_task(outbox_publisher_loop(SessionLocal, rabbit, stop)),
        asyncio.create_task(payment_request_consumer(SessionLocal, rabbit, stop)),
    ]
    try:
        yield
    finally:
        stop.set()
        for t in tasks:
            t.cancel()
        await rabbit.close()


app = FastAPI(title="Payments Service", version="1.0.0", lifespan=lifespan)
app.include_router(accounts_router)
