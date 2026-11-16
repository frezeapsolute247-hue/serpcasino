"""Игры SERP CASINO.

Коэффициенты и условия выигрыша взяты из старого скрипта (C = COEFFICIENT = 1.8).
Кубики, слоты, дартс, дуэль броски делает сам Telegram (send_dice), но перевес
казино задаётся в config.py:
  PLAYER_LOSE_BOOST — выигрышный для игрока бросок может быть переброшен
                      (прошлое сообщение с кубиком удаляется, игрок видит один итог);
  KNB_BOT_WIN      — как часто бот ставит фигуру, которая бьёт выбор игрока;
  COIN_WIN_CHANCE  — шанс игрока в монетке.
RIG_ENABLED = False возвращает честную игру.
"""
import asyncio
import random
from dataclasses import dataclass

import config

_rng = random.SystemRandom()

C = 1.8  # базовый коэффициент (раньше COEFFICIENT в config.py)

GAME_ORDER = ["dice", "dice2", "duel", "coin", "slots",
              "darts", "football", "basket", "bowling", "knb"]

GAME_TITLES = {
    "dice": ("🎲", "Кубик · 1 бросок"),
    "dice2": ("🎲", "Кубик · 2 броска"),
    "duel": ("⚔️", "Дуэль"),
    "coin": ("🪙", "Монетка"),
    "slots": ("🎰", "Слоты"),
    "darts": ("🎯", "Дартс"),
    "football": ("⚽", "Футбол"),
    "basket": ("🏀", "Баскетбол"),
    "bowling": ("🎳", "Боулинг"),
    "knb": ("✊", "КНБ"),
}

# Строки кнопок выбора исхода: (подпись, код, коэффициент). None = особая выплата (слоты).
PICKS = {
    "dice": [
        [("1", "n1", 5), ("2", "n2", 5), ("3", "n3", 5)],
        [("4", "n4", 5), ("5", "n5", 5), ("6", "n6", 5)],
        [("Меньше", "less", C), ("Больше", "more", C)],
        [("Чётное", "even", C), ("Нечётное", "odd", C)],
    ],
    # два броска: оба чёт или оба нечет
    "dice2": [
        [("Оба чёт", "2even", 2.8), ("Оба нечет", "2odd", 2.8)],
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
        [("Центр", "center", 3), ("Отскок", "bounce", 3)],
        [("Красный", "red", C), ("Белый", "white", C)],
    ],
    "football": [
        [("Гол в центр", "goal_c", 3.5), ("Гол в угол", "goal_a", 3.5)],
        [("Промах", "miss", C)],
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


# старые кнопки из истории (футбольный «Гол» убран из PICKS)
LEGACY = {("football", "goal"): ("Гол", 1.5)}


def pick_info(game: str, code: str):
    if (game, code) in LEGACY:
        return LEGACY[(game, code)]
    for row in PICKS[game]:
        for label, c, mult in row:
            if c == code:
                return label, mult
    return code, None


def pick_label(game: str, code: str, number: int | None = None) -> str:
    label, _ = pick_info(game, code)
    if code == "num" and number is not None:
        return f"Число {number}"
    if code == "goal":
        return "Гол"
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


async def play(bot, chat_id: int, game: str, pick: str, number: int | None = None) -> Round:
    _, mult = pick_info(game, pick)

    if game == "dice":
        wins = _dice_wins(pick)
        v = (await _roll(bot, chat_id, "🎲", wins))[0]
        return _win(wins([v]), mult, f"Выпало {v}")

    if game == "dice2":
        # два броска: оба чёт или оба нечет
        wins = _duel_wins(pick)
        v1, v2 = await _roll(bot, chat_id, "🎲", wins, count=2)
        return _win(wins([v1, v2]), mult, f"Выпало {v1} и {v2}")

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
            # 6 — центр, 1 — дротик пролетел мимо мишени (отскок)
            return {"center": v == 6, "bounce": v == 1,
                    "red": v % 2 == 0, "white": v % 2 == 1}[pick]
        v = (await _roll(bot, chat_id, "🎯", wins))[0]
        return _win(wins([v]), mult, f"Выпало {v}")

    if game == "football":
        def wins(vals):
            # у Telegram в футболе значения 1-5: 4 и 5 — гол, 1-3 — мимо
            v = vals[0]
            return {"goal_c": v == 4, "goal_a": v == 5,
                    "miss": v in (1, 2, 3), "goal": v in (4, 5)}[pick]
        v = (await _roll(bot, chat_id, "⚽", wins))[0]
        return _win(wins([v]), mult, f"Выпало {v}")

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
