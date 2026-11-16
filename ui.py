"""Тексты экранов, кнопки и эмодзи SERP CASINO.

Всё оформление — заголовки, строки текста и кнопки — берёт эмодзи из одного
словаря E. Значение = (id кастомного эмодзи, обычный эмодзи).
id=None -> обычный эмодзи. Впиши свой id вместо None — эмодзи сразу
появится и в тексте, и на кнопке, ничего больше менять не нужно.
"""
from datetime import datetime, timedelta, timezone
from html import escape

from aiogram.types import (InlineKeyboardButton, InlineKeyboardMarkup,
                           KeyboardButton, ReplyKeyboardMarkup)

import config
import games
from db import M, usd

TZ = timezone(timedelta(hours=config.TZ_OFFSET_HOURS))

# ── Эмодзи оформления ────────────────────────────────────────────────────
E: dict[str, tuple[str | None, str]] = {
    # id уже есть (из старого ui.py) — эти работают и в тексте, и иконками кнопок
    "casino":    ("5800849384790828447", "🎰"),
    "balance":   ("5472363448404809929", "👛"),
    "games":     ("5938413566624272793", "🎮"),
    "play":      ("5938413566624272793", "🎮"),
    "win":       ("5280769763398671636", "🏆"),
    "deposit":   ("5769126056262898415", "💳"),
    "withdraw":  ("5902206159095339799", "💸"),
    "profile":   ("6035084557378654059", "👤"),
    "cashback":  ("5773677501825945508", "🎁"),
    "stats":     ("6037475557082403885", "📊"),
    "xrocket":   ("5415897719522744378", "🚀"),
    # id пока нет — обычный эмодзи, можно вписать свой
    "menu":      (None, "🏠"),
    "back":      (None, "⬅️"),
    "history":   (None, "🕘"),
    "ops":       (None, "🧾"),
    "treasury":  (None, "🏦"),
    "money":     (None, "💰"),
    "coin":      (None, "🪙"),
    "bet":       (None, "🎯"),
    "dice":      (None, "🎲"),
    "slots":     (None, "🎰"),
    "knb":       (None, "✊"),
    "football":  (None, "⚽"),
    "basket":    (None, "🏀"),
    "bowling":   (None, "🎳"),
    "darts":     (None, "🎯"),
    "lock":      (None, "🔒"),
    "wait":      (None, "⏳"),
    "repeat":    (None, "🔄"),
    "lose":      (None, "❌"),
    "push":      (None, "↩️"),
    "alert":     (None, "⚠️"),
    "check":     (None, "✅"),
}

# Кастомные иконки для кнопок игр (необязательно): "dice": "5400000000000000000".
# Пока пусто — на кнопках игр обычные эмодзи из GAME_TITLES.
GAME_EMOJI_ID: dict[str, str] = {}

# Эмодзи на кнопках выбора исхода — по коду исхода.
PICK_EMOJI: dict[str, str] = {
    "n1": "1️⃣", "n2": "2️⃣", "n3": "3️⃣", "n4": "4️⃣", "n5": "5️⃣", "n6": "6️⃣",
    "less": "🔽", "more": "🔼", "even": "2️⃣", "odd": "1️⃣",
    "p1": "1️⃣", "p2": "2️⃣", "draw": "🤝",
    "2less": "🔽", "2more": "🔼",
    "2even": "2️⃣", "2odd": "1️⃣",
    "center": "🎯", "bounce": "💨", "red": "🔴", "white": "⚪",
    "goal": "⚽", "miss": "❌", "goal_c": "🥅", "goal_a": "🎯",
    "hit": "🏀", "strike": "🎳", "spin": "🎰",
    "heads": "🪙", "tails": "🪙",
    "rock": "✊", "scissors": "✌️", "paper": "✋",
}


def ce(emoji_id: str | None, fallback: str) -> str:
    """Кастомный эмодзи в тексте сообщения (если id известен и включён)."""
    if not emoji_id or not config.USE_TEXT_EMOJI:
        return fallback
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'


def em(key: str) -> str:
    """Эмодзи для текста по ключу из E."""
    eid, plain = E.get(key, (None, "•"))
    return ce(eid, plain)


def eicon(key: str | None) -> str | None:
    """id кастомного эмодзи для кнопки. None -> на кнопке обычный эмодзи."""
    if not key or not config.USE_BUTTON_ICONS:
        return None
    return E.get(key, (None, None))[0]


def quote(text: str) -> str:
    return f"<blockquote>{text}</blockquote>"


def head(key: str, title: str) -> str:
    return quote(f"{em(key)} {title}")


HEAD = quote(f"{em('casino')} SERP CASINO")


# ── кнопки ───────────────────────────────────────────────────────────────
def B(text, cb=None, url=None, key=None, style=None) -> InlineKeyboardButton:
    """Кнопка всегда с эмодзи: кастомная иконка по key или обычный эмодзи в тексте."""
    eid = eicon(key)
    extra = {}
    if eid:
        extra["icon_custom_emoji_id"] = eid
    elif key:
        plain = E.get(key, (None, ""))[1]
        if plain:
            text = f"{plain} {text}"
    if style and config.USE_BUTTON_STYLE:
        extra["style"] = style  # "primary" (синяя) | "success" (зелёная) | "danger"
    return InlineKeyboardButton(text=text, callback_data=cb, url=url, **extra)


def kb(*rows) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[list(r) for r in rows])


def reply_kb() -> ReplyKeyboardMarkup:
    extra = {"style": "primary"} if config.USE_BUTTON_STYLE else {}
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=f"{E['menu'][1]} Меню", **extra),
                   KeyboardButton(text=f"{E['play'][1]} Играть", **extra),
                   KeyboardButton(text=f"{E['balance'][1]} Баланс", **extra)]],
        resize_keyboard=True, is_persistent=True,
    )


BACK_MENU = kb([B("Меню", "menu", key="menu")])


def main_kb():
    return kb(
        [B("Играть", "games", key="play", style="success")],
        [B("Пополнить", "deposit", key="deposit", style="primary"),
         B("Вывести", "withdraw", key="withdraw", style="primary")],
        [B("Профиль", "profile", key="profile"), B("Кэшбек", "cashback", key="cashback")],
        [B("Статистика", "stats", key="stats")],
    )


def games_kb(private: bool = True):
    rows, row = [], []
    for g in games.GAME_ORDER:
        icon, name = games.GAME_TITLES[g]
        eid = GAME_EMOJI_ID.get(g) if config.USE_BUTTON_ICONS else None
        btn = InlineKeyboardButton(text=f"{icon} {name}", callback_data=f"g:{g}")
        if eid:
            btn = B(f"{icon} {name}", f"g:{g}")
            btn.icon_custom_emoji_id = eid
        row.append(btn)
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    if private:
        rows.append([B("Меню", "menu", key="menu")])
    return kb(*rows)


def picks_kb(game: str):
    fallback = games.GAME_TITLES[game][0]
    rows = []
    for prow in games.PICKS[game]:
        rows.append([B(f"{PICK_EMOJI.get(code, fallback)} {label} · {games.mult_text(m)}",
                       f"p:{game}:{code}")
                     for label, code, m in prow])
    rows.append([B("Назад", "games", key="back")])
    return kb(*rows)


def bet_kb(game: str):
    presets = [0.1, 0.5, 1, 5, 10]
    return kb([B(f"{p:g} $", f"a:{p}", key="money") for p in presets],
              [B("Назад", f"g:{game}", key="back")])


def wallet_kb():
    return kb(
        [B("Пополнить", "deposit", key="deposit", style="primary"),
         B("Вывести", "withdraw", key="withdraw", style="primary")],
        [B("Операции", "ops", key="ops")],
        [B("Назад", "menu", key="back")],
    )


def deposit_text() -> str:
    return (f"{head('deposit', 'Пополнение')}\n\n"
            f"{em('money')} Минимум — {config.MIN_DEPOSIT:.2f} $\n\n"
            f"Выберите способ оплаты 👇")


def deposit_kb():
    return kb([B("xRocket", "dep_xr", key="xrocket")], [B("Назад", "menu", key="back")])


def withdraw_text(u) -> str:
    return (f"{head('withdraw', 'Вывод · xRocket')}\n\n"
            f"{em('balance')} Баланс — {usd(u['balance'])} $\n"
            f"{em('money')} Минимум — {config.MIN_WITHDRAW:.2f} $\n\n"
            f"Отправьте сумму 👇")


def withdraw_kb(u):
    return kb([B(f"Всё · {usd(u['balance'])} $", "wd_all", key="money", style="primary")],
              [B("Назад", "menu", key="back")])


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
            f"{em('balance')} Баланс — {usd(u['balance'])} $\n"
            f"{em('games')} Игр — {u['games']} · "
            f"{em('win')} Выиграно — {usd(u['won'])} $")


def games_text(u) -> str:
    return (f"{head('games', 'Игры')}\n\n"
            f"{em('balance')} Баланс — {usd(u['balance'])} $\n\n"
            f"Выбирай режим 👇")


def wallet_text(u) -> str:
    return (f"{head('balance', 'Кошелёк')}\n\n"
            f"{em('money')} Баланс — {usd(u['balance'])} $\n"
            f"{em('cashback')} Кэшбек — {usd(u['cashback'])} $")


def profile_text(u) -> str:
    wr = round(u["wins"] / u["games"] * 100) if u["games"] else 0
    joined = datetime.fromtimestamp(u["joined_at"], TZ).strftime("%d.%m.%Y")
    stats = quote(f"{em('games')} Игр — {u['games']} · винрейт {wr}%\n"
                  f"{em('stats')} Оборот — {usd(u['wagered'])} $\n"
                  f"{em('history')} С нами с {joined}")
    return (f"{head('profile', 'Профиль')}\n\n{name_of(u)}\n"
            f"{em('balance')} Баланс — {usd(u['balance'])} $\n\n{stats}")


def profile_kb():
    rows = [[B("История", "history", key="history"), B("Операции", "ops", key="ops")]]
    # SUPPORT_LINK по умолчанию "none" — такую «ссылку» Telegram не примет,
    # поэтому кнопка появляется только для настоящего адреса.
    if config.SUPPORT_LINK.startswith("http"):
        rows.append([B("Поддержка", url=config.SUPPORT_LINK)])
    rows.append([B("Назад", "menu", key="back")])
    return kb(*rows)


def history_text(rows) -> str:
    if not rows:
        return f"{head('history', 'История игр')}\n\n{em('alert')} Пока нет игр."
    lines = []
    for r in rows:
        icon, title = games.GAME_TITLES[r["game"]]
        if r["outcome"] == "win":
            res = f"{em('win')} +{usd(r['payout'])} $"
        elif r["outcome"] == "push":
            res = f"{em('push')} возврат"
        else:
            res = f"{em('lose')} -{usd(r['bet'])} $"
        lines.append(f"{fmt_ts(r['ts'])} · {icon} {title} · {usd(r['bet'])} $ → {res}")
    return f"{head('history', 'История игр')}\n\n" + quote("\n".join(lines))


def ops_text(rows) -> str:
    if not rows:
        return f"{head('ops', 'Операции')}\n\n{em('alert')} Пока нет операций."
    lines = []
    for r in rows:
        icon, title = KIND.get(r["kind"], ("•", r["kind"]))
        lines.append(f"{fmt_ts(r['ts'])} · {icon} {title} · {signed(r['amount'])}")
    return f"{head('ops', 'Операции')}\n\n" + quote("\n".join(lines))


def cashback_text(u) -> str:
    return (f"{head('cashback', 'Кэшбек')}\n\n"
            f"{em('money')} Накоплено — {usd(u['cashback'])} $\n\n"
            + quote(f"Возвращаем {config.CASHBACK_PERCENT}% с каждого проигрыша. "
                    f"Вывод на баланс от {config.MIN_CASHBACK_CLAIM:g} $"))


def cashback_kb():
    return kb([B("Забрать на баланс", "cb_claim", key="deposit", style="success")],
              [B("Назад", "menu", key="back")])


def top_text(title: str, rows) -> str:
    if not rows:
        return f"{head('win', title)}\n\n{em('alert')} Пока нет данных."
    lines = []
    for i, r in enumerate(rows):
        mark = MEDALS[i] if i < 3 else f"{i + 1}."
        lines.append(f"{mark} {escape(r['name'] or '—')} — {usd(r['turnover'])} $")
    return f"{head('win', title)}\n\n" + "\n".join(lines)


# ── казна ────────────────────────────────────────────────────────────────
def treasury_text(t: dict, tokens: float | None, assets: list[tuple[str, float]]) -> str:
    """Казна = баланс казино в токенах на xRocket. tokens=None — API не ответил."""
    lines = [head("treasury", "Казна · SERP CASINO"), ""]
    if tokens is None:
        lines.append(f"{em('alert')} <b>Токены недоступны</b> — xRocket не ответил.")
        lines.append(f"{em('money')} По учёту: пополнено {usd(t['deposits'])} $ − "
                     f"выведено {usd(t['withdraws'])} $ = "
                     f"<b>{usd(t['deposits'] - t['withdraws'])} $</b>")
    else:
        lines.append(f"{em('money')} <b>Касса (токены) — {tokens:.2f} USDT</b>")
        others = [(a, v) for a, v in assets if a != "USDT" and v > 0]
        if others:
            lines.append("Ещё на счету — " + ", ".join(f"{a}: {v:g}" for a, v in others))
    lines += [
        "",
        f"{em('profile')} Игроков — <b>{t['users']}</b> (с балансом: {t['players']})",
        f"{em('balance')} На балансах игроков — <b>{usd(t['balances'])} $</b>",
        f"{em('cashback')} Кэшбек накоплен — {usd(t['cashback'])} $",
        "",
        f"{em('deposit')} Пополнено — {usd(t['deposits'])} $",
        f"{em('withdraw')} Выведено — {usd(t['withdraws'])} $",
        f"{em('bet')} Ставок сделано — {usd(t['bets'])} $",
        f"{em('win')} Выплачено выигрышей — {usd(t['wins'])} $",
        f"{em('games')} Игр сыграно — {t['games']}",
    ]
    if tokens is not None:
        free = tokens - (t["balances"] + t["cashback"]) / M
        lines += ["", quote(f"{em('treasury')} Свободно в казне — <b>{free:.2f} $</b> "
                            f"= токены − балансы игроков − кэшбек")]
    return "\n".join(lines)
