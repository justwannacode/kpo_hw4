from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from orders.api.deps import get_user_id
from orders.config import settings
from orders.db.session import SessionLocal
from orders.models.order import Order, OrderStatus
from orders.models.outbox import OutboxMessage
from orders.schemas import OrderCreate, OrderRead
from orders.websocket_manager import ConnectionManager

router = APIRouter(prefix="/orders", tags=["orders"])
ws_router = APIRouter(tags=["ws"])

manager = ConnectionManager()


@router.post("", response_model=OrderRead)
async def create_order(payload: OrderCreate, user_id: int = Depends(get_user_id)):
    async with SessionLocal() as session:
        async with session.begin():
            order = Order(user_id=user_id, amount=payload.amount, description=payload.description, status=OrderStatus.NEW)
            session.add(order)
            await session.flush()

            evt = {
                "event_id": str(uuid4()),
                "type": "payment.request",
                "order_id": str(order.id),
                "user_id": user_id,
                "amount": payload.amount,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            session.add(
                OutboxMessage(
                    exchange=settings.exchange_events,
                    routing_key="payment.request",
                    payload=evt,
                )
            )
        await session.refresh(order)
        return order


@router.get("", response_model=list[OrderRead])
async def list_orders(user_id: int = Depends(get_user_id)):
    async with SessionLocal() as session:
        result = await session.execute(select(Order).where(Order.user_id == user_id).order_by(Order.created_at.desc()))
        return list(result.scalars().all())


@router.get("/{order_id}", response_model=OrderRead)
async def get_order(order_id: UUID, user_id: int = Depends(get_user_id)):
    async with SessionLocal() as session:
        order = (await session.execute(select(Order).where(Order.id == order_id, Order.user_id == user_id))).scalar_one_or_none()
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        return order


@ws_router.websocket("/ws/orders/{order_id}")
async def ws_order(websocket: WebSocket, order_id: UUID):
    await manager.connect(order_id, websocket)
    try:
        async with SessionLocal() as session:
            order = (await session.execute(select(Order).where(Order.id == order_id))).scalar_one_or_none()
            if order:
                await websocket.send_text(json.dumps({
                    "type": "order.status",
                    "order_id": str(order.id),
                    "user_id": order.user_id,
                    "status": order.status.value,
                    "updated_at": order.updated_at.isoformat(),
                }, ensure_ascii=False))
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(order_id, websocket)
    except Exception:
        await manager.disconnect(order_id, websocket)
        try:
            await websocket.close()
        except Exception:
            pass
