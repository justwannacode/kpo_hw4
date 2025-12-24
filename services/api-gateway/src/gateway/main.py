from __future__ import annotations

import asyncio
from typing import Any, Dict

import httpx
import websockets
from fastapi import FastAPI, Header, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from gateway.config import settings

app = FastAPI(title="API Gateway", version="1.0.0")


async def _proxy(
    method: str,
    upstream_url: str,
    path: str,
    headers: Dict[str, str],
    json_body: Any | None = None,
    params: Dict[str, Any] | None = None,
):
    url = f"{upstream_url}{path}"
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.request(method, url, headers=headers, json=json_body, params=params)
    return resp


def _user_headers(x_user_id: int | None) -> Dict[str, str]:
    if x_user_id is None:
        raise HTTPException(status_code=400, detail="X-User-Id header is required")
    return {"X-User-Id": str(x_user_id)}


@app.exception_handler(httpx.HTTPError)
async def httpx_error_handler(_: Request, exc: httpx.HTTPError):
    return JSONResponse(status_code=502, content={"detail": f"Upstream error: {exc!s}"})


@app.post("/accounts")
async def create_account(x_user_id: int | None = Header(default=None, alias="X-User-Id")):
    resp = await _proxy("POST", settings.payments_service_url, "/accounts", _user_headers(x_user_id))
    return JSONResponse(status_code=resp.status_code, content=resp.json())


@app.post("/accounts/topup")
async def topup_account(payload: dict, x_user_id: int | None = Header(default=None, alias="X-User-Id")):
    resp = await _proxy("POST", settings.payments_service_url, "/accounts/topup", _user_headers(x_user_id), json_body=payload)
    return JSONResponse(status_code=resp.status_code, content=resp.json())


@app.get("/accounts/balance")
async def get_balance(x_user_id: int | None = Header(default=None, alias="X-User-Id")):
    resp = await _proxy("GET", settings.payments_service_url, "/accounts/balance", _user_headers(x_user_id))
    return JSONResponse(status_code=resp.status_code, content=resp.json())


@app.post("/orders")
async def create_order(payload: dict, x_user_id: int | None = Header(default=None, alias="X-User-Id")):
    resp = await _proxy("POST", settings.orders_service_url, "/orders", _user_headers(x_user_id), json_body=payload)
    return JSONResponse(status_code=resp.status_code, content=resp.json())


@app.get("/orders")
async def list_orders(x_user_id: int | None = Header(default=None, alias="X-User-Id")):
    resp = await _proxy("GET", settings.orders_service_url, "/orders", _user_headers(x_user_id))
    return JSONResponse(status_code=resp.status_code, content=resp.json())


@app.get("/orders/{order_id}")
async def get_order(order_id: str, x_user_id: int | None = Header(default=None, alias="X-User-Id")):
    resp = await _proxy("GET", settings.orders_service_url, f"/orders/{order_id}", _user_headers(x_user_id))
    return JSONResponse(status_code=resp.status_code, content=resp.json())


@app.websocket("/orders/{order_id}/ws")
async def ws_order_status(websocket: WebSocket, order_id: str):
    await websocket.accept()
    upstream = f"{settings.orders_service_url.replace('http://', 'ws://').replace('https://', 'wss://')}/ws/orders/{order_id}"
    try:
        async with websockets.connect(upstream) as upstream_ws:
            async def forward_upstream():
                async for msg in upstream_ws:
                    await websocket.send_text(msg)

            async def drain_client():
                while True:
                    await websocket.receive_text()

            t1 = asyncio.create_task(forward_upstream())
            t2 = asyncio.create_task(drain_client())
            done, pending = await asyncio.wait({t1, t2}, return_when=asyncio.FIRST_EXCEPTION)
            for p in pending:
                p.cancel()
    except WebSocketDisconnect:
        return
    except Exception:
        try:
            await websocket.close()
        except Exception:
            pass
