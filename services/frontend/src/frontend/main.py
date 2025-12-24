from __future__ import annotations

import asyncio
from typing import Any, Dict

import httpx
import websockets
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader, select_autoescape

from frontend.config import settings

app = FastAPI(title="Frontend", version="1.0.0")

templates = Environment(
    loader=FileSystemLoader("src/frontend/templates"),
    autoescape=select_autoescape(["html", "xml"]),
)

app.mount("/static", StaticFiles(directory="src/frontend/static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    tpl = templates.get_template("index.html")
    html = tpl.render()
    return HTMLResponse(html)


async def _proxy(method: str, path: str, headers: Dict[str, str] | None = None, json_body: Any | None = None):
    url = f"{settings.gateway_url}{path}"
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.request(method, url, headers=headers, json=json_body)
    return resp


def _user_headers(user_id: int) -> Dict[str, str]:
    return {"X-User-Id": str(user_id)}


@app.post("/api/accounts")
async def api_create_account(payload: dict):
    user_id = int(payload["user_id"])
    resp = await _proxy("POST", "/accounts", headers=_user_headers(user_id))
    return JSONResponse(status_code=resp.status_code, content=resp.json())


@app.post("/api/accounts/topup")
async def api_topup(payload: dict):
    user_id = int(payload["user_id"])
    amount = int(payload["amount"])
    resp = await _proxy("POST", "/accounts/topup", headers=_user_headers(user_id), json_body={"amount": amount})
    return JSONResponse(status_code=resp.status_code, content=resp.json())


@app.post("/api/orders")
async def api_create_order(payload: dict):
    user_id = int(payload["user_id"])
    amount = int(payload["amount"])
    description = str(payload.get("description", ""))
    resp = await _proxy("POST", "/orders", headers=_user_headers(user_id), json_body={"amount": amount, "description": description})
    return JSONResponse(status_code=resp.status_code, content=resp.json())


@app.get("/api/orders")
async def api_list_orders(user_id: int):
    resp = await _proxy("GET", "/orders", headers=_user_headers(int(user_id)))
    return JSONResponse(status_code=resp.status_code, content=resp.json())


@app.get("/api/accounts/balance")
async def api_balance(user_id: int):
    resp = await _proxy("GET", "/accounts/balance", headers=_user_headers(int(user_id)))
    return JSONResponse(status_code=resp.status_code, content=resp.json())


@app.websocket("/ws/orders/{order_id}")
async def ws_proxy(websocket: WebSocket, order_id: str):
    await websocket.accept()
    upstream = f"{settings.gateway_url.replace('http://', 'ws://').replace('https://', 'wss://')}/orders/{order_id}/ws"
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
