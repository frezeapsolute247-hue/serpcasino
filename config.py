"""Настройки SERP CASINO. Токены вписываешь сам, в архив/чат их больше не кидай."""

# ── Токены ───────────────────────────────────────────────────────────────
import os

# Токен берётся из переменной окружения BOT_TOKEN (Render -> Environment), если она задана,
# иначе — из строки ниже.
BOT_TOKEN = os.getenv("BOT_TOKEN") or "9146869125:AAFMyC5e32DF4Jpz7Mrno5HQs_Z3rmU1nQ8"  # токен из @BotFather

# ВОТ ТУТ ТОКЕН xRocket (Pay API token из бота @xRocket)
XROCKET_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhcHBJZCI6IjMwOTgyNCIsImp0aSI6ImFwcDozMDk4MjQ6MjI3NThiMjktNzk0NS00YWFlLThmYzMtZDExMjhhNzZkNjg0IiwiaWF0IjoxNzk0ODE5MzU4fQ.oPcGy5_wVRg5Klk_VJaHnxi4zOcFVLjVzgRHhVz2rxo"

# xRocket: новый Pay API. Старый адрес pay.xrocket.tg больше не работает.
XROCKET_BASE_URL = "https://pay.api.xrocket.exchange"
XROCKET_AUTH_HEADER = "Authorization"
XROCKET_AUTH_PREFIX = "Bearer "

# Кто может смотреть /казна — твои telegram id (например [123456789]).
# Пустой список = команда видна всем.
ADMIN_IDS = []

# ── Общее ────────────────────────────────────────────────────────────────
BOT_NAME = "SERP CASINO"
SUPPORT_LINK = "none"
DB_PATH = "serp_casino.db"
TZ_OFFSET_HOURS = 3            # время в истории и операциях (Москва)

# ── Лимиты (в $) ─────────────────────────────────────────────────────────
MIN_DEPOSIT = 0.10
MIN_WITHDRAW = 0.50
MIN_BET = 0.10
MAX_BET = 100.0
MIN_CASHBACK_CLAIM = 0.20
CASHBACK_PERCENT = 2           # возврат с каждого проигрыша, %
INVOICE_LIFETIME_MIN = 15      # сколько живёт счёт на пополнение

# ── Внешний вид кнопок ───────────────────────────────────────────────────
# Цвет кнопок (зелёная «Играть», синие «Пополнить/Вывести») и кастомные эмодзи
# на кнопках. Нужна свежая версия aiogram (см. requirements.txt).
# Если Telegram ругается на кнопки, поставь False.
USE_BUTTON_STYLE = True
USE_BUTTON_ICONS = True

# ── Шансы (перевес казино) ───────────────────────────────────────────────
# RIG_ENABLED = False — честная игра, как было до правки.
RIG_ENABLED = True

# С какой вероятностью выигрышный для игрока бросок кубика перебрасывается
# (0 — честно). Итог по кассе: 0.10 -> казино забирает ~34%,
# 0.18 (сейчас) -> ~39%, 0.25 -> ~42%, без подкрутки -> ~29%.
PLAYER_LOSE_BOOST = 0.18
REROLL_TRIES = 3          # максимум перебросов за раунд (каждый = +3.5-4.5 сек)

KNB_BOT_WIN = 0.55        # доля побед бота в КНБ (0.333 — честно, 0.60 — жёстко)
COIN_WIN_CHANCE = 0.46    # шанс игрока в монетке (0.5 — честно)
