from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update

from payments.api.deps import get_user_id
from payments.db.session import SessionLocal
from payments.models.account import Account
from payments.schemas import AccountResponse, BalanceResponse, TopUpRequest

router = APIRouter(tags=["accounts"])


@router.post("/accounts", response_model=AccountResponse)
async def create_account(user_id: int = Depends(get_user_id)):
    async with SessionLocal() as session:
        async with session.begin():
            existing = (await session.execute(select(Account).where(Account.user_id == user_id))).scalar_one_or_none()
            if existing:
                raise HTTPException(status_code=409, detail="Account already exists")
            acc = Account(user_id=user_id, balance=0)
            session.add(acc)
        return AccountResponse(user_id=user_id, balance=0)


@router.post("/accounts/topup", response_model=BalanceResponse)
async def topup(payload: TopUpRequest, user_id: int = Depends(get_user_id)):
    async with SessionLocal() as session:
        async with session.begin():
            # atomic add
            res = await session.execute(
                update(Account)
                .where(Account.user_id == user_id)
                .values(balance=Account.balance + payload.amount)
                .returning(Account.balance)
            )
            new_balance = res.scalar_one_or_none()
            if new_balance is None:
                raise HTTPException(status_code=404, detail="Account not found")
        return BalanceResponse(user_id=user_id, balance=int(new_balance))


@router.get("/accounts/balance", response_model=BalanceResponse)
async def balance(user_id: int = Depends(get_user_id)):
    async with SessionLocal() as session:
        acc = (await session.execute(select(Account).where(Account.user_id == user_id))).scalar_one_or_none()
        if not acc:
            raise HTTPException(status_code=404, detail="Account not found")
        return BalanceResponse(user_id=user_id, balance=acc.balance)
