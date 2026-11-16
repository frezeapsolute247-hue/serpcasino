"""Клиент xRocket Pay API (новый). ВСЕ запросы к xRocket только здесь.

Токен и адрес API берутся из config.py (XROCKET_TOKEN, XROCKET_BASE_URL).

Новый API (pay.api.xrocket.exchange), авторизация: Authorization: Bearer <token>
Счёт на пополнение:  POST /api/v1/invoices
Статус счёта:        GET  /api/v1/invoice?invoiceId=...
Чек на вывод:        POST /api/v1/cheques
Баланс приложения:   GET  /api/v1/balances
"""
import json
import time

import aiohttp

import config


class XRocketError(Exception):
    pass


def _headers() -> dict:
    return {config.XROCKET_AUTH_HEADER: config.XROCKET_AUTH_PREFIX + config.XROCKET_TOKEN}


async def _request(method: str, path: str, body: dict | None = None,
                   params: dict | None = None):
    url = config.XROCKET_BASE_URL.rstrip("/") + path
    timeout = aiohttp.ClientTimeout(total=20)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.request(method, url, json=body, params=params,
                                   headers=_headers()) as resp:
            raw = await resp.text()
            try:
                data = json.loads(raw)
            except Exception:
                data = {"raw": raw[:300]}
            if resp.status >= 400 or (isinstance(data, dict) and data.get("success") is False):
                detail = ""
                if isinstance(data, dict):
                    info = data.get("info") or {}
                    detail = data.get("detail") or data.get("title") or ""
                    if isinstance(info, dict) and info.get("errors"):
                        detail += f" {info['errors']}"
                    elif info:
                        detail += f" {info}"
                raise XRocketError(f"{resp.status} {path}: {detail or raw[:200]}")
            return data


async def create_invoice(amount: float, description: str, payload: str) -> tuple[str, str]:
    """Счёт на пополнение. Возвращает (id счёта, ссылка на оплату)."""
    data = await _request("POST", "/api/v1/invoices", {
        "priceCurrency": "USDT",
        "priceAmount": f"{amount:.2f}",          # только строкой!
        "numPayments": 1,
        "description": description,
        "clientInvoiceId": f"{payload}-{int(time.time())}",   # уникальный на каждый счёт
        "expiresIn": config.INVOICE_LIFETIME_MIN * 60 * 1000,   # миллисекунды
    })
    links = data.get("links") or {}
    link = links.get("telegramBotLink") or links.get("telegramMiniAppLink")
    inv_id = data.get("id")
    if not inv_id or not link:
        raise XRocketError(f"неожиданный ответ на создание счёта: {data}")
    return str(inv_id), link


# статусы нового API -> статусы, которые ждёт бот
_STATUS = {
    "paid": "paid",
    "partially_paid": "active",
    "active": "active",
    "expired": "expired",
    "cancelled": "expired",
}


async def invoice_status(invoice_id: str) -> str:
    """'active' | 'paid' | 'expired'"""
    data = await _request("GET", "/api/v1/invoice", params={"invoiceId": str(invoice_id)})
    return _STATUS.get(str(data.get("status", "active")), "active")


async def create_cheque(tg_user_id: int, amount: float, description: str) -> str:
    """Личный чек игроку (вывод). Возвращает ссылку на чек.

    Внимание: чеки должны быть включены для приложения в @xRocket,
    иначе API отвечает 403 operation_disabled.
    """
    data = await _request("POST", "/api/v1/cheques", {
        "asset": "USDT",
        "amount": f"{amount:.2f}",
        "description": description,
        "targetType": "telegram_user_id",
        "target": str(tg_user_id),
    })
    links = data.get("links") or {}
    link = links.get("telegramBotLink") or links.get("telegramMiniAppLink")
    if not link:
        raise XRocketError(f"неожиданный ответ на создание чека: {data}")
    return link


async def app_balances() -> list:
    """Балансы приложения в xRocket (для /казна).

    Ответ API: {"balances": [{"asset": "USDT", "balance": "2.167",
                              "available": "2.167", "holds": "0"}, ...]}
    Возвращает только ненулевые активы: [{"asset","balance","available"}]
    """
    data = await _request("GET", "/api/v1/balances")
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        items = data.get("balances") or data.get("items") or []
    else:
        items = []
    out = []
    for b in items:
        if not isinstance(b, dict) or not b.get("asset"):
            continue
        try:
            bal = float(b.get("balance") or 0)
        except (TypeError, ValueError):
            continue
        if bal <= 0:
            continue
        try:
            avail = float(b.get("available") or 0)
        except (TypeError, ValueError):
            avail = bal
        out.append({"asset": str(b["asset"]).upper(), "balance": bal, "available": avail})
    out.sort(key=lambda x: -x["balance"])
    return out


async def _rates() -> dict:
    """Курсы активов к доллару: {"USDT": 1.0, "TON": 2.4, ...}"""
    try:
        data = await _request("GET", "/api/v1/rates")
    except Exception:
        return {}
    rows = data if isinstance(data, list) else (data or {}).get("rates") or []
    rates = {}
    for r in rows:
        if not isinstance(r, dict):
            continue
        try:
            rates[str(r.get("currency") or "").upper()] = float(r.get("rate") or 0)
        except (TypeError, ValueError):
            continue
    return rates


async def app_balance_usd() -> tuple[float, list]:
    """Сколько всего денег на счёте приложения: (сумма в долларах, активы)."""
    bals = await app_balances()
    if not bals:
        return 0.0, []
    rates = await _rates()
    total = 0.0
    for b in bals:
        asset = b["asset"]
        rate = rates.get(asset)
        if rate is None:
            rate = 1.0 if asset in ("USDT", "USD", "jUSDT") else 0.0
        total += b["balance"] * rate
    return total, bals
