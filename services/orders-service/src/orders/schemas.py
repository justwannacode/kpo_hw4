from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from orders.models.order import OrderStatus


class OrderCreate(BaseModel):
    amount: int = Field(..., ge=1, description="Сумма в копейках/центах")
    description: str = Field(..., min_length=1, max_length=255)


class OrderRead(BaseModel):
    id: uuid.UUID
    id: uuid.UUID
    user_id: int
    amount: int
    description: str
    status: OrderStatus
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PaymentResultEvent(BaseModel):
    event_id: str
    type: Literal["payment.result"]
    order_id: uuid.UUID
    user_id: int
    amount: int
    status: Literal["SUCCEEDED", "FAILED"]
    reason: str | None = None
    processed_at: str
