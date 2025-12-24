from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from uuid import uuid4

from aio_pika.abc import AbstractIncomingMessage
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import async_sessionmaker

from payments.config import settings
from payments.models.account import Account
from payments.models.inbox import InboxMessage
from payments.models.outbox import OutboxMessage
from payments.models.payment import Payment, PaymentStatus
from payments.schemas import PaymentRequestEvent


async def payment_request_consumer(session_factory: async_sessionmaker, rabbit, stop_event: asyncio.Event) -> None:
    assert rabbit.channel is not None
    queue = await rabbit.channel.declare_queue("payment_requests", durable=True)

    async with queue.iterator() as qiter:
        async for message in qiter:
            if stop_event.is_set():
                break
            await _handle_payment_request(message, session_factory)


async def _handle_payment_request(message: AbstractIncomingMessage, session_factory: async_sessionmaker) -> None:
    async with message.process(requeue=True):
        payload = json.loads(message.body.decode("utf-8"))
        evt = PaymentRequestEvent(**payload)

        msg_id = message.message_id or evt.event_id

        async with session_factory() as session:
            async with session.begin():
                # Transactional Inbox (by message_id)
                stmt = pg_insert(InboxMessage).values(message_id=msg_id, payload=payload).on_conflict_do_nothing(
                    index_elements=["message_id"]
                )
                await session.execute(stmt)

                # Idempotency by order_id (effectively exactly once)
                existing = (await session.execute(select(Payment).where(Payment.order_id == evt.order_id))).scalar_one_or_none()
                if existing:
                    await _enqueue_result(session, existing, evt, reason=existing.reason)
                    return

                acc = (await session.execute(select(Account).where(Account.user_id == evt.user_id))).scalar_one_or_none()
                if not acc:
                    payment = Payment(order_id=evt.order_id, user_id=evt.user_id, amount=evt.amount, status=PaymentStatus.FAILED, reason="Account not found")
                    session.add(payment)
                    await session.flush()
                    await _enqueue_result(session, payment, evt, reason=payment.reason)
                    return

                res = await session.execute(
                    update(Account)
                    .where(Account.user_id == evt.user_id, Account.balance >= evt.amount)
                    .values(balance=Account.balance - evt.amount)
                    .returning(Account.balance)
                )
                new_balance = res.scalar_one_or_none()

                if new_balance is None:
                    payment = Payment(order_id=evt.order_id, user_id=evt.user_id, amount=evt.amount, status=PaymentStatus.FAILED, reason="Insufficient funds")
                    session.add(payment)
                    await session.flush()
                    await _enqueue_result(session, payment, evt, reason=payment.reason)
                    return

                payment = Payment(order_id=evt.order_id, user_id=evt.user_id, amount=evt.amount, status=PaymentStatus.SUCCEEDED, reason=None)
                session.add(payment)
                await session.flush()
                await _enqueue_result(session, payment, evt, reason=None)


async def _enqueue_result(session, payment: Payment, request_evt: PaymentRequestEvent, reason: str | None) -> None:
    result_evt = {
        "event_id": str(uuid4()),
        "type": "payment.result",
        "order_id": str(payment.order_id),
        "user_id": payment.user_id,
        "amount": payment.amount,
        "status": payment.status.value,
        "reason": reason,
        "processed_at": datetime.now(timezone.utc).isoformat(),
    }
    session.add(
        OutboxMessage(
            exchange=settings.exchange_events,
            routing_key="payment.result",
            payload=result_evt,
        )
    )
