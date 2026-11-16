"""Тексты экранов, кнопки и кастомные эмодзи SERP CASINO.

Всё оформление — тексты и кнопки — берётся из одного места: словаря ICONS.
Там у каждого пункта пара: кастомный emoji id (если он есть) и обычный эмодзи,
который подставляется, если кастомный отключён в config (USE_BUTTON_ICONS).
Свои id вписывай прямо в ICONS — больше нигде эмодзи не ищутся.
"""
import re
from datetime import datetime, timedelta, timezone
from html import escape

from aiogram.types import (InlineKeyboardButton, InlineKeyboardMarkup,
                           KeyboardButton, ReplyKeyboardMarkup)

import config
import games
from db import M, usd

TZ = timezone(timedelta(hours=config.TZ_OFFSET_HOURS))

# ── ID кастомных эмодзи ──────────────────────────────────────────────────
E_TITLE = "5800849384790828447"     # 🎰 SERP CASINO
E_BALANCE = "5472363448404809929"   # 👛 баланс
E_GAMES = "5938413566624272793"     # 🎮 игры
E_WIN = "5280769763398671636"       # 🏆 выиграно

I_PLAY = "5938413566624272793"
I_DEPOSIT = "5769126056262898415"
I_WITHDRAW = "5902206159095339799"
I_PROFILE = "6035084557378654059"
I_CASHBACK = "5773677501825945508"
I_STATS = "6037475557082403885"
I_XROCKET = "5415897719522744378"

# ключ → (кастомный emoji id или None, обычный эмодзи)
ICONS = {
    "title":    (E_TITLE, "🎰"),
    "balance":  (E_BALANCE, "👛"),
    "games":    (E_GAMES, "🎮"),
    "win":      (E_WIN, "🏆"),
    "play":     (I_PLAY, "🎮"),
    "deposit":  (I_DEPOSIT, "👛"),
    "withdraw": (I_WITHDRAW, "💸"),
    "profile":  (I_PROFILE, "👤"),
    "cashback": (I_CASHBACK, "🎁"),
    "stats":    (I_STATS, "📊"),
    "xrocket":  (I_XROCKET, "💎"),
    "back":     (None, "⬅️"),
    "menu":     (None, "🏠"),
    "history":  (None, "🕘"),
    "ops":      (None, "🧾"),
    "treasury": (None, "🏦"),
    "support":  (None, "💬"),
    "money":    (None, "💰"),
    "bet":      (None, "💵"),
    "top":      (None, "🏆"),
    "chat":     (None, "💬"),
    "lock":     (None, "🔒"),
    "open":     (None, "🔓"),
    "users":    (None, "👥"),
    "list":     (None, "🗂"),
}


def ce(emoji_id: str, fallback: str) -> str:
    """Кастомный эмодзи в тексте сообщения."""
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'


def ic(key: str) -> str:
    """Эмодзи по ключу: кастомный, если он есть, иначе обычный."""
    cid, fallback = ICONS.get(key, (None, ""))
    if cid and config.USE_BUTTON_ICONS:
        return ce(cid, fallback)
    return fallback


def quote(text: str) -> str:
    return f"<blockquote>{text}</blockquote>"


HEAD = quote(f"{ce(E_TITLE, '🎰')} SERP CASINO")


def head(icon: str, title: str) -> str:
    return quote(f"{icon} {title}")


# ── кнопки ───────────────────────────────────────────────────────────────
# то же оформление для кнопок, у которых эмодзи берётся по тексту
BY_TEXT = {
    "назад": "back", "меню": "menu", "игры": "games", "играть": "play",
    "баланс": "balance", "пополнить": "deposit", "вывести": "withdraw",
    "профиль": "profile", "кэшбек": "cashback", "статистика": "stats",
    "история": "history", "операции": "ops", "поддержка": "support",
    "топ игроков": "top", "топ чатов": "chat", "к категориям": "back",
    "открыть бота": "open", "всё": "money", "забрать на баланс": "cashback",
    "забрать чек": "withdraw", "xrocket": "xrocket",
}


def B(text, cb=None, url=None, icon=None, style=None) -> InlineKeyboardButton:
    """Кнопка. icon — id кастомного эмодзи или ключ из ICONS."""
    cid, fallback = None, None
    if icon in ICONS:                      # ключ: id + запасной эмодзи
        cid, fallback = ICONS[icon]
    elif icon:                             # готовый id кастомного эмодзи
        cid = icon
    else:                                  # эмодзи по тексту кнопки
        key = BY_TEXT.get(text.strip().lower())
        if key:
            cid, fallback = ICONS[key]
    if cid and not config.USE_BUTTON_ICONS:
        cid = None

    extra = {}
    if cid:
        extra["icon_custom_emoji_id"] = cid
    elif fallback:
        text = f"{fallback} {text}"
    if style and config.USE_BUTTON_STYLE:
        extra["style"] = style  # "primary" (синяя) | "success" (зелёная) | "danger"
    try:
        return InlineKeyboardButton(text=text, callback_data=cb, url=url, **extra)
    except TypeError:
        # старая aiogram не знает про style/icon_custom_emoji_id — шлём простую кнопку
        if "icon_custom_emoji_id" in extra and fallback:
            text = f"{fallback} {text}"
        return InlineKeyboardButton(text=text, callback_data=cb, url=url)


def kb(*rows) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[list(r) for r in rows])


def reply_kb() -> ReplyKeyboardMarkup:
    extra = {"style": "primary"} if config.USE_BUTTON_STYLE else {}

    def btn(text):
        try:
            return KeyboardButton(text=text, **extra)
        except TypeError:
            return KeyboardButton(text=text)

    return ReplyKeyboardMarkup(
        keyboard=[[btn("🏠 Меню"), btn("🎮 Играть"), btn("👛 Баланс")]],
        resize_keyboard=True, is_persistent=True,
    )


BACK_MENU = kb([B("Меню", "menu", icon="menu")])


def main_kb():
    return kb(
        [B("Играть", "games", icon="play", style="success")],
        [B("Пополнить", "deposit", icon="deposit", style="primary"),
         B("Вывести", "withdraw", icon="withdraw", style="primary")],
        [B("Профиль", "profile", icon="profile"), B("Кэшбек", "cashback", icon="cashback")],
        [B("Статистика", "stats", icon="stats")],
    )


def games_kb(private: bool = True):
    rows, row = [], []
    for g in games.GAME_ORDER:
        icon, name = games.GAME_TITLES[g]
        row.append(B(f"{icon} {name}", f"g:{g}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    if private:
        rows.append([B("Меню", "menu", icon="menu")])
    return kb(*rows)


def picks_kb(game: str):
    icon = games.GAME_TITLES[game][0]
    rows = []
    for prow in games.PICKS[game]:
        rows.append([B(f"{icon} {label} · {games.mult_text(m)}", f"p:{game}:{code}")
                     for label, code, m in prow])
    rows.append([B("Назад", "games", icon="back")])
    return kb(*rows)


def bet_kb(game: str):
    presets = [0.1, 0.5, 1, 5, 10]
    return kb([B(f"{p:g}$", f"a:{p}", icon="bet") for p in presets],
              [B("Назад", f"g:{game}", icon="back")])


def wallet_kb():
    return kb(
        [B("Пополнить", "deposit", icon="deposit", style="primary"),
         B("Вывести", "withdraw", icon="withdraw", style="primary")],
        [B("Операции", "ops", icon="ops")],
        [B("Назад", "menu", icon="back")],
    )


def deposit_text() -> str:
    return (f"{head(ic('deposit'), 'Пополнение')}\n\n"
            f"Минимум — {config.MIN_DEPOSIT:.2f} $\n\nВыберите способ оплаты 👇")


def deposit_kb():
    return kb([B("xRocket", "dep_xr", icon="xrocket")],
              [B("Назад", "menu", icon="back")])


def withdraw_text(u) -> str:
    return (f"{head(ic('withdraw'), 'Вывод · xRocket')}\n\n"
            f"Баланс — {usd(u['balance'])} $\n"
            f"Минимум — {config.MIN_WITHDRAW:.2f} $\n\nОтправьте сумму 👇")


def withdraw_kb(u):
    return kb([B(f"Всё · {usd(u['balance'])} $", "wd_all", icon="money", style="primary")],
              [B("Назад", "menu", icon="back")])


# ── форматирование ───────────────────────────────────────────────────────
def fmt_ts(ts: int) -> str:
    return datetime.fromtimestamp(ts, TZ).strftime("%d.%m %H:%M")


def name_of(u) -> str:
    return f"@{escape(u['username'])}" if u["username"] else escape(u["first_name"] or "игрок")


def signed(a: int) -> str:
    return f"{'+' if a > 0 else '-'}{abs(a) / M:.2f} $"


KIND = {
    "bet": ("🎮", "Ставка"), "win": ("🏆", "Выигрыш"), "cashback": ("🎁", "Кэшбек"),
    "deposit": ("💳", "Пополнение"), "withdraw": ("💸", "Вывод"),
    "withdraw_refund": ("↩️", "Возврат вывода"), "refund": ("↩️", "Возврат ставки"),
}

MEDALS = ["🥇", "🥈", "🥉"]


# ── тексты экранов ───────────────────────────────────────────────────────
def menu_text(u) -> str:
    return (f"{HEAD}\n\nПривет, {name_of(u)} 👋\n\n"
            f"{ic('balance')} Баланс — {usd(u['balance'])} $\n"
            f"{ic('games')} Игр — {u['games']} · "
            f"{ic('win')} Выиграно — {usd(u['won'])} $")


def games_text(u) -> str:
    return (f"{quote(ic('games') + ' Игры')}\n\n"
            f"{ic('balance')} Баланс — {usd(u['balance'])} $\n\n"
            f"Выбирай режим 👇")


def wallet_text(u) -> str:
    return (f"{head(ic('balance'), 'Кошелёк')}\n\n"
            f"Баланс — {usd(u['balance'])} $\n"
            f"Кэшбек — {usd(u['cashback'])} $")


def profile_text(u) -> str:
    wr = round(u["wins"] / u["games"] * 100) if u["games"] else 0
    joined = datetime.fromtimestamp(u["joined_at"], TZ).strftime("%d.%m.%Y")
    stats = quote(f"🎮 Игр — {u['games']} · винрейт {wr}%\n"
                  f"📈 Оборот — {usd(u['wagered'])} $\n"
                  f"📅 С нами с {joined}")
    return (f"{head(ic('profile'), 'Профиль')}\n\n{name_of(u)}\n"
            f"{ic('balance')} Баланс — {usd(u['balance'])} $\n\n{stats}")


def profile_kb():
    rows = [[B("История", "history", icon="history"), B("Операции", "ops", icon="ops")]]
    # SUPPORT_LINK по умолчанию "none" — такую «ссылку» Telegram не примет,
    # поэтому кнопка появляется только для настоящего адреса.
    if config.SUPPORT_LINK.startswith("http"):
        rows.append([B("Поддержка", url=config.SUPPORT_LINK, icon="support")])
    rows.append([B("Назад", "menu", icon="back")])
    return kb(*rows)


def history_text(rows) -> str:
    if not rows:
        return f"{head(ic('history'), 'История игр')}\n\nПока нет игр."
    lines = []
    for r in rows:
        icon, title = games.GAME_TITLES[r["game"]]
        if r["outcome"] == "win":
            res = f"🏆 +{usd(r['payout'])} $"
        elif r["outcome"] == "push":
            res = "↩️ возврат"
        else:
            res = f"❌ -{usd(r['bet'])} $"
        lines.append(f"{fmt_ts(r['ts'])} · {icon} {title} · {usd(r['bet'])} $ → {res}")
    return f"{head(ic('history'), 'История игр')}\n\n" + quote("\n".join(lines))


def ops_text(rows) -> str:
    if not rows:
        return f"{head(ic('ops'), 'Операции')}\n\nПока нет операций."
    lines = []
    for r in rows:
        icon, title = KIND.get(r["kind"], ("•", r["kind"]))
        lines.append(f"{fmt_ts(r['ts'])} · {icon} {title} · {signed(r['amount'])}")
    return f"{head(ic('ops'), 'Операции')}\n\n" + quote("\n".join(lines))


def cashback_text(u) -> str:
    return (f"{head(ic('cashback'), 'Кэшбек')}\n\nНакоплено — {usd(u['cashback'])} $\n\n"
            + quote(f"Возвращаем {config.CASHBACK_PERCENT}% с каждого проигрыша. "
                    f"Вывод на баланс от {config.MIN_CASHBACK_CLAIM:g} $"))


def cashback_kb():
    return kb([B("Забрать на баланс", "cb_claim", icon="cashback", style="success")],
              [B("Назад", "menu", icon="back")])


def top_text(title: str, rows) -> str:
    if not rows:
        return f"{head(ic('top'), title)}\n\nПока нет данных."
    lines = []
    for i, r in enumerate(rows):
        mark = MEDALS[i] if i < 3 else f"{i + 1}."
        lines.append(f"{mark} {escape(r['name'] or '—')} — {usd(r['turnover'])} $")
    return f"{head(ic('top'), title)}\n\n" + "\n".join(lines)


# ── казна: деньги всего казино ───────────────────────────────────────────
def treasury_text(t, xr: dict) -> str:
    """t — сводка из БД, xr — реальный баланс приложения в xRocket.

    xr = {"total": 2.17, "assets": [{"asset": "USDT", "balance": 2.167}], "error": None}
    """
    assets = xr.get("assets") or []
    total = xr.get("total") or 0.0
    net = t["deposits"] - t["withdraws"] - t["balances"]

    lines = [head(ic("treasury"), "Казна SERP CASINO"), ""]
    if xr.get("error"):
        lines.append(f"{ic('xrocket')} xRocket — баланс недоступен")
        lines.append(quote(f"Ошибка: {escape(xr['error'])}"))
    else:
        lines.append(f"{ic('xrocket')} xRocket — <b>{total:.2f} $</b>")
        if assets:
            for a in assets[:8]:
                lines.append(f"   · {escape(str(a['asset']))} — {a['balance']:g}")
        else:
            lines.append("   · пусто, на счёте приложения ничего нет")
        lines.append("")
        lines.append(f"{ic('money')} Всего в кассе — <b>{total:.2f} $</b>")

    lines.append("")
    lines.append(quote(
        f"{ic('users')} Игроков — <b>{t['users']}</b> (с балансом: {t['players']})\n"
        f"{ic('balance')} На балансах игроков — <b>{usd(t['balances'])} $</b>\n"
        f"{ic('cashback')} Кэшбек накоплен — {usd(t['cashback'])} $\n"
        f"{ic('deposit')} Пополнено — {usd(t['deposits'])} $ · выведено — {usd(t['withdraws'])} $\n"
        f"{ic('games')} Ставок — {usd(t['bets'])} $ · выплачено — {usd(t['wins'])} $\n"
        f"🕹 Игр сыграно — {t['games']}"
    ))
    lines.append("")
    lines.append(quote(
        f"📊 Чистая касса — <b>{usd(net)} $</b>\n"
        f"= пополнения − выводы − балансы игроков"
    ))
    return "\n".join(lines)
