"""Игры SERP CASINO.

Коэффициенты и условия выигрыша взяты из старого скрипта (C = COEFFICIENT = 1.8).
Кубики, слоты, дартс, дуэль броски делает сам Telegram (send_dice), но перевес
казино задаётся в config.py:
  PLAYER_LOSE_BOOST — выигрышный для игрока бросок может быть переброшен
                      (прошлое сообщение с кубиком удаляется, игрок видит один итог);
  KNB_BOT_WIN      — как часто бот ставит фигуру, которая бьёт выбор игрока;
  COIN_WIN_CHANCE  — шанс игрока в монетке.
RIG_ENABLED = False возвращает честную игру.

Значения кубиков Telegram (на них держится вся математика ниже):
  🎲 1-6;
  🎯 1-6: 6 — центр мишени, 1 — край (= отскок), чётные — красный сектор, нечётные — белый;
  ⚽ 1-5: 1-2 — мимо, 3 — по центру ворот, 4-5 — в угол;
  🏀 1-5;  🎳 1-6, где 6 — страйк;
  🎰 1-64.
"""
import asyncio
import random
from dataclasses import dataclass

import config

_rng = random.SystemRandom()

C = 1.8  # базовый коэффициент (раньше COEFFICIENT в config.py)

GAME_ORDER = ["dice", "duel", "coin", "slots",
              "darts", "football", "basket", "bowling", "knb"]

GAME_TITLES = {
    "dice": ("🎲", "Кубик"),
    "duel": ("⚔️", "Дуэль"),
    "coin": ("🪙", "Монетка"),
    "slots": ("🎰", "Слоты"),
    "darts": ("🎯", "Дартс"),
    "football": ("⚽", "Футбол"),
    "basket": ("🏀", "Баскетбол"),
    "bowling": ("🎳", "Боулинг"),
    "knb": ("✊", "КНБ"),
}

# ── Значения кубиков ─────────────────────────────────────────────────────
DARTS_CENTER = 6          # 6 — в центр, x3
DARTS_BOUNCE = 1          # 1 — край, отскок, x3
FOOTBALL_GOAL = (3, 4, 5)
FOOTBALL_CENTER = 3       # 3 — по центру ворот, x3.5
FOOTBALL_CORNER = (4, 5)  # 4-5 — в угол, x3.5
FOOTBALL_MISS = (1, 2)

# Строки кнопок выбора исхода: (подпись, код, коэффициент). None = особая выплата (слоты).
PICKS = {
    "dice": [
        [("1", "n1", 5), ("2", "n2", 5), ("3", "n3", 5)],
        [("4", "n4", 5), ("5", "n5", 5), ("6", "n6", 5)],
        [("Меньше", "less", C), ("Больше", "more", C)],
        [("Чётное", "even", C), ("Нечётное", "odd", C)],
        [("2 броска · оба чёт", "2even", 2.8)],
        [("2 броска · оба нечёт", "2odd", 2.8)],
    ],
    "duel": [
        [("Победа 1", "p1", C), ("Победа 2", "p2", C)],
        [("Ничья", "draw", 3)],
        [("2 меньше", "2less", 2.6), ("2 больше", "2more", 2.6)],
        [("2 чётных", "2even", 2.6), ("2 нечётных", "2odd", 2.6)],
    ],
    "coin": [
        [("Орёл", "heads", C), ("Решка", "tails", C)],
    ],
    "slots": [
        [("Крутить", "spin", None)],
    ],
    "darts": [
        [("Центр", "center", 3)],
        [("Отскок", "bounce", 3)],
        [("Красный", "red", C), ("Белый", "white", C)],
    ],
    "football": [
        [("Гол", "goal", 1.5), ("Промах", "miss", C)],
        [("Гол в центр", "goal_c", 3.5)],
        [("Гол в угол", "goal_a", 3.5)],
    ],
    "basket": [
        [("Попал", "hit", C), ("Мимо", "miss", 1.5)],
    ],
    "bowling": [
        [("Страйк", "strike", 2)],
        [("1", "n1", 3), ("2", "n2", 3), ("3", "n3", 3)],
        [("4", "n4", 3), ("5", "n5", 3), ("6", "n6", 3)],
    ],
    "knb": [
        [("Камень", "rock", C), ("Ножницы", "scissors", C), ("Бумага", "paper", C)],
    ],
}

SLOTS_PAYOUT = {1: 7, 22: 7, 43: 7, 16: 5, 32: 5, 48: 5, 64: 10}
SLOTS_NAMES = {7: "Занос", 5: "Куш", 10: "Джекпот"}

DICE_DELAY = {"🎲": 3.5, "🎯": 3.5, "⚽": 4.0, "🏀": 4.5, "🎳": 4.0, "🎰": 2.5}

# Кто кого бьёт в КНБ: beats["rock"] == "scissors" (камень бьёт ножницы).
BEATS = {"rock": "scissors", "scissors": "paper", "paper": "rock"}
# Что поставить против выбора игрока: COUNTER["rock"] == "paper".
COUNTER = {"rock": "paper", "scissors": "rock", "paper": "scissors"}


@dataclass
class Round:
    outcome: str   # "win" | "lose" | "push"
    mult: float    # коэффициент выплаты (для win)
    detail: str    # что выпало


def pick_info(game: str, code: str):
    for row in PICKS[game]:
        for label, c, mult in row:
            if c == code:
                return label, mult
    return code, None


def pick_label(game: str, code: str, number: int | None = None) -> str:
    label, _ = pick_info(game, code)
    if code == "num" and number is not None:
        return f"Число {number}"
    if game in ("dice", "bowling") and code.startswith("n"):
        return f"Число {code[1:]}"
    return label


def mult_text(mult) -> str:
    return "до ×10" if mult is None else f"×{mult:g}"


async def _dice(bot, chat_id: int, emoji: str) -> int:
    msg = await bot.send_dice(chat_id, emoji=emoji)
    await asyncio.sleep(DICE_DELAY[emoji])
    return msg.dice.value


async def _roll(bot, chat_id: int, emoji: str, wins, count: int = 1) -> list[int]:
    """Бросок с перевесом казино.

    Если по правилам (wins) игрок выигрывает, с шансом PLAYER_LOSE_BOOST
    бросок перебрасывается: сообщение с прошлым кубиком удаляется, игрок
    видит только итоговый результат. Если удалить нельзя (бот не админ,
    сообщение уже старое) — результат остаётся как есть.
    """
    tries = config.REROLL_TRIES if config.RIG_ENABLED else 0
    vals: list[int] = []
    for attempt in range(tries + 1):
        msgs = []
        for _ in range(count):
            msgs.append(await bot.send_dice(chat_id, emoji=emoji))
        await asyncio.sleep(DICE_DELAY[emoji])
        vals = [m.dice.value for m in msgs]
        if attempt == tries:                       # последняя попытка — принимаем
            return vals
        if not wins(vals):                         # игрок и так проиграл
            return vals
        if _rng.random() >= config.PLAYER_LOSE_BOOST:
            return vals                            # перевес не сработал
        try:
            for m in msgs:
                await m.delete()
        except Exception:
            return vals                            # удалить нельзя — не подменяем
    return vals


def _win(cond: bool, mult: float, detail: str) -> Round:
    return Round("win" if cond else "lose", mult, detail)


def _dice_wins(pick: str):
    def wins(vals: list[int]) -> bool:
        x = vals[0]
        if pick.startswith("n"):
            return x == int(pick[1:])
        return {"less": x <= 3, "more": x >= 4,
                "even": x % 2 == 0, "odd": x % 2 == 1}[pick]
    return wins


def _dice2_wins(pick: str):
    """Кубик в два броска: оба чётных (2even) или оба нечётных (2odd)."""
    def wins(vals: list[int]) -> bool:
        a, b = vals[0], vals[1]
        if pick == "2even":
            return a % 2 == 0 and b % 2 == 0
        return a % 2 == 1 and b % 2 == 1
    return wins


def _duel_wins(pick: str):
    def wins(vals: list[int]) -> bool:
        v1, v2 = vals
        return {
            "p1": v1 > v2, "p2": v2 > v1, "draw": v1 == v2,
            "2less": v1 < 4 and v2 < 4, "2more": v1 > 3 and v2 > 3,
            "2even": v1 % 2 == 0 and v2 % 2 == 0,
            "2odd": v1 % 2 == 1 and v2 % 2 == 1,
        }[pick]
    return wins


def _darts_detail(v: int) -> str:
    if v == DARTS_CENTER:
        return "🎯 В центр!"
    if v == DARTS_BOUNCE:
        return "💨 Отскок от края"
    return f"Выпало {v} · {'красный' if v % 2 == 0 else 'белый'} сектор"


def _football_detail(v: int) -> str:
    if v == FOOTBALL_CENTER:
        return "⚽ Точно в центр ворот!"
    if v in FOOTBALL_CORNER:
        return "⚽ Гол в угол!"
    return f"Мимо · выпало {v}"


async def play(bot, chat_id: int, game: str, pick: str, number: int | None = None) -> Round:
    _, mult = pick_info(game, pick)

    if game == "dice":
        if pick in ("2even", "2odd"):
            wins = _dice2_wins(pick)
            v1, v2 = await _roll(bot, chat_id, "🎲", wins, count=2)
            return _win(wins([v1, v2]), mult, f"Выпало {v1} и {v2}")
        wins = _dice_wins(pick)
        v = (await _roll(bot, chat_id, "🎲", wins))[0]
        return _win(wins([v]), mult, f"Выпало {v}")

    if game == "duel":
        wins = _duel_wins(pick)
        v1, v2 = await _roll(bot, chat_id, "🎲", wins, count=2)
        return _win(wins([v1, v2]), mult, f"Счёт {v1}:{v2}")

    if game == "coin":
        chance = config.COIN_WIN_CHANCE if config.RIG_ENABLED else 0.5
        ok = _rng.random() < chance
        side = pick if ok else ("tails" if pick == "heads" else "heads")
        name = "орёл" if side == "heads" else "решка"
        return _win(ok, mult, f"Выпал {name}" if side == "heads" else f"Выпала {name}")

    if game == "slots":
        v = (await _roll(bot, chat_id, "🎰", lambda vals: vals[0] in SLOTS_PAYOUT))[0]
        m = SLOTS_PAYOUT.get(v)
        if m:
            return Round("win", m, f"{SLOTS_NAMES[m]}!")
        return Round("lose", 0, "Не повезло")

    if game == "darts":
        def wins(vals):
            v = vals[0]
            return {"center": v == DARTS_CENTER, "bounce": v == DARTS_BOUNCE,
                    "red": v % 2 == 0, "white": v % 2 == 1}[pick]
        v = (await _roll(bot, chat_id, "🎯", wins))[0]
        return _win(wins([v]), mult, _darts_detail(v))

    if game == "football":
        def wins(vals):
            v = vals[0]
            if pick == "goal_c":
                return v == FOOTBALL_CENTER
            if pick == "goal_a":
                return v in FOOTBALL_CORNER
            if pick == "goal":
                return v in FOOTBALL_GOAL
            return v in FOOTBALL_MISS          # pick == "miss"
        v = (await _roll(bot, chat_id, "⚽", wins))[0]
        return _win(wins([v]), mult, _football_detail(v))

    if game == "basket":
        def wins(vals):
            v = vals[0]
            return v in (4, 5) if pick == "hit" else v in (1, 2, 3)
        v = (await _roll(bot, chat_id, "🏀", wins))[0]
        return _win(wins([v]), mult, f"Выпало {v}")

    if game == "bowling":
        def wins(vals):
            v = vals[0]
            return v == 6 if pick == "strike" else v == int(pick[1:])
        v = (await _roll(bot, chat_id, "🎳", wins))[0]
        return _win(wins([v]), mult, f"Выпало {v}")

    if game == "knb":
        target = config.KNB_BOT_WIN if config.RIG_ENABLED else 1 / 3
        if _rng.random() < target:
            bot_pick = COUNTER[pick]          # бот бьёт выбор игрока
        else:
            bot_pick = _rng.choice([c for c in BEATS if c != COUNTER[pick]])
        icons = {"rock": "✊", "scissors": "✌️", "paper": "✋"}
        detail = f"Вы {icons[pick]} · бот {icons[bot_pick]}"
        if pick == bot_pick:
            return Round("push", 1, detail + " · ничья")
        return _win(BEATS[pick] == bot_pick, mult, detail)

    raise ValueError(f"unknown game {game}")
