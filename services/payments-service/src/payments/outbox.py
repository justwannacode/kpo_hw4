from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from payments.config import settings
from payments.models.outbox import OutboxMessage
from payments.messaging.rabbit import Rabbit


async def outbox_publisher_loop(session_factory: async_sessionmaker, rabbit: Rabbit, stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        try:
            async with session_factory() as session:
                async with session.begin():
                    result = await session.execute(
                        select(OutboxMessage)
                        .where(OutboxMessage.published_at.is_(None))
                        .order_by(OutboxMessage.created_at.asc())
                        .with_for_update(skip_locked=True)
                        .limit(50)
                    )
                    messages = list(result.scalars().all())
                    for msg in messages:
                        msg.attempts += 1
                        try:
                            await rabbit.publish(
                                routing_key=msg.routing_key,
                                payload=msg.payload,
                                message_id=str(msg.id),
                            )
                            msg.published_at = datetime.now(timezone.utc)
                            msg.last_error = None
                        except Exception as e:
                            msg.last_error = str(e)[:500]
            await asyncio.sleep(settings.outbox_poll_interval_sec)
        except Exception:
            await asyncio.sleep(1.0)
