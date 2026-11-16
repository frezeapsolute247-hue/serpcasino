"""SERP CASINO: Telegram-бот (aiogram 3). Запуск: python main.py"""
import asyncio
import logging
import time
from decimal import Decimal, InvalidOperation, ROUND_DOWN

from aiogram import BaseMiddleware, Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ChatType, ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart, Filter, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

import config
import games
import ui
import xrocket
from db import Database, M, micro, usd
from ui import B, ce, head, kb, quote
from flask import Flask
from threading import Thread

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive!"

def run_web():
    app.run(host='0.0.0.0', port=8080)
log = logging.getLogger("serp")
db = Database(config.DB_PATH)
router = Router()

ACTIVE: set[int] = set()        # игроки, у которых сейчас идёт раунд
LAST: dict[int, dict] = {}      # последняя ставка игрока (кнопка «Ещё раз»)
BOT_LINK = ""                   # @username бота, заполняется при старте


class Deposit(StatesGroup):
    amount = State()


class Withdraw(StatesGroup):
    amount = State()


class Bet(StatesGroup):
    number = State()
    amount = State()


# ── вспомогательное ──────────────────────────────────────────────────────
class Touch(BaseMiddleware):
    """Запоминает/обновляет игрока при любом действии."""

    async def __call__(self, handler, event, data):
        u = data.get("event_from_user")
        if u and not u.is_bot:
            await db.upsert_user(u.id, u.first_name, u.username)
        return await handler(event, data)


def parse_amount(text: str) -> int | None:
    t = text.strip().replace(",", ".").replace("$", "").strip()
    try:
        d = Decimal(t)
    except InvalidOperation:
        return None
    if not d.is_finite() or d <= 0:
        return None
    d = d.quantize(Decimal("0.01"), rounding=ROUND_DOWN)
    return int(d * M) if d > 0 else None


def is_private(chat) -> bool:
    return chat.type == ChatType.PRIVATE


async def show(target, text: str, markup):
    """Обновляет сообщение с кнопками: и в личке, и в чате. Если нельзя — шлёт новое."""
    if isinstance(target, CallbackQuery):
        msg = target.message
        try:
            await msg.edit_text(text, reply_markup=markup)
            return
        except TelegramBadRequest as e:
            if "not modified" in str(e):
                return
        await msg.answer(text, reply_markup=markup)
    else:
        await target.answer(text, reply_markup=markup)


def dm_link(payload: str = "") -> str:
    """Ссылка в личку с ботом — чтобы из чата прыгнуть сразу на нужный экран."""
    base = f"https://t.me/{BOT_LINK}" if BOT_LINK else "https://t.me"
    return f"{base}?start={payload}" if payload else base


async def private_only(cb: CallbackQuery, title: str, payload: str = "") -> bool:
    """Деньги — только в личке; в чате показываем кнопку перехода в бота."""
    if is_private(cb.message.chat):
        return True
    await cb.answer()
    await cb.message.answer(
        f"{head('🔒', title)}\n\nОткрой бота в личных сообщениях — там пополнение и вывод.",
        reply_markup=kb([B("Открыть бота", url=dm_link(payload), style="primary")]))
    return False


async def send_menu(target):
    uid = target.from_user.id
    await show(target, ui.menu_text(await db.get_user(uid)), ui.main_kb())


async def send_games(target):
    uid = target.from_user.id
    chat = target.message.chat if isinstance(target, CallbackQuery) else target.chat
    await show(target, ui.games_text(await db.get_user(uid)), ui.games_kb(is_private(chat)))


# ── /start, /play и нижние кнопки ────────────────────────────────────────
@router.message(CommandStart())
async def cmd_start(m: Message, state: FSMContext):
    await state.clear()
    payload = (m.text or "").partition(" ")[2].strip().lower()
    if not is_private(m.chat):
        await m.answer("🎰 SERP CASINO\nИграть: /play\nКазна: /казна")
        return
    await m.answer("👋 Добро пожаловать в SERP CASINO!", reply_markup=ui.reply_kb())
    action = text_action(payload) if payload else None
    if action in ("deposit", "withdraw", "games", "balance", "cashback", "stats"):
        await run_action(m, action, state)
        return
    await send_menu(m)


@router.message(Command("play"))
async def cmd_play(m: Message, state: FSMContext):
    await state.clear()
    await send_games(m)


def is_admin(uid: int) -> bool:
    return not config.ADMIN_IDS or uid in config.ADMIN_IDS


async def treasury_allowed(m: Message) -> bool:
    """Личка — можно (если ADMIN_IDS пуст), в чате — только админам чата."""
    if config.ADMIN_IDS:
        return m.from_user.id in config.ADMIN_IDS
    if is_private(m.chat):
        return True
    try:
        member = await m.bot.get_chat_member(m.chat.id, m.from_user.id)
        return member.status in ("creator", "administrator")
    except Exception:
        return False


@router.message(Command("казна", "касса", "kassa", "treasury"))
async def cmd_treasury(m: Message):
    """Казна = деньги всего казино: реальный баланс приложения в xRocket."""
    if not await treasury_allowed(m):
        await m.answer(f"{ui.ic('lock')} Казна — только для владельца казино "
                       f"и админов чата.")
        return
    t = await db.treasury()
    xr = {"total": 0.0, "assets": [], "error": None}
    try:
        total, assets = await xrocket.app_balance_usd()
        xr["total"], xr["assets"] = total, assets
    except Exception as e:
        log.warning("app_balance_usd failed", exc_info=True)
        xr["error"] = str(e)[:160]
    await m.answer(ui.treasury_text(t, xr),
                   reply_markup=ui.BACK_MENU if is_private(m.chat) else None)


# ── текстовые команды: и в личке, и в чатах, без учёта регистра ──────────
TEXT_ACTIONS = {
    "меню": "menu", "menu": "menu", "старт": "menu", "start": "menu",
    "играть": "games", "игры": "games", "игра": "games", "games": "games",
    "play": "games", "казино": "games",
    "профиль": "profile", "profile": "profile", "проф": "profile",
    "баланс": "balance", "балансы": "balance", "кошелек": "balance",
    "кошелёк": "balance", "wallet": "balance", "деньги": "balance",
    "деп": "deposit", "депозит": "deposit", "пополнить": "deposit",
    "пополнение": "deposit", "deposit": "deposit",
    "вывод": "withdraw", "вывести": "withdraw", "выведи": "withdraw",
    "снять": "withdraw", "withdraw": "withdraw",
    "кэшбек": "cashback", "кэшбэк": "cashback", "cashback": "cashback",
    "статистика": "stats", "топ": "stats", "stats": "stats",
    "история": "history", "history": "history",
    "операции": "ops", "ops": "ops",
    "казна": "treasury", "касса": "treasury", "кассы": "treasury",
    "kassa": "treasury", "treasury": "treasury",
}


def text_action(text: str | None) -> str | None:
    if not text:
        return None
    key = text.strip().lower().lstrip("/!").split("@")[0].strip().strip(" .!?,")
    return TEXT_ACTIONS.get(key)


class Nav(Filter):
    """Ловит только слова-команды, чтобы не перехватывать суммы ставок."""

    async def __call__(self, message: Message) -> bool:
        return text_action(message.text) is not None


async def run_action(source: Message, action: str, state: FSMContext | None = None):
    """Один и тот же экран по кнопке и по слову, в личке и в чате."""
    if state is not None:
        await state.clear()
    uid = source.from_user.id
    private = is_private(source.chat)
    if action == "menu":
        await send_menu(source)
    elif action == "games":
        await send_games(source)
    elif action == "balance":
        await source.answer(ui.wallet_text(await db.get_user(uid)), reply_markup=ui.wallet_kb())
    elif action == "profile":
        await source.answer(ui.profile_text(await db.get_user(uid)), reply_markup=ui.profile_kb())
    elif action == "history":
        await source.answer(ui.history_text(await db.recent_games(uid, 10)),
                            reply_markup=kb([B("Назад", "profile")]))
    elif action == "ops":
        await source.answer(ui.ops_text(await db.recent_ops(uid, 12)),
                            reply_markup=kb([B("Назад", "profile")]))
    elif action == "cashback":
        await source.answer(ui.cashback_text(await db.get_user(uid)), reply_markup=ui.cashback_kb())
    elif action == "stats":
        await source.answer(head(ce(ui.E_WIN, "🏆"), "Выберите категорию топа"), reply_markup=kb(
            [B("Топ игроков", "top_p", style="primary"), B("Топ чатов", "top_c", style="primary")],
            [B("Назад", "menu")]))
    elif action == "deposit":
        if private:
            await source.answer(ui.deposit_text(), reply_markup=ui.deposit_kb())
        else:
            await source.answer(
                f"{head(ui.ic('deposit'), 'Пополнение')}\n\nПополнение — в личке с ботом.",
                reply_markup=kb([B("Открыть бота", url=dm_link("deposit"), style="primary")]))
    elif action == "withdraw":
        u = await db.get_user(uid)
        if private:
            if state is not None:
                await state.set_state(Withdraw.amount)
            await source.answer(ui.withdraw_text(u), reply_markup=ui.withdraw_kb(u))
        else:
            await source.answer(
                f"{head('💸', 'Вывод')}\n\nВывод — в личке с ботом.",
                reply_markup=kb([B("Открыть бота", url=dm_link("withdraw"), style="primary")]))
    elif action == "treasury":
        await cmd_treasury(source)


@router.message(Nav(), StateFilter("*"))
async def nav_text(m: Message, state: FSMContext):
    await run_action(m, text_action(m.text), state)


# ── главное меню / кошелёк / профиль ─────────────────────────────────────
@router.callback_query(F.data == "menu")
async def cb_menu(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.answer()
    await send_menu(cb)


@router.callback_query(F.data == "wallet")
async def cb_wallet(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.answer()
    await show(cb, ui.wallet_text(await db.get_user(cb.from_user.id)), ui.wallet_kb())


@router.callback_query(F.data == "profile")
async def cb_profile(cb: CallbackQuery):
    await cb.answer()
    await show(cb, ui.profile_text(await db.get_user(cb.from_user.id)), ui.profile_kb())


@router.callback_query(F.data == "history")
async def cb_history(cb: CallbackQuery):
    await cb.answer()
    rows = await db.recent_games(cb.from_user.id, 10)
    await show(cb, ui.history_text(rows), kb([B("Назад", "profile")]))


@router.callback_query(F.data == "ops")
async def cb_ops(cb: CallbackQuery):
    await cb.answer()
    rows = await db.recent_ops(cb.from_user.id, 12)
    await show(cb, ui.ops_text(rows), kb([B("Назад", "profile")]))


# ── кэшбек ───────────────────────────────────────────────────────────────
@router.callback_query(F.data == "cashback")
async def cb_cashback(cb: CallbackQuery):
    await cb.answer()
    await show(cb, ui.cashback_text(await db.get_user(cb.from_user.id)), ui.cashback_kb())


@router.callback_query(F.data == "cb_claim")
async def cb_claim(cb: CallbackQuery):
    got = await db.claim_cashback(cb.from_user.id, micro(config.MIN_CASHBACK_CLAIM))
    if not got:
        # Заголовок окна = имя бота. Чтобы было «SERP CASINO», переименуй бота в @BotFather (/setname).
        await cb.answer(f"Минимум {config.MIN_CASHBACK_CLAIM:g} $", show_alert=True)
        return
    await cb.answer(f"Зачислено {usd(got)} $", show_alert=True)
    await show(cb, ui.cashback_text(await db.get_user(cb.from_user.id)), ui.cashback_kb())


# ── статистика ───────────────────────────────────────────────────────────
@router.callback_query(F.data == "stats")
async def cb_stats(cb: CallbackQuery):
    await cb.answer()
    await show(cb, head(ce(ui.E_WIN, "🏆"), "Выберите категорию топа"), kb(
        [B("Топ игроков", "top_p", style="primary"), B("Топ чатов", "top_c", style="primary")],
        [B("Назад", "menu")],
    ))


@router.callback_query(F.data == "top_p")
async def cb_top_players(cb: CallbackQuery):
    await cb.answer()
    rows = await db.top_players(int(time.time()) - 7 * 86400)
    await show(cb, ui.top_text("Топ игроков недели · оборот", rows), kb([B("К категориям", "stats")]))


@router.callback_query(F.data == "top_c")
async def cb_top_chats(cb: CallbackQuery):
    await cb.answer()
    rows = await db.top_chats(int(time.time()) - 7 * 86400)
    await show(cb, ui.top_text("Топ чатов недели · оборот", rows), kb([B("К категориям", "stats")]))


# ── пополнение (xRocket) ─────────────────────────────────────────────────
@router.callback_query(F.data == "deposit")
async def cb_deposit(cb: CallbackQuery, state: FSMContext):
    if not await private_only(cb, "Пополнение", "deposit"):
        return
    await state.clear()
    await cb.answer()
    await show(cb, ui.deposit_text(), ui.deposit_kb())


@router.callback_query(F.data == "dep_xr")
async def cb_dep_xrocket(cb: CallbackQuery, state: FSMContext):
    if not await private_only(cb, "Пополнение", "deposit"):
        return
    await state.set_state(Deposit.amount)
    await cb.answer()
    await show(cb, f"{head(ui.ic('deposit'), 'Пополнение · xRocket')}\n\n"
                   f"Минимум — {config.MIN_DEPOSIT:.2f} $\n\nОтправьте сумму в USDT 👇",
               kb([B("Назад", "deposit")]))


@router.message(Deposit.amount, F.text)
async def deposit_amount(m: Message, state: FSMContext):
    amt = parse_amount(m.text)
    if amt is None:
        await m.answer("Отправьте сумму числом, например 1.5")
        return
    if amt < micro(config.MIN_DEPOSIT):
        await m.answer(f"Минимальная сумма пополнения — {config.MIN_DEPOSIT:.2f} $")
        return
    try:
        invoice_id, link = await xrocket.create_invoice(amt / M, "SERP CASINO", str(m.from_user.id))
    except Exception:
        log.exception("xRocket create_invoice failed")
        await m.answer("Не удалось создать счёт, попробуйте позже.", reply_markup=ui.BACK_MENU)
        return
    await db.create_deposit(invoice_id, m.from_user.id, amt)
    await state.clear()
    text = (f"{head(ui.ic('deposit'), 'Счёт создан')}\n\nСумма — {usd(amt)} $\nСпособ — xRocket\n\n"
            + quote(f"Счёт действует {config.INVOICE_LIFETIME_MIN} мин. Баланс пополнится автоматически"))
    await m.answer(text, reply_markup=kb(
        [B(f"Оплатить · {amt / M:g} $", url=link, icon=ui.I_DEPOSIT, style="success")],
        [B("Меню", "menu")],
    ))


# ── вывод (xRocket) ──────────────────────────────────────────────────────
@router.callback_query(F.data == "withdraw")
async def cb_withdraw(cb: CallbackQuery, state: FSMContext):
    if not await private_only(cb, "Вывод", "withdraw"):
        return
    await state.set_state(Withdraw.amount)
    await cb.answer()
    u = await db.get_user(cb.from_user.id)
    await show(cb, ui.withdraw_text(u), ui.withdraw_kb(u))


async def do_withdraw(msg: Message, uid: int, amount: int, state: FSMContext):
    back = kb([B("Назад", "menu")])
    if amount < micro(config.MIN_WITHDRAW):
        await msg.answer(f"Минимальная сумма вывода — {config.MIN_WITHDRAW:.2f} $", reply_markup=back)
        return
    # Сначала списываем с баланса, потом создаём чек; при ошибке возвращаем деньги.
    if not await db.debit_withdraw(uid, amount):
        await msg.answer("Недостаточно средств на балансе", reply_markup=back)
        return
    try:
        link = await xrocket.create_cheque(uid, amount / M, "SERP CASINO · вывод")
    except Exception:
        log.exception("xRocket create_cheque failed")
        await db.refund_withdraw(uid, amount)
        await msg.answer("Не удалось создать чек, средства возвращены на баланс.", reply_markup=back)
        return
    await state.clear()
    await msg.answer(f"{head('💸', 'Вывод · xRocket')}\n\nСумма — {usd(amount)} $\n\n"
                     + quote("Чек создан. Заберите его по кнопке ниже"),
                     reply_markup=kb([B("Забрать чек", url=link, icon=ui.I_WITHDRAW, style="success")],
                                     [B("Меню", "menu")]))


@router.message(Withdraw.amount, F.text)
async def withdraw_amount(m: Message, state: FSMContext):
    amt = parse_amount(m.text)
    if amt is None:
        await m.answer("Отправьте сумму числом, например 1.5")
        return
    await do_withdraw(m, m.from_user.id, amt, state)


@router.callback_query(Withdraw.amount, F.data == "wd_all")
async def withdraw_all(cb: CallbackQuery, state: FSMContext):
    if not await private_only(cb, "Вывод", "withdraw"):
        return
    await cb.answer()
    u = await db.get_user(cb.from_user.id)
    await do_withdraw(cb.message, cb.from_user.id, u["balance"], state)


# ── игры ─────────────────────────────────────────────────────────────────
@router.callback_query(F.data == "games")
async def cb_games(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.answer()
    await send_games(cb)


@router.callback_query(F.data.startswith("g:"))
async def cb_game(cb: CallbackQuery, state: FSMContext):
    game = cb.data[2:]
    if game not in games.GAME_TITLES:
        await cb.answer()
        return
    await state.clear()
    await cb.answer()
    icon, name = games.GAME_TITLES[game]
    u = await db.get_user(cb.from_user.id)
    await show(cb, f"{quote(f'{icon} {name}')}\n\nБаланс — {usd(u['balance'])} $\n"
                   f"Ставка — от {config.MIN_BET:.2f} до {config.MAX_BET:g} $\n\nВыбери исход 👇",
               ui.picks_kb(game))


def ask_amount_text(game: str, code: str, number, balance: int, private: bool) -> str:
    icon, name = games.GAME_TITLES[game]
    _, mult = games.pick_info(game, code)
    label = games.pick_label(game, code, number)
    text = (f"{quote(f'{icon} {name} · {label} · {games.mult_text(mult)}')}\n\n"
            f"Баланс — {usd(balance)} $\n"
            f"Ставка — от {config.MIN_BET:.2f} до {config.MAX_BET:g} $\n\n"
            f"Отправьте сумму ставки или выберите 👇")
    if not private:
        text += "\n<i>В группе отправьте сумму ответом на это сообщение.</i>"
    return text


@router.callback_query(F.data.startswith("p:"))
async def cb_pick(cb: CallbackQuery, state: FSMContext):
    parts = cb.data.split(":")
    if len(parts) != 3 or parts[1] not in games.PICKS:
        await cb.answer()
        return
    _, game, code = parts
    if not any(code == c for row in games.PICKS[game] for _, c, _ in row):
        await cb.answer()
        return
    await cb.answer()
    if code == "num":
        await state.set_state(Bet.number)
        await state.update_data(game=game, pick=code, number=None)
        await show(cb, f"{quote('🎡 Рулетка · Число')}\n\nОтправьте число от 0 до 36 👇",
                   kb([B("Назад", f"g:{game}")]))
        return
    await state.set_state(Bet.amount)
    await state.update_data(game=game, pick=code, number=None)
    u = await db.get_user(cb.from_user.id)
    await show(cb, ask_amount_text(game, code, None, u["balance"], is_private(cb.message.chat)),
               ui.bet_kb(game))


@router.message(Bet.number, F.text)
async def bet_number(m: Message, state: FSMContext):
    try:
        n = int(m.text.strip())
    except ValueError:
        n = -1
    if not 0 <= n <= 36:
        await m.answer("Отправьте целое число от 0 до 36")
        return
    await state.update_data(number=n)
    await state.set_state(Bet.amount)
    data = await state.get_data()
    u = await db.get_user(m.from_user.id)
    await m.answer(ask_amount_text(data["game"], data["pick"], n, u["balance"], is_private(m.chat)),
                   reply_markup=ui.bet_kb(data["game"]))


@router.message(Bet.amount, F.text)
async def bet_amount(m: Message, state: FSMContext):
    amt = parse_amount(m.text)
    if amt is None:
        await m.answer("Отправьте сумму числом, например 0.5")
        return
    await run_round(m, m.from_user.id, await state.get_data(), amt, state)


@router.callback_query(Bet.amount, F.data.startswith("a:"))
async def bet_preset(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await run_round(cb.message, cb.from_user.id, await state.get_data(), micro(cb.data[2:]), state)


@router.callback_query(F.data == "r")
async def cb_repeat(cb: CallbackQuery, state: FSMContext):
    last = LAST.get(cb.from_user.id)
    if not last:
        await cb.answer("Нет прошлой ставки", show_alert=True)
        return
    await cb.answer()
    await run_round(cb.message, cb.from_user.id, last["data"], last["amount"], state)


async def run_round(msg: Message, uid: int, data: dict, amount: int, state: FSMContext):
    game, pick, number = data.get("game"), data.get("pick"), data.get("number")
    if not game:
        await msg.answer("Выберите игру: /play")
        return
    if amount < micro(config.MIN_BET) or amount > micro(config.MAX_BET):
        await msg.answer(f"Ставка от {config.MIN_BET:.2f} до {config.MAX_BET:g} $")
        return
    if uid in ACTIVE:
        await msg.answer("Дождитесь окончания текущей игры")
        return
    ACTIVE.add(uid)
    try:
        private = is_private(msg.chat)
        if not await db.debit_bet(uid, amount):
            rows = [[B("Игры", "games")]]
            if private:
                rows.insert(0, [B("Пополнить", "deposit", icon=ui.I_DEPOSIT, style="primary")])
            await msg.answer("Недостаточно средств на балансе", reply_markup=kb(*rows))
            return
        if not private:
            await db.upsert_chat(msg.chat.id, msg.chat.title or "—")
        try:
            rnd = await games.play(msg.bot, msg.chat.id, game, pick, number)
        except Exception:
            log.exception("round failed")
            await db.refund_bet(uid, amount)
            await msg.answer("Не удалось провести игру, ставка возвращена.")
            return

        payout = {"win": int(round(amount * rnd.mult)), "push": amount}.get(rnd.outcome, 0)
        balance = await db.settle(uid, None if private else msg.chat.id,
                                  game, pick, amount, payout, rnd.outcome)
        LAST[uid] = {"data": {"game": game, "pick": pick, "number": number}, "amount": amount}
        await state.clear()

        icon, name = games.GAME_TITLES[game]
        label = games.pick_label(game, pick, number)
        top = quote(f"{icon} {name} · {label} · {usd(amount)} $")
        if rnd.outcome == "win":
            body = (f"{ce(ui.E_WIN, '🏆')} <b>Победа!</b> {rnd.detail}\n"
                    f"Выплата — {usd(payout)} $ (×{rnd.mult:g})")
        elif rnd.outcome == "push":
            body = f"↩️ <b>Ничья.</b> {rnd.detail}\nСтавка возвращена"
        else:
            body = f"❌ <b>Проигрыш.</b> {rnd.detail}"
        rows = [[B(f"Ещё раз · {usd(amount)} $", "r", style="success")],
                [B("Игры", "games")] + ([B("Меню", "menu")] if private else [])]
        await msg.answer(f"{top}\n\n{body}\n\nБаланс — {usd(balance)} $", reply_markup=kb(*rows))
    finally:
        ACTIVE.discard(uid)


# ── автозачисление пополнений ────────────────────────────────────────────
async def deposits_watcher(bot: Bot):
    """Каждые 10 секунд проверяет неоплаченные счета и зачисляет оплаченные."""
    while True:
        try:
            for dep in await db.pending_deposits():
                try:
                    status = await xrocket.invoice_status(dep["invoice_id"])
                except Exception as e:
                    log.warning("invoice_status %s: %s", dep["invoice_id"], e)
                    status = None
                if status == "paid":
                    res = await db.credit_deposit(dep["invoice_id"])
                    if res:
                        uid, amt = res
                        try:
                            await bot.send_message(
                                uid, f"{head(ui.ic('deposit'), 'Пополнение')}\n\nБаланс пополнен на {usd(amt)} $ ✅",
                                reply_markup=kb([B("Играть", "games", icon=ui.I_PLAY, style="success")]))
                        except Exception:
                            pass
                elif status == "expired" or time.time() - dep["created"] > (config.INVOICE_LIFETIME_MIN + 5) * 60:
                    await db.expire_deposit(dep["invoice_id"])
        except Exception:
            log.exception("deposits watcher")
        await asyncio.sleep(10)


async def main():
    Thread(target=run_web).start()
    logging.basicConfig(level=logging.INFO)
    await db.init()
    global BOT_LINK
    bot = Bot(config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    me = await bot.me()
    BOT_LINK = me.username or ""
    dp = Dispatcher()
    dp.update.outer_middleware(Touch())
    dp.include_router(router)
    watcher = asyncio.create_task(deposits_watcher(bot))
    try:
        await dp.start_polling(bot)
    finally:
        watcher.cancel()
        await db.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
