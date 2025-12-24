from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from payments.models.payment import PaymentStatus


class TopUpRequest(BaseModel):
    amount: int = Field(..., ge=1, description="Сумма в копейках/центах")


class BalanceResponse(BaseModel):
    user_id: int
    balance: int


class AccountResponse(BaseModel):
    user_id: int
    balance: int


class PaymentRequestEvent(BaseModel):
    event_id: str
    type: Literal["payment.request"]
    order_id: uuid.UUID
    user_id: int
    amount: int
    created_at: str


class PaymentResultEvent(BaseModel):
    event_id: str
    type: Literal["payment.result"]
    order_id: uuid.UUID
    user_id: int
    amount: int
    status: Literal["SUCCEEDED", "FAILED"]
    reason: str | None = None
    processed_at: str
