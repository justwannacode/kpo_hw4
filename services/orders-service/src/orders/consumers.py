from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from uuid import UUID

from aio_pika.abc import AbstractIncomingMessage
from sqlalchemy import insert, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import async_sessionmaker

from orders.config import settings
from orders.models.inbox import InboxMessage
from orders.models.order import Order, OrderStatus
from orders.models.outbox import OutboxMessage
from orders.schemas import PaymentResultEvent
from orders.websocket_manager import ConnectionManager
from orders.messaging.rabbit import Rabbit


async def payment_result_consumer(session_factory: async_sessionmaker, rabbit: Rabbit, stop_event: asyncio.Event) -> None:
    assert rabbit.channel is not None
    queue = await rabbit.channel.declare_queue("payment_results", durable=True)

    async with queue.iterator() as qiter:
        async for message in qiter:
            if stop_event.is_set():
                break
            await _handle_payment_result(message, session_factory)


async def _handle_payment_result(message: AbstractIncomingMessage, session_factory: async_sessionmaker) -> None:
    async with message.process(requeue=True):
        payload = json.loads(message.body.decode("utf-8"))
        evt = PaymentResultEvent(**payload)

        msg_id = message.message_id or evt.event_id

        async with session_factory() as session:
            async with session.begin():
                stmt = pg_insert(InboxMessage).values(message_id=msg_id, payload=payload).on_conflict_do_nothing(
                    index_elements=["message_id"]
                ).returning(InboxMessage.message_id)
                inserted = (await session.execute(stmt)).scalar_one_or_none()
                if inserted is None:
                    return

                order = (await session.execute(select(Order).where(Order.id == evt.order_id))).scalar_one_or_none()
                if not order:
                    return

                if order.status in (OrderStatus.FINISHED, OrderStatus.CANCELLED):
                    return

                order.status = OrderStatus.FINISHED if evt.status == "SUCCEEDED" else OrderStatus.CANCELLED

                ws_payload = {
                    "event_id": str(UUID(msg_id)) if _is_uuid(msg_id) else msg_id,
                    "type": "order.status",
                    "order_id": str(order.id),
                    "user_id": order.user_id,
                    "status": order.status.value,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
                session.add(
                    OutboxMessage(
                        exchange=settings.exchange_ws,
                        routing_key="order.status",
                        payload=ws_payload,
                    )
                )


def _is_uuid(val: str) -> bool:
    try:
        UUID(val)
        return True
    except Exception:
        return False


async def ws_broadcast_consumer(rabbit: Rabbit, manager: ConnectionManager, stop_event: asyncio.Event) -> None:
    assert rabbit.channel is not None
    queue = await rabbit.channel.declare_queue("", exclusive=True, auto_delete=True)
    assert rabbit.exchange_ws is not None
    await queue.bind(rabbit.exchange_ws, routing_key="order.status")

    async with queue.iterator() as qiter:
        async for message in qiter:
            if stop_event.is_set():
                break
            async with message.process(requeue=False):
                try:
                    payload = json.loads(message.body.decode("utf-8"))
                    order_id = UUID(payload["order_id"])
                    await manager.broadcast(order_id, json.dumps(payload, ensure_ascii=False))
                except Exception:
                    continue
