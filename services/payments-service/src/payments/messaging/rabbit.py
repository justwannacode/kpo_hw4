from __future__ import annotations

import json
from typing import Any, Dict

import aio_pika
from aio_pika import DeliveryMode, ExchangeType, Message, RobustChannel, RobustConnection

from payments.config import settings


class Rabbit:
    def __init__(self) -> None:
        self.connection: RobustConnection | None = None
        self.channel: RobustChannel | None = None
        self.exchange_events = None

    async def connect(self) -> None:
        self.connection = await aio_pika.connect_robust(settings.rabbitmq_url)
        self.channel = await self.connection.channel(publisher_confirms=True)
        await self.channel.set_qos(prefetch_count=settings.consumer_prefetch)

        self.exchange_events = await self.channel.declare_exchange(
            settings.exchange_events, ExchangeType.DIRECT, durable=True
        )

        q_requests = await self.channel.declare_queue("payment_requests", durable=True)
        await q_requests.bind(self.exchange_events, routing_key="payment.request")
        q_results = await self.channel.declare_queue("payment_results", durable=True)
        await q_results.bind(self.exchange_events, routing_key="payment.result")

    async def close(self) -> None:
        if self.connection:
            await self.connection.close()

    async def publish(self, routing_key: str, payload: Dict[str, Any], message_id: str) -> None:
        assert self.exchange_events is not None
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        msg = Message(
            body=body,
            message_id=message_id,
            delivery_mode=DeliveryMode.PERSISTENT,
            content_type="application/json",
        )
        await self.exchange_events.publish(msg, routing_key=routing_key)
