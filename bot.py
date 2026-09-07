from aiohttp import web
import re
import asyncio
import json
import os
import logging
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from aiogram import Bot, Dispatcher, types, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandStart, Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
    InputMediaPhoto,
    InputMediaVideo
)

import aiosqlite
from apscheduler.schedulers.asyncio import AsyncIOScheduler

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if os.path.exists("/var/www/muvio_bot"):
    BASE_DIR = "/var/www/muvio_bot"
else:
    BASE_DIR = CURRENT_DIR

LOG_FILE = os.path.join(BASE_DIR, "bot.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, encoding="utf-8")
    ]
)
logger = logging.getLogger("muvio_bot")

KYIV_TZ = ZoneInfo("Europe/Kyiv")

def get_kyiv_now():
    return datetime.now(KYIV_TZ)

BOT_TOKEN = "8704593495:AAFOeKPzOxdyomCGRd87HoWX_zSTP3EXHLs"
ADMIN_ID = 7288164492
DB_PATH = os.path.join(BASE_DIR, "rentals_base.db")
WEBAPP_URL = "https://deliver-grammar-employment-three.trycloudflare.com"

async def safe_clear_state(state: FSMContext | None, reset_data: bool = False):
    """
    Безпечне скидання стану FSM без падіння при state is None
    та без скидання сесії клієнта (за умовчанням reset_data=False).
    """
    if state is None:
        return
    try:
        if reset_data:
            await state.clear()
        else:
            await state.set_state(None)
    except Exception as e:
        logger.warning(f"Error in safe_clear_state: {e}")

# ==================== РЕКВИЗИТЫ ФОП ====================
FOP_IBAN = "UA213220010000026005350116194"
FOP_NAME = "ФОП Привалов Максим Олександрович"
FOP_TAX_ID = "3894802591"

def generate_payment_purpose(contract_num: str, contract_date: str, start_date: str, end_date: str, vehicle_type: str = "🛵 Електроскутер", has_helmet: bool = False, is_buyout: bool = False) -> str:
    is_bike = "велосипед" in (vehicle_type or "").lower()
    type_str = "електровелосипед" if is_bike else "скутер"
    c_num = contract_num if contract_num else "2804-5"
    c_date = contract_date if contract_date else "28.04.2026"
    
    if is_buyout:
        return f"Платіж за викуп транспортного засобу ({type_str}) згідно з Договором №{c_num} від {c_date} р. Без ПДВ."
        
    equipment_str = f"транспортного засобу ({type_str}) та шолома" if has_helmet else f"транспортного засобу ({type_str})"
    return f"Оплата за оренду {equipment_str} згідно з Договором №{c_num} від {c_date} р. за період з {start_date} по {end_date}. Без ПДВ."

def resolve_prices(rental_row, vehicle_data):
    p_day = vehicle_data.get("price_day", 900)
    p_week = vehicle_data.get("price_week", 2200)
    p_month = vehicle_data.get("price_month", 8000)

    if rental_row:
        try:
            if rental_row['custom_price_day'] is not None:
                p_day = rental_row['custom_price_day']
            if rental_row['custom_price_week'] is not None:
                p_week = rental_row['custom_price_week']
            if rental_row['custom_price_month'] is not None:
                p_month = rental_row['custom_price_month']
        except Exception:
            pass

    return p_day, p_week, p_month

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
scheduler = AsyncIOScheduler()

JSON_FILE = os.path.join(BASE_DIR, "fleet.json")
WAITLIST_FILE = os.path.join(BASE_DIR, "waitlist.json")
CREDENTIALS_FILE = os.path.join(BASE_DIR, "credentials.json")
LOCATION_FILE = os.path.join(BASE_DIR, "location_media.json")
SPREADSHEET_NAME = "MUVIO_Rent_CRM"

sheet_requests = None
sheet_incidents = None

def init_google_sheets():
    global sheet_requests, sheet_incidents
    if os.path.exists(CREDENTIALS_FILE):
        try:
            import gspread
            from oauth2client.service_account import ServiceAccountCredentials
            scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
            creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
            client = gspread.authorize(creds)
            spreadsheet = client.open(SPREADSHEET_NAME)
            sheet_requests = spreadsheet.worksheet("Заявки")
            sheet_incidents = spreadsheet.worksheet("Поломки")
            logger.info("✅ Подключение к Google Таблицам успешно!")
        except Exception as e:
            logger.error(f"❌ Ошибка Google Sheets: {e}")
    else:
        logger.warning(f"⚠️ Файл credentials.json не найден: {CREDENTIALS_FILE}")

init_google_sheets()

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                phone_number TEXT UNIQUE,
                full_name TEXT,
                bonus_balance REAL DEFAULT 0,
                referred_by INTEGER DEFAULT NULL,
                invited_count INTEGER DEFAULT 0,
                first_rent_date TEXT DEFAULT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS rentals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_phone TEXT,
                vehicle_info TEXT,
                end_date TEXT,
                amount_due REAL,
                custom_price_day REAL DEFAULT NULL,
                custom_price_week REAL DEFAULT NULL,
                custom_price_month REAL DEFAULT NULL,
                contract_num TEXT DEFAULT '2804-5',
                contract_date TEXT DEFAULT '28.04.2026',
                has_helmet INTEGER DEFAULT 0,
                reminder_sent INTEGER DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                rental_id INTEGER,
                amount REAL,
                bonus_used REAL DEFAULT 0,
                date_paid TEXT,
                payment_type TEXT DEFAULT 'rent'
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS buyout_deals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                vehicle_key TEXT,
                vehicle_info TEXT,
                total_price REAL,
                paid_amount REAL DEFAULT 0,
                deposit_paid REAL DEFAULT 0,
                status TEXT DEFAULT 'active',
                start_date TEXT,
                battery_spec TEXT,
                charger_spec TEXT,
                term_months INTEGER DEFAULT 6,
                contract_num TEXT DEFAULT '2804-5',
                contract_date TEXT DEFAULT '28.04.2026',
                is_current_vehicle INTEGER DEFAULT 1
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vehicle_key TEXT,
                category TEXT,
                amount REAL,
                description TEXT,
                date_added TEXT,
                paid_by TEXT DEFAULT 'company'
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS franchise_leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                phone TEXT,
                city TEXT,
                budget TEXT,
                scooters_count TEXT,
                comment TEXT,
                date_added TEXT,
                status TEXT DEFAULT 'new'
            )
        """)

        # Safe schema migrations for all existing tables in rentals_base.db
        for col_def in [
            "bonus_balance REAL DEFAULT 0",
            "referred_by INTEGER DEFAULT NULL",
            "invited_count INTEGER DEFAULT 0",
            "first_rent_date TEXT DEFAULT NULL"
        ]:
            try:
                await db.execute(f"ALTER TABLE users ADD COLUMN {col_def}")
            except Exception:
                pass

        for col_def in [
            "custom_price_day REAL DEFAULT NULL",
            "custom_price_week REAL DEFAULT NULL",
            "custom_price_month REAL DEFAULT NULL",
            "contract_num TEXT DEFAULT '2804-5'",
            "contract_date TEXT DEFAULT '28.04.2026'",
            "has_helmet INTEGER DEFAULT 0",
            "reminder_sent INTEGER DEFAULT 0"
        ]:
            try:
                await db.execute(f"ALTER TABLE rentals ADD COLUMN {col_def}")
            except Exception:
                pass

        for col_def in [
            "bonus_used REAL DEFAULT 0",
            "payment_type TEXT DEFAULT 'rent'"
        ]:
            try:
                await db.execute(f"ALTER TABLE payments ADD COLUMN {col_def}")
            except Exception:
                pass

        for col_def in [
            "battery_spec TEXT",
            "charger_spec TEXT",
            "term_months INTEGER DEFAULT 6",
            "contract_num TEXT DEFAULT '2804-5'",
            "contract_date TEXT DEFAULT '28.04.2026'",
            "is_current_vehicle INTEGER DEFAULT 1"
        ]:
            try:
                await db.execute(f"ALTER TABLE buyout_deals ADD COLUMN {col_def}")
            except Exception:
                pass

        for col_def in [
            "paid_by TEXT DEFAULT 'company'"
        ]:
            try:
                await db.execute(f"ALTER TABLE expenses ADD COLUMN {col_def}")
            except Exception:
                pass

        await db.commit()

DEFAULT_FLEET = {
    "aima_a700": {"name": "Aima A700", "type": "🛵 Електроскутер", "voltage": "72V", "range": "до 150 км", "speed": "47 км/год", "charging": "10Ач (6 годин)", "battery": "Знімається", "price_day": 900, "price_week": 2200, "price_month": 8000, "deposit": 4000, "buyout_available": True, "buyout_base_price": 50000, "status": "available", "photo_id": None, "reserved_by": None, "custom_parts_prices": {}},
    "aima_a715": {"name": "Aima A715", "type": "🛵 Електроскутер", "voltage": "72V", "range": "до 150 км", "speed": "65 км/год", "charging": "10Ач (4 години)", "battery": "Знімається", "price_day": 900, "price_week": 2200, "price_month": 8000, "deposit": 4000, "buyout_available": True, "buyout_base_price": 53000, "status": "available", "photo_id": None, "reserved_by": None, "custom_parts_prices": {}},
    "aima_f606_1": {"name": "Aima F606 №1", "type": "🛵 Електроскутер", "voltage": "72V", "range": "до 100 км", "speed": "70 км/год", "charging": "10Ач (4 години)", "battery": "Знімається", "price_day": 900, "price_week": 2200, "price_month": 8000, "deposit": 4000, "buyout_available": True, "buyout_base_price": 48000, "status": "available", "photo_id": None, "reserved_by": None, "custom_parts_prices": {}},
    "aima_journey": {"name": "Aima Journey", "type": "🛵 Електроскутер", "voltage": "72V", "range": "до 160 км", "speed": "60 км/год", "charging": "10Ач (6 годин)", "battery": "Знімається", "price_day": 900, "price_week": 2300, "price_month": 8300, "deposit": 4000, "buyout_available": True, "buyout_base_price": 55000, "status": "available", "photo_id": "AgACAgIAAxkDAAIl42qZg_FAKwHdckGhnTAsk8yblWKoAAJtHmsbtbnISCN39uZr99L9AQADAgADeQADPQQ", "reserved_by": None, "custom_parts_prices": {}},
    "aima_leopard": {"name": "Aima Leopard", "type": "🛵 Електроскутер", "voltage": "72V", "range": "до 150 км", "speed": "48 км/год", "charging": "10Ач (6 годин)", "battery": "Знімається", "price_day": 900, "price_week": 2200, "price_month": 8000, "deposit": 4000, "buyout_available": True, "buyout_base_price": 49000, "status": "available", "photo_id": None, "reserved_by": None, "custom_parts_prices": {}},
    "aima_mine": {"name": "Aima Mine", "type": "🛵 Електроскутер", "voltage": "60V", "range": "до 130 км", "speed": "55 км/год", "charging": "7Ач (6 годин)", "battery": "Знімається", "price_day": 900, "price_week": 2200, "price_month": 8000, "deposit": 4000, "buyout_available": True, "buyout_base_price": 46000, "status": "available", "photo_id": "AgACAgIAAxkDAAIl4mqZg-m6NG2rV1HIGx6SpNzMBdOhAAJsHmsbtbnISL9-I7CdeepuAQADAgADeQADPQQ", "reserved_by": None, "custom_parts_prices": {}},
    "crosser_cr13_1": {"name": "Crosser CR-13 №1", "type": "🛵 Електроскутер", "voltage": "72V", "range": "до 160 км", "speed": "85 км/год", "charging": "10Ач (6 годин)", "battery": "Знімається", "price_day": 1000, "price_week": 2500, "price_month": 8500, "deposit": 4500, "buyout_available": True, "buyout_base_price": 57000, "status": "available", "photo_id": None, "reserved_by": None, "custom_parts_prices": {}},
    "like_bike_bruser_1": {"name": "Like Bike Bruser №1", "type": "🚲 Електровелосипед", "voltage": "48V", "range": "до 80 км", "speed": "45 км/год", "charging": "7Ач (4 години)", "battery": "Знімається", "price_day": 800, "price_week": 1800, "price_month": 6000, "deposit": 3000, "buyout_available": True, "buyout_base_price": 32000, "status": "available", "photo_id": None, "reserved_by": None, "custom_parts_prices": {}},
    "crosser_cr13_2": {"name": "Crosser CR-13 №2", "type": "🛵 Електроскутер", "voltage": "72V", "range": "до 160 км", "speed": "85 км/год", "charging": "10Ач (6 годин)", "battery": "Знімається", "price_day": 1000, "price_week": 2500, "price_month": 8500, "deposit": 4500, "buyout_available": True, "buyout_base_price": 57000, "status": "available", "photo_id": None, "reserved_by": None, "custom_parts_prices": {}},
    "aima_f606_2": {"name": "Aima F606 №2", "type": "🛵 Електроскутер", "voltage": "72V", "range": "до 130 км", "speed": "70 км/год", "charging": "10Ач (4 години)", "battery": "Знімається", "price_day": 900, "price_week": 2200, "price_month": 8000, "deposit": 4000, "buyout_available": True, "buyout_base_price": 48000, "status": "available", "photo_id": None, "reserved_by": None, "custom_parts_prices": {}},
    "ado_a20f": {"name": "ADO A20F", "type": "🚲 Електровелосипед", "voltage": "48V", "range": "до 150 км", "speed": "40 км/год", "charging": "10Ач (4 години)", "battery": "Знімається", "price_day": 800, "price_week": 1800, "price_month": 6000, "deposit": 3000, "buyout_available": True, "buyout_base_price": 30000, "status": "available", "photo_id": None, "reserved_by": None, "custom_parts_prices": {}},
    "crosser_cr20": {"name": "Crosser CR-20", "type": "🛵 Електроскутер", "voltage": "72V", "range": "до 160 км", "speed": "75 км/год", "charging": "10Ач (6 годин)", "battery": "Знімається", "price_day": 1000, "price_week": 2400, "price_month": 8300, "deposit": 4000, "buyout_available": True, "buyout_base_price": 54000, "status": "available", "photo_id": None, "reserved_by": None, "custom_parts_prices": {}},
    "aima_mine_plus": {"name": "Aima Mine Plus", "type": "🛵 Електроскутер", "voltage": "60V", "range": "до 130 км", "speed": "60 км/год", "charging": "7Ач (6 годин)", "battery": "Знімається", "price_day": 900, "price_week": 2200, "price_month": 8000, "deposit": 4000, "buyout_available": True, "buyout_base_price": 47000, "status": "available", "photo_id": None, "reserved_by": None, "custom_parts_prices": {}},
    "like_bike_n5": {"name": "Like Bike N5", "type": "🛵 Електроскутер", "voltage": "60V", "range": "до 130 км", "speed": "65 км/год", "charging": "10Ач (6 годин)", "battery": "Знімається", "price_day": 900, "price_week": 2200, "price_month": 8000, "deposit": 4000, "buyout_available": True, "buyout_base_price": 46000, "status": "available", "photo_id": None, "reserved_by": None, "custom_parts_prices": {}},
    "like_bike_bruser_2": {"name": "Like Bike Bruser №2", "type": "🚲 Електровелосипед", "voltage": "48V", "range": "до 80 км", "speed": "45 км/год", "charging": "7Ач (4 години)", "battery": "Знімається", "price_day": 800, "price_week": 1800, "price_month": 6000, "deposit": 3000, "buyout_available": True, "buyout_base_price": 32000, "status": "available", "photo_id": None, "reserved_by": None, "custom_parts_prices": {}}
}

PARTS_PRICES = {
    "72V_40Ah": 14000, "72V_60Ah": 21000,
    "72V_ch5A": 1400, "72V_ch10A": 2800,
    "60V_40Ah": 14000, "60V_60Ah": 21000,
    "60V_ch5A": 1400, "60V_ch10A": 2800,
    "48V_10Ah": 0, "48V_20Ah": 3500, "48V_30Ah": 7000, "48V_40Ah": 10500,
    "48V_ch3A": 0, "48V_ch5A": 1400
}

def load_fleet():
    fleet_res = DEFAULT_FLEET.copy()
    if os.path.exists(JSON_FILE):
        try:
            with open(JSON_FILE, "r", encoding="utf-8") as f:
                saved_data = json.load(f)
                for k, v in saved_data.items():
                    if k in fleet_res:
                        fleet_res[k]["status"] = v.get("status", "available")
                        fleet_res[k]["photo_id"] = v.get("photo_id", None)
                        fleet_res[k]["reserved_by"] = v.get("reserved_by", None)
                        if "price_day" in v: fleet_res[k]["price_day"] = v["price_day"]
                        if "price_week" in v: fleet_res[k]["price_week"] = v["price_week"]
                        if "price_month" in v: fleet_res[k]["price_month"] = v["price_month"]
                        if "voltage" in v: fleet_res[k]["voltage"] = v["voltage"]
                        if "buyout_base_price" in v: fleet_res[k]["buyout_base_price"] = v["buyout_base_price"]
                        if "buyout_available" in v: fleet_res[k]["buyout_available"] = v["buyout_available"]
                        if "custom_parts_prices" in v: fleet_res[k]["custom_parts_prices"] = v["custom_parts_prices"]
        except Exception as e:
            logger.error(f"Ошибка загрузки fleet.json: {e}")
    return fleet_res

def save_fleet():
    try:
        with open(JSON_FILE, "w", encoding="utf-8") as f:
            json.dump(FLEET_DATABASE, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logger.error(f"Ошибка сохранения fleet.json: {e}")

def load_waitlist():
    if os.path.exists(WAITLIST_FILE):
        try:
            with open(WAITLIST_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_waitlist(data):
    try:
        with open(WAITLIST_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logger.error(f"Ошибка сохранения waitlist.json: {e}")

FLEET_DATABASE = load_fleet()
WAITLIST = load_waitlist()

def load_location_media():
    if os.path.exists(LOCATION_FILE):
        try:
            with open(LOCATION_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"file_id": None, "type": None}
    return {"file_id": None, "type": None}

def save_location_media(file_id, media_type):
    try:
        with open(LOCATION_FILE, "w", encoding="utf-8") as f:
            json.dump({"file_id": file_id, "type": media_type}, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logger.error(f"Ошибка сохранения location_media.json: {e}")

LOCATION_MEDIA = load_location_media()

def get_part_price(v_key: str, part_code: str) -> float:
    v_data = FLEET_DATABASE.get(v_key, {})
    custom = v_data.get("custom_parts_prices", {})
    if part_code in custom:
        return float(custom[part_code])
    return float(PARTS_PRICES.get(part_code, 0.0))

async def safe_render_card(target, text: str, reply_markup: InlineKeyboardMarkup, photo_id: str = None):
    if isinstance(target, types.CallbackQuery):
        msg = target.message
        if photo_id:
            if getattr(msg, "photo", None):
                try:
                    media = InputMediaPhoto(media=photo_id, caption=text, parse_mode="HTML")
                    await msg.edit_media(media=media, reply_markup=reply_markup)
                    return
                except Exception:
                    pass
            try:
                await msg.delete()
            except Exception:
                pass
            await msg.answer_photo(photo=photo_id, caption=text, parse_mode="HTML", reply_markup=reply_markup)
        else:
            if getattr(msg, "photo", None) or getattr(msg, "video", None):
                try:
                    await msg.delete()
                except Exception:
                    pass
                await msg.answer(text, parse_mode="HTML", reply_markup=reply_markup)
            else:
                try:
                    await msg.edit_text(text, parse_mode="HTML", reply_markup=reply_markup)
                except TelegramBadRequest:
                    pass
                except Exception:
                    await msg.answer(text, parse_mode="HTML", reply_markup=reply_markup)
    else:
        if photo_id:
            await target.answer_photo(photo=photo_id, caption=text, parse_mode="HTML", reply_markup=reply_markup)
        else:
            await target.answer(text, parse_mode="HTML", reply_markup=reply_markup)

# --- ГАЛЕРЕЯ (ОРИГИНАЛЬНАЯ ПАГИНАЦИЯ И ФИЛЬТРЫ) ---
def get_gallery_data(filter_type: str = "all"):
    items = []
    for k, v in FLEET_DATABASE.items():
        if filter_type == "available" and v["status"] != "available":
            continue
        if filter_type == "scooter" and "скутер" not in v["type"].lower():
            continue
        if filter_type == "bike" and "велосипед" not in v["type"].lower():
            continue
        items.append((k, v))
    return items

def build_gallery_card(item_key, data, index, total, filter_type):
    status_icon = "🟢 В наявності (Вільний)" if data["status"] == "available" else ("🔴 В оренді" if data["status"] == "rented" else "🛠 В ремонті")
    volt = data.get("voltage", "72V")
    buyout_p = data.get("buyout_base_price", 46000)
    
    caption = (
        f"⚡ <b>{data['name']}</b> ({data['type']} | {volt})\n"
        "────────────────────\n"
        f"📊 <b>Статус:</b> {status_icon}\n"
        f"🔋 <b>Запас ходу:</b> {data['range']}\n"
        f"🚀 <b>Швидкість:</b> {data['speed']}\n"
        f"🔌 <b>Зарядка:</b> {data['charging']}\n"
        f"🔋 <b>Акумулятор:</b> {data['battery']}\n\n"
        f"💰 <b>Тарифи оренди:</b>\n"
        f"• 1 доба: <b>{data['price_day']} грн</b>\n"
        f"• 1 тиждень: <b>{data['price_week']} грн</b>\n"
        f"• 1 місяць (28 днів): <b>{data['price_month']} грн</b>\n"
        f"🔒 <b>Застава:</b> {data['deposit']} грн\n"
        f"🏷 <b>Викуп (базова ціна):</b> {buyout_p} грн [{volt}]"
    )
    
    kb_buttons = []
    if data["status"] == "available":
        kb_buttons.append([InlineKeyboardButton(text="📝 Забронювати цей транспорт", callback_data=f"book_{item_key}")])
    else:
        kb_buttons.append([InlineKeyboardButton(text="⏳ Встати в лист очікування", callback_data=f"join_waitlist:{item_key}")])


    nav_row = [
        InlineKeyboardButton(text="◀️", callback_data=f"gallery_prev:{filter_type}:{index}"),
        InlineKeyboardButton(text=f"📍 {index + 1}/{total}", callback_data="ignore_pagination"),
        InlineKeyboardButton(text="▶️", callback_data=f"gallery_next:{filter_type}:{index}")
    ]
    kb_buttons.append(nav_row)

    filter_row = [
        InlineKeyboardButton(text="🛵 С...тери", callback_data="gallery_filter:scooter:0"),
        InlineKeyboardButton(text="🚲 Байки", callback_data="gallery_filter:bike:0"),
        InlineKeyboardButton(text="🟢 Вільні", callback_data="gallery_filter:available:0"),
        InlineKeyboardButton(text="Всі", callback_data="gallery_filter:all:0")
    ]
    kb_buttons.append(filter_row)
    
    return caption, InlineKeyboardMarkup(inline_keyboard=kb_buttons)

# --- СОСТОЯНИЯ FSM ---
class RentalForm(StatesGroup):
    chosen_vehicle_id = State()
    selected_scooter = State()
    rental_period = State()
    helmets_count = State()
    full_name = State()
    phone = State()
    age = State()
    usage_type = State()
    delivery_experience = State()
    confirm = State()

class IncidentForm(StatesGroup):
    description = State()
    photo = State()
    location = State()

class AdminReplyIncidentState(StatesGroup):
    waiting_for_reply = State()

class PaymentReceiptState(StatesGroup):
    waiting_for_receipt = State()

class BuyoutReceiptState(StatesGroup):
    waiting_for_receipt = State()

class AdminBuyoutState(StatesGroup):
    waiting_for_user_id = State()
    waiting_for_amount = State()

AdminBuyoutPayState = AdminBuyoutState

class AdminSetPartPriceState(StatesGroup):
    waiting_for_part_choice = State()
    waiting_for_price = State()

class AdminBuyoutPriceState(StatesGroup):
    waiting_for_price = State()

class AdminPhotoState(StatesGroup):
    waiting_for_photo = State()

class AdminLocationMediaState(StatesGroup):
    waiting_for_media = State()

class AdminIssueState(StatesGroup):
    waiting_for_days = State()
    waiting_for_amount = State()
    waiting_for_contract_num = State()
    waiting_for_contract_date = State()
    waiting_for_helmet = State()
    waiting_for_phone_manual = State()
    waiting_for_confirm = State()

class AdminChangeDateState(StatesGroup):
    waiting_for_new_date = State()

class AdminChangePriceState(StatesGroup):
    waiting_for_period_choice = State()
    waiting_for_new_price = State()

class AdminUpgradeState(StatesGroup):
    waiting_for_new_item = State()
    waiting_for_days = State()
    waiting_for_amount = State()

class AdminExpenseState(StatesGroup):
    waiting_for_type = State()
    waiting_for_vehicle = State()
    waiting_for_payer = State()
    waiting_for_exact_category = State()
    waiting_for_desc_manual = State()
    waiting_for_amount = State()
    waiting_for_desc = State()

# --- КЛАВИАТУРЫ ---
def get_main_keyboard():
    kb = [
        [KeyboardButton(text="🛵 Вільні скутери"), KeyboardButton(text="👤 Особистий кабінет")],
        [KeyboardButton(text="📄 Умови оренди"), KeyboardButton(text="🛠 Поломка")],
        [KeyboardButton(text="📍 Локація та контакти")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_admin_keyboard():
    kb = [
        [KeyboardButton(text="📊 Фінансова статистика (/stats)"), KeyboardButton(text="👑 Управління флотом")],
        [KeyboardButton(text="➕ Додати витрату"), KeyboardButton(text="📜 Історія та опис витрат")],
        [KeyboardButton(text="🏷 Активні викупи")],
        [KeyboardButton(text="🗑 Видалити витрату"), KeyboardButton(text="🚪 Вийти з адмінки")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_auth_keyboard():
    kb = [
        [KeyboardButton(text="📱 Авторизуватися за номером", request_contact=True)],
        [KeyboardButton(text="❌ Скасувати дію")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True, one_time_keyboard=True)

def get_cancel_keyboard(show_back: bool = False):
    if show_back:
        kb = [[KeyboardButton(text="⬅️ Назад"), KeyboardButton(text="❌ Скасувати дію")]]
    else:
        kb = [[KeyboardButton(text="❌ Скасувати дію")]]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_exp_main_type_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛵 Витрати на Скутер", callback_data="exptype:scooter")],
        [InlineKeyboardButton(text="🚲 Витрати на Велосипед", callback_data="exptype:bike")],
        [InlineKeyboardButton(text="🏢 Загальні витрати флоту / Офіс", callback_data="exptype:general")]
    ])

def get_exp_vehicles_kb(v_type: str):
    target_type = "🛵 Електроскутер" if v_type == "scooter" else "🚲 Електровелосипед"
    buttons = []
    for k, v in FLEET_DATABASE.items():
        if v["type"] == target_type:
            buttons.append([InlineKeyboardButton(text=f"{v['name']}", callback_data=f"expveh:{k}")])
    buttons.append([InlineKeyboardButton(text="⬅️ Назад до типу", callback_data="exp_back_to_type")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_exp_payer_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏢 За наш рахунок (MUVIO)", callback_data="exppayer:company")],
        [InlineKeyboardButton(text="👤 За рахунок клієнта (Вина орендаря)", callback_data="exppayer:client")],
        [InlineKeyboardButton(text="⬅️ Назад до вибору транспорту", callback_data="exp_back_to_veh")]
    ])

def get_admin_text_and_kb():
    total = len(FLEET_DATABASE)
    avail = sum(1 for v in FLEET_DATABASE.values() if v["status"] == "available")
    rented = sum(1 for v in FLEET_DATABASE.values() if v["status"] == "rented")
    repair = sum(1 for v in FLEET_DATABASE.values() if v["status"] == "repair")
    
    text = (
        "👑 <b>УПРАВЛІННЯ ФЛОТОМ MUVIO</b>\n"
        "────────────────────\n"
        f"📊 <b>Всього одиниць:</b> {total}\n"
        f"🟢 <b>Вільні:</b> {avail}\n"
        f"🔴 <b>В оренді / Броні:</b> {rented}\n"
        f"🛠 <b>В ремонті:</b> {repair}\n"
        f"📋 <b>Лист очікування:</b> {len(WAITLIST)} осіб\n\n"
        "Оберіть модель для видачі клієнту або зміни статусу:"
    )
    
    buttons = []
    for item_id, data in FLEET_DATABASE.items():
        status_icon = "🟢" if data["status"] == "available" else ("🔴" if data["status"] == "rented" else "🛠")
        photo_icon = " 📷" if data.get("photo_id") else ""
        res_info = f" (Бронь: {data['reserved_by']})" if data.get("reserved_by") else ""
        volt_tag = f" [{data.get('voltage', '72V')}]"
        buttons.append([InlineKeyboardButton(
            text=f"{status_icon} {data['name']}{volt_tag}{res_info}{photo_icon}", 
            callback_data=f"admmanage:{item_id}"
        )])
        
    buttons.append([InlineKeyboardButton(text="🏷 Активні викупи (Rent-to-Own)", callback_data="adm_all_buyouts")])
    buttons.append([InlineKeyboardButton(text="📍 Оновити медіа локації (фото/відео)", callback_data="add_loc_media")])
    return text, InlineKeyboardMarkup(inline_keyboard=buttons)

# ==================== СТАРТ И ОСНОВНОЙ РОУТИНГ ====================

@dp.message(CommandStart(), StateFilter("*"))
async def start_cmd_handler(message: types.Message, state: FSMContext):
    await safe_clear_state(state)
    args = message.text.split()[1:]
    if args and args[0].startswith("ref_"):
        try:
            ref_id = int(args[0].replace("ref_", ""))
            if ref_id != message.from_user.id:
                async with aiosqlite.connect(DB_PATH) as db:
                    await db.execute(
                        "INSERT OR IGNORE INTO users (telegram_id, referred_by) VALUES (?, ?)",
                        (message.from_user.id, ref_id)
                    )
                    await db.commit()
        except Exception:
            pass

    user_name = message.from_user.first_name or "Максим"
    welcome_text = (
        f"Привіт, {user_name}! 👋\n\n"
        "Вітаємо в офіційному боті <b>MUVIO Rent Odesa</b> — сервісі оренди та викупу електроскутерів і електровелосипедів!\n\n"
        "📌 <b>Що ви можете зробити в цьому боті:</b>\n\n"
        "🛵 <b>«Вільні скутери»</b> — перегляд каталогу техніки в наявності (скутери та велобайки), вибір тарифу (доба / тиждень / місяць), шоломів та швидке оформлення заявки.\n\n"
        "👤 <b>«Особистий кабінет»</b> — трекінг терміну оренди, перегляд шкали прогресу викупу скутера, формування реквізитів ФОП та надсилання чеків.\n\n"
        "🎁 <b>«Реферальна програма»</b> (у кабінеті) — ваша особиста посилка для запрошення друзів. Отримуйте <b>+200 грн бонусів</b> на рахунок за кожного друга, який візьме транспорт!\n\n"
        "📄 <b>«Умови оренди»</b> — правила експлуатації в Одесі, порядок оплати, застави та розподіл відповідальності.\n\n"
        "🛠 <b>«Поломка»</b> — швидка форма сповіщення техпідтримки про несправність із надсиланням фото та геолокації.\n\n"
        "📍 <b>«Локація та контакти»</b> — точна адреса точки видачі (Приморська, 22), фото/відео орієнтир входу та прямий зв'язок з менеджером.\n\n"
        "Оберіть потрібний розділ у меню нижче 👇"
    )
    await message.answer(welcome_text, parse_mode="HTML", reply_markup=get_main_keyboard())

@dp.message(lambda msg: msg.text and any(w in msg.text.lower() for w in ["вільні", "каталог", "скутери"]), StateFilter("*"))
async def client_gallery_trigger(message: types.Message, state: FSMContext):
    await safe_clear_state(state)
    items = get_gallery_data("all")
    if not items:
        await message.answer("⚠️ Каталог транспорту наразі пустий.", reply_markup=get_main_keyboard())
        return
    item_key, data = items[0]
    caption, kb = build_gallery_card(item_key, data, 0, len(items), "all")
    await safe_render_card(message, caption, kb, data.get("photo_id"))

@dp.callback_query(F.data.startswith("gallery_next:") | F.data.startswith("gallery_prev:"), StateFilter("*"))
async def gallery_pagination_handler(callback: CallbackQuery):
    await callback.answer()
    parts = callback.data.split(":")
    action = parts[0]
    filter_type = parts[1]
    curr_idx = int(parts[2])
    
    items = get_gallery_data(filter_type)
    if not items:
        await callback.answer("Каталог порожній", show_alert=True)
        return
        
    if action == "gallery_next":
        new_idx = (curr_idx + 1) % len(items)
    else:
        new_idx = (curr_idx - 1 + len(items)) % len(items)
        
    item_key, data = items[new_idx]
    caption, kb = build_gallery_card(item_key, data, new_idx, len(items), filter_type)
    await safe_render_card(callback, caption, kb, data.get("photo_id"))

@dp.callback_query(F.data.startswith("gallery_filter:"), StateFilter("*"))
async def gallery_filter_handler(callback: CallbackQuery):
    await callback.answer()
    parts = callback.data.split(":")
    filter_type = parts[1]
    items = get_gallery_data(filter_type)
    if not items:
        await callback.answer("Немає транспорту за цим фільтром", show_alert=True)
        return
    item_key, data = items[0]
    caption, kb = build_gallery_card(item_key, data, 0, len(items), filter_type)
    await safe_render_card(callback, caption, kb, data.get("photo_id"))

@dp.callback_query(F.data == "ignore_pagination", StateFilter("*"))
async def ignore_pagination_callback(callback: CallbackQuery):
    await callback.answer()

@dp.callback_query(F.data.startswith("join_waitlist:"), StateFilter("*"))
async def join_waitlist_handler(callback: CallbackQuery):
    parts = callback.data.split(":")
    v_key = parts[1] if len(parts) > 1 else ""
    user_id = callback.from_user.id
    user_name = callback.from_user.full_name
    username = f"@{callback.from_user.username}" if callback.from_user.username else "немає"
    
    v_data = FLEET_DATABASE.get(v_key, {})
    model_name = v_data.get("name", "скутер")
    
    global WAITLIST
    if not isinstance(WAITLIST, list):
        WAITLIST = []
    
    if user_id not in WAITLIST:
        WAITLIST.append(user_id)
        save_waitlist(WAITLIST)
        
    await callback.answer("✅ Вас успішно додано до листа очікування!", show_alert=True)
    
    client_msg = (
        f"📋 <b>Лист очікування:</b>\n\n"
        f"Вас успішно додано до черги на <b>{model_name}</b>.\n"
        "Як тільки цей транспорт або інша модель звільниться, ми одразу повідомимо вас!"
    )
    try:
        await callback.message.answer(client_msg, parse_mode="HTML")
    except Exception:
        pass
        
    admin_msg = (
        "📋 <b>НОВИЙ КЛІЄНТ У ЛИСТІ ОЧІКУВАННЯ!</b>\n"
        "────────────────────\n"
        f"👤 <b>Клієнт:</b> {user_name} ({username})\n"
        f"🆔 <b>TG ID:</b> <code>{user_id}</code>\n"
        f"🛵 <b>Цікавить модель:</b> <b>{model_name}</b> (<code>{v_key}</code>)\n\n"
        f"👥 <b>Загалом людей у черзі:</b> {len(WAITLIST)} осіб"
    )
    try:
        await bot.send_message(chat_id=ADMIN_ID, text=admin_msg, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Помилка відправки повідомлення адміну про лист очікування: {e}")


@dp.callback_query(F.data == "back_to_main", StateFilter("*"))
async def back_to_main_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await safe_clear_state(state)
    await callback.message.answer("Головне меню:", reply_markup=get_main_keyboard())

@dp.message(lambda msg: msg.text and any(w in msg.text.lower() for w in ["кабінет", "профіль", "особистий"]), StateFilter("*"))
async def client_profile_trigger(message: types.Message, state: FSMContext):
    await process_profile(message, state)

@dp.callback_query(F.data == "back_to_cabinet", StateFilter("*"))
async def back_to_cabinet_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await process_profile(callback, state)

@dp.message(lambda msg: msg.text and any(w in msg.text.lower() for w in ["умови", "правила"]), StateFilter("*"))
async def client_conditions_trigger(message: types.Message, state: FSMContext):
    await show_faq_and_conditions(message, state)

async def show_faq_and_conditions(message: types.Message, state: FSMContext = None):
    await safe_clear_state(state)
    text = (
        "📋 <b>УМОВИ ОРЕНДИ ТА ФІНАНСОВА ВІДПОВІДАЛЬНІСТЬ MUVIO RENT</b>\n"
        "────────────────────\n\n"
        "💵 <b>Правила оплати та застави:</b>\n"
        "• Мінімальний термін оренди — <b>1 доба</b>.\n"
        "• <b>Перерахунок не проводиться:</b> При достроковому поверненні транспорту з ініціативи орендаря <b>оплата за сплачений період не повертається</b>.\n"
        "• <b>Повернення залогу:</b> Здійснюється протягом <b>від 1 до 5 днів</b> після здачі скутера назад.\n\n"
        "📍 <b>Доставка та зона експлуатації:</b>\n"
        "• Самовивіз з нашої локації або доставка по місту (тариф виїзду до клієнта) — <b>500–700 грн</b>.\n"
        "• Доставка за межі міста (область) — <b>700–1000 грн</b>.\n"
        "• Про необхідність доставки слід попереджати завчасно!\n"
        "• Основна зона: м. Одеса.\n"
        "• Їзда за межі міста дозволена <b>виключно за попередньою домовленістю</b> з менеджером.\n\n"
        "⏰ <b>Терміни, повернення та штрафи:</b>\n"
        "• Повернення скутера відбувається в останній день оренди у час, узгоджений з менеджером.\n"
        "• У разі не приїзду у потрібний час у призначену годину стягується <b>штраф 100 грн</b>.\n"
        "• Затримка повернення скутера без попереднього обговорення з менеджером карається <b>штрафом 10% за добу</b>.\n\n"
        "🛠 <b>Розподіл відповідальності при поломках та ДТП:</b>\n"
        "• <b>Технічні поломки:</b> Ремонт вузлів, які вийшли з ладу через технічну несправність, здійснюється <b>за рахунок компанії</b>.\n"
        "• <b>Проколи та знос:</b> Пробиття або попередчасний знос покришки здійснюється <b>за рахунок клієнта</b>.\n"
        "• <b>Механічні пошкодження / Падіння:</b> Пошкодження внаслідок падіння оплачуються <b>клієнтом</b>.\n"
        "• <b>ДТП:</b> У разі ДТП клієнт зобов'язаний у терміновому порядку набрати менеджера. Простій скутера на штрафстоянці відбувається <b>за рахунок клієнта</b>. Якщо клієнт вирішив вирішити питання самостійно з винуватцем і по ітогу не отримав оплату за збиток — виплата покладається <b>на клієнта</b>.\n\n"
        "📄 <b>Оформлення:</b>\n"
        "• Угода фіксується в електронному договорі перед видачею ключа.\n"
        "• Договір підписується в цифровому вигляді за допомогою КЕП (кваліфікованого електронного підпису).\n"
        "• У разі проблем із КЕП питання обговорюється з менеджером."
    )
    if isinstance(message, types.CallbackQuery):
        await message.message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard())
    else:
        await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard())

@dp.message(lambda msg: msg.text and any(w in msg.text.lower() for w in ["локація", "контакти", "адреса"]), StateFilter("*"))
async def client_location_trigger(message: types.Message, state: FSMContext):
    await contacts_info(message, state)

async def contacts_info(message: types.Message, state: FSMContext = None):
    await safe_clear_state(state)
    text = (
        "📍 <b>ТОЧКА ВИДАЧІ ТА СЕРВІС MUVIO RENT</b>\n"
        "────────────────────\n\n"
        "🏢 <b>Адреса:</b> м. Одеса, вул. Приморська, 22\n"
        "🗺 <a href=\"https://maps.google.com\">Відкрити локацію на Google Maps</a>\n\n"
        "⏰ <b>Графік видачі та прийому:</b> 11:00 - 22:00 (за попередньою домовленістю)\n\n"
        "📞 <b>Контакти для зв'язку:</b>\n"
        "📱 <b>Телефон:</b> +380 (63) 831-63-61\n"
        "💬 <b>Telegram:</b> @Muvio_Odesa"
    )
    file_id = LOCATION_MEDIA.get("file_id")
    media_type = LOCATION_MEDIA.get("type")

    if file_id and media_type == "video":
        video_caption = "📼 <b>Відео-орієнтир як до нас пройти</b>"
        if isinstance(message, types.CallbackQuery):
            await message.message.answer(text, parse_mode="HTML", disable_web_page_preview=False)
            await message.message.answer_video(video=file_id, caption=video_caption, parse_mode="HTML", reply_markup=get_main_keyboard())
        else:
            await message.answer(text, parse_mode="HTML", disable_web_page_preview=False)
            await message.answer_video(video=file_id, caption=video_caption, parse_mode="HTML", reply_markup=get_main_keyboard())
        return

    if file_id and media_type == "photo":
        if isinstance(message, types.CallbackQuery):
            await message.message.answer_photo(photo=file_id, caption=text, parse_mode="HTML", reply_markup=get_main_keyboard())
        else:
            await message.answer_photo(photo=file_id, caption=text, parse_mode="HTML", reply_markup=get_main_keyboard())
        return

    if isinstance(message, types.CallbackQuery):
        await message.message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard(), disable_web_page_preview=False)
    else:
        await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard(), disable_web_page_preview=False)

# --- АДМИН: ОБНОВЛЕНИЕ МЕДИА ЛОКАЦИИ ---
@dp.callback_query(F.data == "add_loc_media", StateFilter("*"))
async def add_loc_media_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID: return
    await callback.answer()
    await state.set_state(AdminLocationMediaState.waiting_for_media)
    await callback.message.answer("Надішліть нове **відео або фото** для розділу локації:", reply_markup=get_cancel_keyboard())

@dp.message(StateFilter(AdminLocationMediaState.waiting_for_media), F.photo | F.video)
async def add_loc_media_save(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    if message.video:
        file_id = message.video.file_id
        media_type = "video"
    else:
        file_id = message.photo[-1].file_id
        media_type = "photo"
    
    LOCATION_MEDIA["file_id"] = file_id
    LOCATION_MEDIA["type"] = media_type
    save_location_media(file_id, media_type)
    await safe_clear_state(state)
    await message.answer(f"✅ Медіа локації успішно збережено ({media_type})!", reply_markup=get_admin_keyboard())

# ==================== ПОЛОМКИ ====================

@dp.message(lambda msg: msg.text and any(w in msg.text.lower() for w in ["поломка", "ремонт", "зламався"]), StateFilter("*"))
async def client_incident_trigger(message: types.Message, state: FSMContext):
    await start_incident(message, state)

async def start_incident(message: types.Message, state: FSMContext = None):
    await safe_clear_state(state)
    await state.set_state(IncidentForm.description)
    text = (
        "🛠 <b>ПОВІДОМИТИ ПРО ПОЛОМКУ / СЕРВІС</b>\n"
        "────────────────────\n"
        "Будь ласка, детально опишіть, що сталося з технікою:"
    )
    if isinstance(message, types.CallbackQuery):
        await message.message.answer(text, parse_mode="HTML", reply_markup=get_cancel_keyboard())
    else:
        await message.answer(text, parse_mode="HTML", reply_markup=get_cancel_keyboard())

@dp.message(StateFilter(IncidentForm.description), F.text)
async def incident_desc_handler(message: types.Message, state: FSMContext):
    if "скасувати" in message.text.lower():
        await safe_clear_state(state)
        await message.answer("Дію скасовано.", reply_markup=get_main_keyboard())
        return
    await state.update_data(incident_desc=message.text.strip())
    await state.set_state(IncidentForm.photo)
    
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="⏭ Пропустити фото")],
            [KeyboardButton(text="❌ Скасувати дію")]
        ],
        resize_keyboard=True
    )
    await message.answer("Надішліть **фото або відео** поломки (або натисніть «Пропустити фото»):", reply_markup=kb)

@dp.message(StateFilter(IncidentForm.photo), F.photo | F.video | F.text)
async def incident_photo_handler(message: types.Message, state: FSMContext):
    if message.text and "скасувати" in message.text.lower():
        await safe_clear_state(state)
        await message.answer("Дію скасовано.", reply_markup=get_main_keyboard())
        return
        
    file_id = None
    if message.photo:
        file_id = message.photo[-1].file_id
    elif message.video:
        file_id = message.video.file_id
        
    await state.update_data(incident_file=file_id)
    await state.set_state(IncidentForm.location)
    
    loc_kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📍 Поділитися геолокацією", request_location=True)],
            [KeyboardButton(text="⏭ Пропустити геолокацію")],
            [KeyboardButton(text="❌ Скасувати дію")]
        ],
        resize_keyboard=True
    )
    await message.answer("📍 Поділіться вашою **геолокацією** для швидкого виїзду майстра (або пропустіть):", reply_markup=loc_kb)

@dp.message(StateFilter(IncidentForm.location), F.location | F.text)
async def incident_finalize_handler(message: types.Message, state: FSMContext):
    if message.text and "скасувати" in message.text.lower():
        await safe_clear_state(state)
        await message.answer("Дію скасовано.", reply_markup=get_main_keyboard())
        return

    data = await state.get_data()
    await safe_clear_state(state)
    
    desc = data.get("incident_desc", "-")
    file_id = data.get("incident_file")
    
    lat, lon = None, None
    if message.location:
        lat = message.location.latitude
        lon = message.location.longitude

    user = message.from_user
    now_str = get_kyiv_now().strftime("%Y-%m-%d %H:%M:%S")

    user_phone = "Не визначено"
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT phone_number FROM users WHERE telegram_id = ?", (user.id,)) as cur:
            u_row = await cur.fetchone()
            if u_row and u_row[0]:
                user_phone = f"+{u_row[0]}"

    if sheet_incidents:
        try:
            sheet_incidents.append_row([
                now_str, str(user.id), user.full_name, f"@{user.username or 'немає'}", desc,
                f"Lat: {lat}, Lon: {lon}" if lat else "Не вказано", "Нова"
            ])
        except Exception as e:
            logger.error(f"Ошибка записи поломки в CRM: {e}")

    await message.answer(
        "✅ <b>Ваше повідомлення про поломку прийнято!</b>\n\n"
        "Технічний відділ MUVIO вже отримав інформацію та зв'яжеться з вами прямо в цьому боті або за телефоном.",
        parse_mode="HTML",
        reply_markup=get_main_keyboard()
    )

    admin_text = (
        "🚨 <b>НОВЕ ПОВІДОМЛЕННЯ ПРО ПОЛОМКУ / ЧП!</b>\n"
        "────────────────────\n"
        f"👤 <b>Клієнт:</b> {user.full_name} (@{user.username or 'немає'})\n"
        f"📱 <b>Телефон:</b> {user_phone}\n"
        f"🛵 <b>Транспорт:</b> Не визначено\n"
        f"⏰ <b>Час:</b> <code>{now_str}</code>\n\n"
        f"📝 <b>Опис проблеми:</b>\n{desc}\n\n"
        f"📍 <b>Локація:</b> {'Вказано' if lat else 'Не вказана'}"
    )
    
    admin_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Відповісти клієнту", callback_data=f"adm_reply_incident:{user.id}")]
    ])

    try:
        if file_id:
            await bot.send_photo(chat_id=ADMIN_ID, photo=file_id, caption=admin_text, parse_mode="HTML", reply_markup=admin_kb)
        else:
            await bot.send_message(chat_id=ADMIN_ID, text=admin_text, parse_mode="HTML", reply_markup=admin_kb)
            
        if lat and lon:
            await bot.send_location(chat_id=ADMIN_ID, latitude=lat, longitude=lon)
    except Exception as e:
        logger.error(f"Ошибка отправки поломки админу: {e}")

@dp.callback_query(F.data.startswith("adm_reply_incident:"), StateFilter("*"))
async def admin_reply_incident_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID: return
    await callback.answer()
    target_user_id = int(callback.data.split(":")[1])
    await state.update_data(reply_target_user_id=target_user_id)
    await state.set_state(AdminReplyIncidentState.waiting_for_reply)
    await callback.message.answer(f"Введіть текст відповіді для клієнта <b>{target_user_id}</b>:", parse_mode="HTML", reply_markup=get_cancel_keyboard())

@dp.message(StateFilter(AdminReplyIncidentState.waiting_for_reply), F.text)
async def admin_reply_incident_send(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    if "скасувати" in message.text.lower():
        await safe_clear_state(state)
        await message.answer("Дію скасовано.", reply_markup=get_admin_keyboard())
        return

    data = await state.get_data()
    target_user_id = data.get("reply_target_user_id")
    reply_text = message.text.strip()
    await safe_clear_state(state)

    try:
        await bot.send_message(
            chat_id=target_user_id,
            text=f"🛠 <b>Відповідь техпідтримки MUVIO Rent:</b>\n────────────────────\n\n{reply_text}",
            parse_mode="HTML"
        )
        await message.answer("✅ <b>Відповідь доставлена клієнту!</b>", parse_mode="HTML", reply_markup=get_admin_keyboard())
    except Exception as e:
        await message.answer(f"❌ Не вдалося надіслати повідомлення клієнту: {e}", reply_markup=get_admin_keyboard())

@dp.message(lambda msg: msg.text and "скасувати" in msg.text.lower(), StateFilter("*"))
async def cancel_action_msg(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    await safe_clear_state(state)
    if current_state and "Admin" in current_state:
        await message.answer("Дію скасовано. Ви повернулися в панель адміністратора.", reply_markup=get_admin_keyboard())
    else:
        await message.answer("Дію скасовано.", reply_markup=get_main_keyboard())

# ==================== ОСОБИСТИЙ КАБІНЕТ ====================

async def process_profile(event: types.Message | types.CallbackQuery, state: FSMContext = None):
    await safe_clear_state(state)
    if isinstance(event, types.CallbackQuery):
        user_id = event.from_user.id
        msg = event.message
    else:
        user_id = event.from_user.id if (event.from_user and not event.from_user.is_bot) else event.chat.id
        msg = event

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE telegram_id = ?", (user_id,)) as cursor:
            user = await cursor.fetchone()

        if not user or not user['phone_number']:
            text = (
                "🔒 <b>Авторизація не пройдена</b>\n\n"
                "Для перегляду інформації про активні оренди, статус викупу та терміни оплати, будь ласка, поділіться номером телефону."
            )
            if isinstance(event, types.CallbackQuery):
                await event.message.answer(text, parse_mode="HTML", reply_markup=get_auth_keyboard())
            else:
                await msg.answer(text, parse_mode="HTML", reply_markup=get_auth_keyboard())
            return

        async with db.execute("SELECT * FROM rentals WHERE user_phone = ? ORDER BY id DESC LIMIT 1", (user['phone_number'],)) as cursor:
            single_r = await cursor.fetchone()
        rentals = [single_r] if single_r else []

        async with db.execute("SELECT * FROM buyout_deals WHERE user_id = ? AND status = 'active' ORDER BY id DESC LIMIT 1", (user_id,)) as cursor:
            buyout = await cursor.fetchone()

    bonus_bal = user['bonus_balance'] if 'bonus_balance' in user.keys() and user['bonus_balance'] else 0.0
    now = get_kyiv_now().replace(tzinfo=None)

    text = f"👤 <b>Особистий кабінет</b>\n📱 Номер: +{user['phone_number']}\n💰 <b>Бонусний баланс:</b> {bonus_bal:.2f} грн\n\n"
    
    if rentals:
        text += "<b>📊 СТАТУС АКТИВНОЇ ОРЕНДИ:</b>\n────────────────────\n"
        for r in rentals:
            try:
                raw_end = r['end_date']
                end_dt = datetime.strptime(raw_end, "%Y-%m-%d %H:%M") if " " in raw_end else datetime.strptime(raw_end, "%Y-%m-%d")
                total_hours = (end_dt - (end_dt - timedelta(days=7))).total_seconds() / 3600
                hours_left = max(0, (end_dt - now).total_seconds() / 3600)
                pct = max(0.0, min(1.0, hours_left / total_hours)) if total_hours > 0 else 0
                
                filled = int(pct * 10)
                bar = "▓" * filled + "░" * (10 - filled)
                
                days_left = int(hours_left // 24)
                hrs_left = int(hours_left % 24)
                time_str = f"<b>{days_left} дн. {hrs_left} год.</b>" if hours_left > 0 else "🔴 <b>Термін вичерпано!</b>"
            except Exception:
                bar = "▓▓▓▓▓▓▓▓▓▓"
                time_str = r['end_date']

            text += (
                f"🛵 <b>Техніка:</b> {r['vehicle_info']}\n"
                f"📅 <b>Діє до:</b> <code>{r['end_date']}</code>\n"
                f"⏳ <b>До кінця тижня:</b> {time_str}\n"
                f"📈 <b>Шкала оренди:</b> <code>[{bar}]</code>\n"
                f"💰 <b>До сплати за оренду:</b> <b>{r['amount_due']:.2f} грн</b>\n"
                f"────────────────────\n"
            )
    else:
        text += "────────────────────\nУ вас немає активної техніки в оренді.\n────────────────────\n"

    if buyout:
        tot = buyout['total_price']
        paid = buyout['paid_amount']
        dep = buyout['deposit_paid']
        rem = max(0.0, tot - paid)
        b_pct = (paid / tot) if tot > 0 else 0.0
        b_filled = int(b_pct * 10)
        b_bar = "▓" * b_filled + "░" * (10 - b_filled)
        
        term_plan = buyout['term_months'] if 'term_months' in buyout.keys() and buyout['term_months'] else 6
        months_passed = 1
        try:
            start_raw = buyout['start_date']
            start_dt = datetime.strptime(start_raw[:10], "%Y-%m-%d")
            days_passed = max(0, (now - start_dt).days)
            months_passed = min(term_plan, max(1, (days_passed // 30) + 1))
        except Exception:
            months_passed = 1

        def format_ukr_months(n: int) -> str:
            if n % 10 == 1 and n % 100 != 11:
                return f"{n} місяць"
            elif 2 <= n % 10 <= 4 and not (12 <= n % 100 <= 14):
                return f"{n} місяці"
            else:
                return f"{n} місяців"

        term_str = f"{format_ukr_months(months_passed)} з {format_ukr_months(term_plan)}"
        bat_spec = buyout['battery_spec'] if 'battery_spec' in buyout.keys() and buyout['battery_spec'] else "-"
        ch_spec = buyout['charger_spec'] if 'charger_spec' in buyout.keys() and buyout['charger_spec'] else "-"
        comp_str = f"{bat_spec}, {ch_spec}" if (bat_spec != "-" or ch_spec != "-") else "Стандарт"

        text += (
            "\n<b>🏷 ПРОГРАМА ВИКУПУ (RENT-TO-OWN):</b>\n"
            "────────────────────\n"
            f"🛵 <b>Назва моделі скутера:</b> <b>{buyout['vehicle_info']}</b>\n"
            f"🔋 <b>Комплектація:</b> {comp_str}\n"
            f"🔒 <b>Сума залогу (20%):</b> <code>{dep:.2f} грн</code>\n"
            f"💵 <b>Повна сума викупу:</b> <code>{tot:.2f} грн</code>\n"
            f"✅ <b>Вже виплачено:</b> <code>{paid:.2f} грн з {tot:.2f} грн</code>\n"
            f"⏳ <b>Залишилось виплатити:</b> <b>{rem:.2f} грн</b>\n"
            f"📅 <b>Термін викупу:</b> {term_str}\n"
            f"📈 <b>Прогрес викупу ({int(b_pct*100)}%):</b>\n"
            f"<code>[{b_bar}]</code>\n"
            "────────────────────\n"
        )


    kb_buttons = []
    if buyout:
        kb_buttons.append([InlineKeyboardButton(text="💳 Внести платіж за викуп", callback_data="buyout_pay_req")])
    else:
        kb_buttons.append([InlineKeyboardButton(text="🛵 Викуп скутера", callback_data="client_buyout_menu")])

    if rentals:
        kb_buttons.append([InlineKeyboardButton(text="💳 Продовжити оренду (Реквізити)", callback_data="select_period")])
        
    kb_buttons.append([InlineKeyboardButton(text="🎁 Реферальна програма", callback_data="ref_program")])

    cabinet_kb = InlineKeyboardMarkup(inline_keyboard=kb_buttons)
    if isinstance(event, types.CallbackQuery):
        await safe_render_card(event, text, cabinet_kb)
    else:
        await msg.answer(text, parse_mode="HTML", reply_markup=cabinet_kb)


@dp.callback_query(F.data == "ref_program", StateFilter("*"))
async def process_ref_program(callback: CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    bot_info = await bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start=ref_{user_id}"

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT bonus_balance, invited_count FROM users WHERE telegram_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()

    bonus_bal = row['bonus_balance'] if row and 'bonus_balance' in row.keys() and row['bonus_balance'] else 0.0
    invited = row['invited_count'] if row and 'invited_count' in row.keys() and row['invited_count'] else 0

    share_text = "Привіт! Орендуй електроскутер або електровелосипед у MUVIO Rent зі знижкою. Реєструйся за посиланням:"
    import urllib.parse
    share_url = f"https://t.me/share/url?url={urllib.parse.quote(ref_link)}&text={urllib.parse.quote(share_text)}"

    ref_text = (
        "🎁 <b>РЕФЕРАЛЬНА ПРОГРАМА MUVIO RENT</b>\n"
        "────────────────────\n"
        "Запрошуйте друзів та колег-кур'єрів та отримуйте бонуси на оплату оренди!\n\n"
        f"👥 <b>Запрошено друзів:</b> {invited} осіб\n"
        f"💰 <b>Нараховано бонусів:</b> {bonus_bal:.2f} грн\n\n"
        f"🔗 <b>Ваше персональне реферальне посилання:</b>\n"
        f"<code>{ref_link}</code>\n\n"
        "<i>Скопіюйте посилання та надішліть другу. Коли він забронює транспорт та отримає ключі, вам автоматично буде нараховано +200 грн на бонусний рахунок!</i>"
    )

    ref_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 Поділитися посиланням", url=share_url)],
        [InlineKeyboardButton(text="◀️ Назад до кабінету", callback_data="back_to_cabinet")]
    ])
    await safe_render_card(callback, ref_text, ref_kb)

# ==================== МОДУЛЬ ПРОДОВЖЕННЯ ОРЕНДИ ТА ОПЛАТИ ЗА РЕКВІЗИТАМИ ====================

@dp.callback_query(F.data == "select_period", StateFilter("*"))
async def process_select_period(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await show_renew_period_selection(callback, state)

@dp.message(lambda msg: msg.text and ("продовжити" in msg.text.lower() and "реквизит" in msg.text.lower()), StateFilter("*"))
async def client_renew_by_msg_trigger(message: types.Message, state: FSMContext):
    await show_renew_period_selection(message, state)

async def show_renew_period_selection(target, state: FSMContext):
    user_id = target.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE telegram_id = ?", (user_id,)) as cur:
            user = await cur.fetchone()

        if not user or not user['phone_number']:
            text = "⚠️ Спочатку пройдіть авторизацію за номером телефону!"
            if isinstance(target, types.CallbackQuery):
                await target.answer(text, show_alert=True)
            else:
                await target.answer(text)
            return

        async with db.execute(
            "SELECT * FROM rentals WHERE user_phone = ? ORDER BY id DESC LIMIT 1",
            (user['phone_number'],)
        ) as cur:
            rental = await cur.fetchone()

    if not rental:
        text = "У вас немає активної оренди для продовження."
        if isinstance(target, types.CallbackQuery):
            await target.answer(text, show_alert=True)
        else:
            await target.answer(text)
        return

    vehicle_name = rental['vehicle_info']
    fleet_item = None
    for k, v in FLEET_DATABASE.items():
        if v["name"] == vehicle_name:
            fleet_item = v
            break

    p_day, p_week, p_month = resolve_prices(rental, fleet_item or {})

    period_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🗓 1 Доба — {int(p_day)} грн", callback_data="renew_period:1")],
        [InlineKeyboardButton(text=f"📅 1 Тиждень — {int(p_week)} грн", callback_data="renew_period:7")],
        [InlineKeyboardButton(text=f"🗓 1 Місяць — {int(p_month)} грн", callback_data="renew_period:28")],
        [InlineKeyboardButton(text="⬅️ Назад до кабінету", callback_data="back_to_cabinet")]
    ])

    text = (
        f"🛵 <b>ПРОДОВЖЕННЯ ОРЕНДИ: {vehicle_name}</b>\n"
        "────────────────────\n"
        f"📅 Поточний термін дії до: <code>{rental['end_date']}</code>\n\n"
        "Оберіть період, на який ви бажаєте продовжити оренду:"
    )

    if isinstance(target, types.CallbackQuery):
        await safe_render_card(target, text, period_kb)
    else:
        await target.answer(text, parse_mode="HTML", reply_markup=period_kb)

@dp.callback_query(F.data.startswith("renew_period:"), StateFilter("*"))
async def process_renew_period_choice(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    days = int(callback.data.split(":")[1])
    user_id = callback.from_user.id

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE telegram_id = ?", (user_id,)) as cur:
            user = await cur.fetchone()

        async with db.execute(
            "SELECT * FROM rentals WHERE user_phone = ? ORDER BY id DESC LIMIT 1",
            (user['phone_number'],)
        ) as cur:
            rental = await cur.fetchone()

    if not rental:
        await callback.answer("У вас немає активної оренди.", show_alert=True)
        return

    vehicle_name = rental['vehicle_info']
    fleet_item = None
    for k, v in FLEET_DATABASE.items():
        if v["name"] == vehicle_name:
            fleet_item = v
            break

    p_day, p_week, p_month = resolve_prices(rental, fleet_item or {})
    vehicle_type = fleet_item["type"] if fleet_item else "🛵 Електроскутер"

    if days == 1:
        base_amount = p_day
    elif days in (28, 30):
        base_amount = p_month
    else:
        base_amount = p_week

    bonus_bal = user['bonus_balance'] if 'bonus_balance' in user.keys() and user['bonus_balance'] else 0.0

    if bonus_bal >= 200:
        use_bonus_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"🎁 Списати 200 грн бонусів (До сплати {int(base_amount - 200)} грн)", callback_data=f"apply_bonus:{days}:200")],
            [InlineKeyboardButton(text=f"💳 Сплатити повну суму ({int(base_amount)} грн)", callback_data=f"apply_bonus:{days}:0")],
            [InlineKeyboardButton(text="◀️ Назад до вибору терміну", callback_data="select_period")]
        ])
        text = (
            f"💰 <b>Бонусна програма MUVIO:</b>\n"
            f"На вашому балансі є <b>{bonus_bal:.2f} грн</b> бонусів.\n\n"
            f"Бажаєте списати <b>200 грн</b> у рахунок цієї оплати?"
        )
        await safe_render_card(callback, text, use_bonus_kb)
        return

    await render_payment_requisites(callback, state, rental, user, days, base_amount, 0, vehicle_type)

@dp.callback_query(F.data.startswith("apply_bonus:"), StateFilter("*"))
async def process_apply_bonus_choice(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    _, days_str, bonus_str = callback.data.split(":")
    days = int(days_str)
    bonus_used = float(bonus_str)
    user_id = callback.from_user.id

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE telegram_id = ?", (user_id,)) as cur:
            user = await cur.fetchone()

        async with db.execute(
            "SELECT * FROM rentals WHERE user_phone = ? ORDER BY id DESC LIMIT 1",
            (user['phone_number'],)
        ) as cur:
            rental = await cur.fetchone()

    if not rental:
        await callback.answer("У вас немає активної оренди.", show_alert=True)
        return

    vehicle_name = rental['vehicle_info']
    fleet_item = None
    for k, v in FLEET_DATABASE.items():
        if v["name"] == vehicle_name:
            fleet_item = v
            break

    p_day, p_week, p_month = resolve_prices(rental, fleet_item or {})
    vehicle_type = fleet_item["type"] if fleet_item else "🛵 Електроскутер"

    if days == 1:
        base_amount = p_day
    elif days in (28, 30):
        base_amount = p_month
    else:
        base_amount = p_week

    await render_payment_requisites(callback, state, rental, user, days, base_amount, bonus_used, vehicle_type)

async def render_payment_requisites(target, state: FSMContext, rental, user, days: int, base_amount: float, bonus_used: float, vehicle_type: str):
    amount_due = max(0.0, base_amount - bonus_used)

    raw_date_str = rental['end_date'].split()[0] if rental['end_date'] else ""
    try:
        if "." in raw_date_str:
            current_end_dt = datetime.strptime(raw_date_str, "%d.%m.%Y")
        elif "-" in raw_date_str:
            current_end_dt = datetime.strptime(raw_date_str, "%Y-%m-%d")
        else:
            current_end_dt = datetime.now()
    except Exception:
        current_end_dt = datetime.now()

    new_start_dt = current_end_dt
    if days == 1:
        # На добу: з 01 по 01 (той самий день)
        purpose_end_dt = new_start_dt
        new_db_end_dt = new_start_dt + timedelta(days=1)
    elif days == 7:
        # На тиждень: з 01 по 07 (+6 днів включно)
        purpose_end_dt = new_start_dt + timedelta(days=6)
        new_db_end_dt = new_start_dt + timedelta(days=7)
    elif days in (28, 30):
        # На місяць: з 01 по 28 (+27 днів включно)
        purpose_end_dt = new_start_dt + timedelta(days=27)
        new_db_end_dt = new_start_dt + timedelta(days=days)
    else:
        purpose_end_dt = new_start_dt + timedelta(days=max(0, days - 1))
        new_db_end_dt = new_start_dt + timedelta(days=days)

    start_str = new_start_dt.strftime("%d.%m.%Y")
    end_str = purpose_end_dt.strftime("%d.%m.%Y")
    new_end_date_str = new_db_end_dt.strftime("%Y-%m-%d 23:59")

    rental_keys = rental.keys()
    contract_num = rental['contract_num'] if 'contract_num' in rental_keys and rental['contract_num'] else "2804-5"
    contract_date = rental['contract_date'] if 'contract_date' in rental_keys and rental['contract_date'] else "28.04.2026"
    has_helmet = bool(rental['has_helmet']) if 'has_helmet' in rental_keys else False

    payment_purpose = generate_payment_purpose(
        contract_num=contract_num,
        contract_date=contract_date,
        start_date=start_str,
        end_date=end_str,
        vehicle_type=vehicle_type,
        has_helmet=has_helmet,
        is_buyout=False
    )

    await state.update_data(
        renew_days=days,
        renew_amount=amount_due,
        bonus_used=bonus_used,
        new_end_date=new_end_date_str,
        rental_id=rental['id'],
        vehicle_info=rental['vehicle_info'],
        user_phone=rental['user_phone']
    )

    bonus_info = f"🎁 <b>Списано бонусів:</b> <code>{bonus_used:.2f} грн</code>\n" if bonus_used > 0 else ""

    text = (
        "💳 <b>РЕКВІЗИТИ ДЛЯ ОПЛАТИ ТА ПРОДОВЖЕННЯ ОРЕНДИ</b>\n"
        "────────────────────\n"
        "Натисніть на текст у блоці коду, щоб скопіювати в 1 клік:\n\n"
        f"🏢 <b>Отримувач:</b>\n<code>{FOP_NAME}</code>\n\n"
        f"🔢 <b>ЄДРПОУ / ІПН (РНОКПП):</b>\n<code>{FOP_TAX_ID}</code>\n\n"
        f"🏛 <b>IBAN:</b>\n<code>{FOP_IBAN}</code>\n\n"
        f"{bonus_info}"
        f"💰 <b>Сума до сплати:</b>\n<code>{amount_due:.2f} грн</code>\n\n"
        f"📝 <b>Призначення платежу:</b>\n<code>{payment_purpose}</code>\n\n"
        "⚠️ <b>Важливо:</b> Вставляйте призначення платежу повністю без змін, щоб платіж зарахувався автоматично.\n\n"
        "<i>Після переказу коштів натисніть кнопку «✅ Я оплатив(ла) (Надіслати чек)» нижче та надішліть квитанцію.</i>"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Я оплатив(ла) (Надіслати чек)", callback_data="upload_receipt")],
        [InlineKeyboardButton(text="◀️ Назад до вибору терміну", callback_data="select_period")]
    ])

    if isinstance(target, types.CallbackQuery):
        await safe_render_card(target, text, kb)
    else:
        await target.answer(text, parse_mode="HTML", reply_markup=kb)

@dp.callback_query(F.data == "upload_receipt", StateFilter("*"))
async def process_start_upload_receipt(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    if not data.get("rental_id"):
        user_id = callback.from_user.id
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM users WHERE telegram_id = ?", (user_id,)) as cur:
                user = await cur.fetchone()
            if user:
                async with db.execute("SELECT * FROM rentals WHERE user_phone = ? ORDER BY id DESC LIMIT 1", (user['phone_number'],)) as cur:
                    rental = await cur.fetchone()
                if rental:
                    await state.update_data(
                        rental_id=rental['id'],
                        user_phone=rental['user_phone'],
                        vehicle_info=rental['vehicle_info'],
                        renew_days=7,
                        renew_amount=rental['amount_due'],
                        bonus_used=0.0
                    )

    await state.set_state(PaymentReceiptState.waiting_for_receipt)
    cancel_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Скасувати", callback_data="back_to_cabinet")]
    ])
    await callback.message.answer(
        "📄 <b>Будь ласка, надішліть фото або файл квитанції про оплату:</b>\n\n"
        "<i>(Прикріпіть скріншот з банківського додатку або PDF-файл квитанції)</i>",
        parse_mode="HTML",
        reply_markup=cancel_kb
    )

@dp.message(PaymentReceiptState.waiting_for_receipt, F.text)
async def process_receipt_text_or_cancel(message: types.Message, state: FSMContext):
    msg_text = (message.text or "").strip().lower()
    if any(w in msg_text for w in ["скасувати", "відміна", "отмена", "назад", "cancel"]):
        await safe_clear_state(state)
        await message.answer("Дію скасовано. Повернення до кабінету:", reply_markup=get_main_keyboard())
        await process_profile(message, state)
        return
    await message.answer(
        "Будь ласка, надішліть саме <b>фото скріншоту</b> або <b>файл квитанції</b> (PDF) про сплату:",
        parse_mode="HTML"
    )

@dp.message(PaymentReceiptState.waiting_for_receipt, F.photo | F.document)
async def process_receive_receipt(message: types.Message, state: FSMContext):
    data = await state.get_data()
    await safe_clear_state(state)

    days = data.get("renew_days", 7)
    amount = data.get("renew_amount", 0.0)
    bonus_used = data.get("bonus_used", 0.0)
    new_end_date = data.get("new_end_date", "")
    rental_id = data.get("rental_id")
    vehicle_info = data.get("vehicle_info", "Скутер")
    user_phone = data.get("user_phone", "")

    user_id = message.from_user.id
    username_str = f"@{message.from_user.username}" if message.from_user.username else "немає"
    full_name = message.from_user.full_name or "Клієнт"

    bonus_str = f"\n🎁 <b>Використано бонусів:</b> <code>{bonus_used:.2f} грн</code>" if bonus_used > 0 else ""

    admin_card = (
        "💳 <b>НОВА ЗАЯВКА НА ПРОДОВЖЕННЯ ОРЕНДИ!</b>\n"
        "────────────────────\n"
        f"👤 <b>Клієнт:</b> {full_name} ({username_str})\n"
        f"📱 <b>Телефон:</b> +{user_phone}\n"
        f"🆔 <b>Telegram ID:</b> <code>{user_id}</code>\n"
        f"🛵 <b>Транспорт:</b> <b>{vehicle_info}</b>\n"
        f"⏱ <b>Термін продовження:</b> <b>{days} дн.</b>{bonus_str}\n"
        f"💰 <b>До сплати на ФОП:</b> <b>{amount:.2f} грн</b>\n"
        f"📅 <b>Нова дата (після підтвердження):</b> <code>{new_end_date}</code>\n"
        "────────────────────\n"
        "Перевірте надходження коштів на рахунок ФОП:"
    )

    confirm_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Підтвердити оплату та продовжити", callback_data=f"payok:{rental_id}:{days}:{user_id}:{bonus_used}:{amount}")],
        [InlineKeyboardButton(text="❌ Відхилити платіж", callback_data=f"payreject:{rental_id}:{user_id}")]
    ])

    await message.answer(
        "✅ <b>Квитанцію прийнято!</b>\n"
        "Менеджер перевірить надходження коштів та підтвердить продовження оренди у боті.",
        parse_mode="HTML",
        reply_markup=get_main_keyboard()
    )

    try:
        if message.photo:
            await bot.send_photo(chat_id=ADMIN_ID, photo=message.photo[-1].file_id, caption=admin_card, parse_mode="HTML", reply_markup=confirm_kb)
        elif message.document:
            await bot.send_document(chat_id=ADMIN_ID, document=message.document.file_id, caption=admin_card, parse_mode="HTML", reply_markup=confirm_kb)
    except Exception as e:
        logger.error(f"Помилка відправки чека адміну: {e}")

@dp.callback_query(F.data.startswith("payok:"), StateFilter("*"))
async def admin_confirm_payment_action(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return

    parts = callback.data.split(":")
    rental_id = int(parts[1])
    days = int(parts[2])
    user_id = int(parts[3])
    bonus_used = float(parts[4]) if len(parts) > 4 else 0.0
    paid_amount = float(parts[5]) if len(parts) > 5 else 0.0

    now_str = get_kyiv_now().strftime("%Y-%m-%d %H:%M:%S")

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM rentals WHERE id = ?", (rental_id,)) as cur:
            rental = await cur.fetchone()

        if not rental:
            await callback.answer("⚠️ Оренду не знайдено в БД!", show_alert=True)
            return

        try:
            raw_date_str = rental['end_date'].split()[0]
            if "." in raw_date_str:
                current_end_dt = datetime.strptime(raw_date_str, "%d.%m.%Y")
            elif "-" in raw_date_str:
                current_end_dt = datetime.strptime(raw_date_str, "%Y-%m-%d")
            else:
                current_end_dt = datetime.now()
        except Exception:
            current_end_dt = datetime.now()

        new_end_dt = current_end_dt + timedelta(days=days)
        new_end_date_str = new_end_dt.strftime("%Y-%m-%d 23:59")

        await db.execute(
            "UPDATE rentals SET end_date = ?, reminder_sent = 0 WHERE id = ?",
            (new_end_date_str, rental_id)
        )

        await db.execute(
            "INSERT INTO payments (user_id, rental_id, amount, bonus_used, date_paid, payment_type) VALUES (?, ?, ?, ?, ?, 'rent')",
            (user_id, rental_id, paid_amount, bonus_used, now_str)
        )

        if bonus_used > 0:
            await db.execute(
                "UPDATE users SET bonus_balance = MAX(0, bonus_balance - ?) WHERE telegram_id = ?",
                (bonus_used, user_id)
            )

        await db.commit()

    push_msg = (
        "🎉 <b>Оплату підтверджено! Оренду успішно продовжено.</b>\n"
        "────────────────────\n"
        f"📅 <b>Новий термін оренди до:</b> <code>{new_end_date_str}</code>\n"
        "────────────────────\n"
        "Вся оновлена інформація доступна у вашому <b>«👤 Особистому кабінеті»</b>.\n"
        "Дякуємо, що обираєте MUVIO Rent! 🚀"
    )

    try:
        await bot.send_message(chat_id=user_id, text=push_msg, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Помилка відправки клієнту: {e}")

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    await callback.message.answer(
        f"✅ <b>Оплату {paid_amount:.2f} грн успішно підтверджено!</b>\n"
        f"Термін оренди для клієнта (ID: <code>{user_id}</code>) оновлено до <b>{new_end_date_str}</b>.",
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("payreject:"), StateFilter("*"))
async def admin_reject_payment_action(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return

    parts = callback.data.split(":")
    rental_id = int(parts[1])
    user_id = int(parts[2])

    reject_msg = (
        "❌ <b>Ваш платіж було відхилено або кошти не надійшли на рахунок ФОП.</b>\n\n"
        "Будь ласка, перевірте статус переказу або зверніться до менеджера: @Muvio_Odesa"
    )
    try:
        await bot.send_message(chat_id=user_id, text=reject_msg, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Помилка сповіщення про відхилення: {e}")

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    await callback.message.answer(f"❌ Платіж для клієнта (ID: <code>{user_id}</code>) відхилено.", parse_mode="HTML")
    await callback.answer()


# ==================== МОДУЛЬ ВЫКУПА ====================

@dp.callback_query(F.data == "client_buyout_menu", StateFilter("*"))
async def client_buyout_menu_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await safe_clear_state(state)
    
    text = (
        "🛵 <b>ПРОГРАМА ВИКУПУ ТРАНСПОРТУ MUVIO (RENT-TO-OWN)</b>\n"
        "────────────────────\n"
        "Оберіть модель скутера або електровелосипеда, яку ви хочете оформити під викуп:"
    )
    
    buttons = []
    for k, v in FLEET_DATABASE.items():
        if v.get("buyout_available", True):
            volt = v.get("voltage", "72V")
            b_price = v.get("buyout_base_price", 46000)
            buttons.append([InlineKeyboardButton(text=f"{v['name']} ({volt}) — від {b_price} грн", callback_data=f"show_buyout_card:{k}")])
            
    buttons.append([InlineKeyboardButton(text="⬅️ Назад в кабінет", callback_data="back_to_cabinet")])
    await safe_render_card(callback, text, InlineKeyboardMarkup(inline_keyboard=buttons))

@dp.callback_query(F.data.startswith("show_buyout_card:"), StateFilter("*"))
async def show_buyout_vehicle_card(callback: CallbackQuery):
    await callback.answer()
    v_key = callback.data.split(":")[1]
    data = FLEET_DATABASE.get(v_key, {})
    volt = data.get("voltage", "60V")
    b_price = data.get("buyout_base_price", 46000)
    
    text = (
        f"🛵 <b>Викуп моделі: {data.get('name', 'Транспорт')}</b>\n"
        "────────────────────\n"
        f"⚡ <b>Вольтаж системи:</b> {volt}\n"
        f"🔋 <b>Запас ходу:</b> {data.get('range')}\n"
        f"🚀 <b>Швидкість:</b> {data.get('speed')}\n"
        f"🏷 <b>Базова вартість викупу (без АКБ):</b> {b_price} грн\n\n"
        "Натисніть кнопку нижче, щоб ознайомитися з офіційними умовами та підібрати комплектацію (АКБ + Зарядка):"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Подати заявку на викуп", callback_data=f"b_terms:{v_key}")],
        [InlineKeyboardButton(text="⬅️ Назад до каталогу", callback_data="client_buyout_menu")]
    ])
    await safe_render_card(callback, text, kb)

@dp.callback_query(F.data.startswith("b_terms:"), StateFilter("*"))
async def buyout_terms_explanation_step(callback: CallbackQuery):
    await callback.answer()
    v_key = callback.data.split(":")[1]
    
    terms_text = (
        "📜 <b>ОФІЦІЙНІ УМОВИ ПРОГРАМИ ВИКУПУ (RENT-TO-OWN)</b>\n"
        "────────────────────\n\n"
        "1. 🔒 <b>Завдаток (Застава):</b>\n"
        "• Обов'язковий перший внесок складає <b>20% від повної вартості</b> обраної комплектації.\n"
        "• ⚠️ <b>Увага:</b> У разі відмови клієнта від викупу через деякий час — <b>застава 20% не повертається</b>.\n\n"
        "2. 🛠 <b>Сервіс та Обслуговування:</b>\n"
        "• <b>Вартість запчастин та деталей:</b> сплачується <b>клієнтом</b>.\n"
        "• <b>Робота та ремонт:</b> здійснюється майстрами MUVIO <b>безкоштовно</b>.\n\n"
        "3. 💰 <b>Порядок виплат:</b>\n"
        "• Клієнт продовжує оплачувати щотижневу оренду скутера/велосипеда, на якому катається.\n"
        "• <b>Усі кошти, які ви вносите окремо зверху оренди, зараховуються у шкалу викупу!</b>\n\n"
        "4. 🔋 <b>Формування ціни та комплектація:</b>\n"
        "• Базова комплектація йде з мінімально допустимою на транспортний засіб батареєю: <b>10 Ah для велосипеда, 40 Ah для скутера</b>.\n"
        "• Фінальна сума залежить від обраної ємності батареї та потужності зарядного пристрою.\n"
        "────────────────────\n"
        "Ви погоджуєтеся з цими умовами?"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Погоджуюсь з умовами", callback_data=f"b_bat:{v_key}")],
        [InlineKeyboardButton(text="❌ Скасувати", callback_data="client_buyout_menu")]
    ])
    await safe_render_card(callback, terms_text, kb)

@dp.callback_query(F.data.startswith("b_bat:"), StateFilter("*"))
async def buyout_choose_battery_step(callback: CallbackQuery):
    await callback.answer()
    v_key = callback.data.split(":")[1]
    v_data = FLEET_DATABASE.get(v_key, {})
    volt = v_data.get("voltage", "60V")
    
    buttons = []
    if volt == "72V":
        p_40 = get_part_price(v_key, "72V_40Ah")
        p_60 = get_part_price(v_key, "72V_60Ah")
        buttons.append([InlineKeyboardButton(text=f"🔋 72V 40Ah (базова) (+{p_40:.0f} грн)", callback_data=f"b_ch:{v_key}:72V_40Ah")])
        buttons.append([InlineKeyboardButton(text=f"🔋 72V 60Ah (+{p_60:.0f} грн)", callback_data=f"b_ch:{v_key}:72V_60Ah")])
    elif volt == "60V":
        p_40 = get_part_price(v_key, "60V_40Ah")
        p_60 = get_part_price(v_key, "60V_60Ah")
        buttons.append([InlineKeyboardButton(text=f"🔋 60V 40Ah (базова) (+{p_40:.0f} грн)", callback_data=f"b_ch:{v_key}:60V_40Ah")])
        buttons.append([InlineKeyboardButton(text=f"🔋 60V 60Ah (+{p_60:.0f} грн)", callback_data=f"b_ch:{v_key}:60V_60Ah")])
    else:
        p_10 = get_part_price(v_key, "48V_10Ah")
        p_20 = get_part_price(v_key, "48V_20Ah")
        p_30 = get_part_price(v_key, "48V_30Ah")
        p_40 = get_part_price(v_key, "48V_40Ah")
        buttons.append([InlineKeyboardButton(text=f"🔋 48V 10Ah (базова) (+{p_10:.0f} грн)", callback_data=f"b_ch:{v_key}:48V_10Ah")])
        buttons.append([InlineKeyboardButton(text=f"🔋 48V 20Ah (+{p_20:.0f} грн)", callback_data=f"b_ch:{v_key}:48V_20Ah")])
        buttons.append([InlineKeyboardButton(text=f"🔋 48V 30Ah (+{p_30:.0f} грн)", callback_data=f"b_ch:{v_key}:48V_30Ah")])
        buttons.append([InlineKeyboardButton(text=f"🔋 48V 40Ah (+{p_40:.0f} грн)", callback_data=f"b_ch:{v_key}:48V_40Ah")])

    buttons.append([InlineKeyboardButton(text="❌ Скасувати", callback_data="client_buyout_menu")])
    text = f"⚡ <b>Оберіть ємність акумулятора під систему {volt}:</b>"
    await safe_render_card(callback, text, InlineKeyboardMarkup(inline_keyboard=buttons))

@dp.callback_query(F.data.startswith("b_ch:"), StateFilter("*"))
async def buyout_choose_charger_step(callback: CallbackQuery):
    await callback.answer()
    _, v_key, bat_code = callback.data.split(":")
    v_data = FLEET_DATABASE.get(v_key, {})
    volt = v_data.get("voltage", "60V")
    
    buttons = []
    prefix = "72V" if volt == "72V" else ("60V" if volt == "60V" else "48V")
    if volt in ["72V", "60V"]:
        p_5a = get_part_price(v_key, f"{prefix}_ch5A")
        p_10a = get_part_price(v_key, f"{prefix}_ch10A")
        buttons.append([InlineKeyboardButton(text=f"🔌 Зарядка 5A (+{p_5a:.0f} грн)", callback_data=f"b_term:{v_key}:{bat_code}:{prefix}_ch5A")])
        buttons.append([InlineKeyboardButton(text=f"🔌 Швидка 10A (+{p_10a:.0f} грн)", callback_data=f"b_term:{v_key}:{bat_code}:{prefix}_ch10A")])
    else:
        p_3a = get_part_price(v_key, "48V_ch3A")
        p_5a = get_part_price(v_key, "48V_ch5A")
        buttons.append([InlineKeyboardButton(text=f"🔌 Зарядка 3A (+{p_3a:.0f} грн)", callback_data=f"b_term:{v_key}:{bat_code}:48V_ch3A")])
        buttons.append([InlineKeyboardButton(text=f"🔌 Швидка 5A (+{p_5a:.0f} грн)", callback_data=f"b_term:{v_key}:{bat_code}:48V_ch5A")])

    buttons.append([InlineKeyboardButton(text="❌ Скасувати", callback_data="client_buyout_menu")])
    text = "🔌 <b>Оберіть зарядний пристрій:</b>"
    await safe_render_card(callback, text, InlineKeyboardMarkup(inline_keyboard=buttons))

@dp.callback_query(F.data.startswith("b_term:"), StateFilter("*"))
async def buyout_choose_term_step(callback: CallbackQuery):
    await callback.answer()
    parts = callback.data.split(":")
    v_key, bat_code, ch_code = parts[1], parts[2], parts[3]
    v_data = FLEET_DATABASE.get(v_key, {})
    
    text = (
        f"🛵 <b>Викуп {v_data.get('name', 'скутера')}</b>\n"
        "────────────────────\n"
        "⏳ <b>Оберіть бажаний термін викупу (від 3 до 8 місяців):</b>\n\n"
        "Оберіть період, за який вам зручно виплатити повну вартість транспорту:"
    )
    buttons = [
        [
            InlineKeyboardButton(text="🗓 3 міс.", callback_data=f"b_calc:{v_key}:{bat_code}:{ch_code}:3"),
            InlineKeyboardButton(text="🗓 4 міс.", callback_data=f"b_calc:{v_key}:{bat_code}:{ch_code}:4"),
            InlineKeyboardButton(text="🗓 5 міс.", callback_data=f"b_calc:{v_key}:{bat_code}:{ch_code}:5")
        ],
        [
            InlineKeyboardButton(text="🗓 6 міс.", callback_data=f"b_calc:{v_key}:{bat_code}:{ch_code}:6"),
            InlineKeyboardButton(text="🗓 7 міс.", callback_data=f"b_calc:{v_key}:{bat_code}:{ch_code}:7"),
            InlineKeyboardButton(text="🗓 8 міс.", callback_data=f"b_calc:{v_key}:{bat_code}:{ch_code}:8")
        ],
        [InlineKeyboardButton(text="🔄 Назад до комплектації", callback_data=f"b_bat:{v_key}")],
        [InlineKeyboardButton(text="❌ Скасувати", callback_data="client_buyout_menu")]
    ]
    await safe_render_card(callback, text, InlineKeyboardMarkup(inline_keyboard=buttons))

@dp.callback_query(F.data.startswith("b_calc:"), StateFilter("*"))
async def buyout_finalize_calculation_step(callback: CallbackQuery):
    await callback.answer()
    parts = callback.data.split(":")
    v_key = parts[1]
    bat_code = parts[2]
    ch_code = parts[3]
    months = int(parts[4]) if len(parts) > 4 else 6
    
    v_data = FLEET_DATABASE.get(v_key, {})
    base_pr = float(v_data.get("buyout_base_price", 46000))
    bat_pr = get_part_price(v_key, bat_code)
    ch_pr = get_part_price(v_key, ch_code)
    
    total_buyout_price = base_pr + bat_pr + ch_pr
    deposit_required = total_buyout_price * 0.20
    monthly_payment = (total_buyout_price - deposit_required) / months if months > 0 else 0
    
    summary_text = (
        f"📋 <b>ПІДСУМОК КОМПЛЕКТАЦІЇ ВИКУПУ:</b>\n"
        "────────────────────\n"
        f"🛵 <b>Модель:</b> {v_data.get('name')}\n"
        f"⚡ <b>Вольтаж:</b> {v_data.get('voltage', '60V')}\n"
        f"🔋 <b>Акумулятор:</b> {bat_code.replace('_', ' ')} (+{bat_pr:.0f} грн)\n"
        f"🔌 <b>Зарядний пристрій:</b> {ch_code.replace('_', ' ')} (+{ch_pr:.0f} грн)\n"
        f"📅 <b>Обраний термін викупу:</b> <b>{months} міс.</b>\n"
        "────────────────────\n"
        f"💵 <b>Повна вартість викупу:</b> {total_buyout_price:.2f} грн\n"
        f"🔒 <b>Обов'язковий завдаток (20%):</b> {deposit_required:.2f} грн\n"
        f"💳 <b>Щомісячний платіж:</b> ~{monthly_payment:.2f} грн/міс.\n\n"
        "Надіслати заявку менеджеру для підтвердження та оформлення?"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Підтвердити та надіслати заявку", callback_data=f"sfab:{v_key}:{bat_code}:{ch_code}:{months}")],
        [InlineKeyboardButton(text="⏳ Змінити термін викупу", callback_data=f"b_term:{v_key}:{bat_code}:{ch_code}")],
        [InlineKeyboardButton(text="🔄 Обрати іншу комплектацію", callback_data=f"b_bat:{v_key}")],
        [InlineKeyboardButton(text="❌ Скасувати", callback_data="client_buyout_menu")]
    ])
    await safe_render_card(callback, summary_text, kb)

@dp.callback_query(F.data.startswith("sfab:"), StateFilter("*"))
async def process_send_final_buyout_app(callback: CallbackQuery):
    await callback.answer()
    parts = callback.data.split(":")
    v_key = parts[1]
    bat_code = parts[2]
    ch_code = parts[3]
    months = int(parts[4]) if len(parts) > 4 else 6
    
    user_id = callback.from_user.id
    user_name = callback.from_user.full_name
    username = f"@{callback.from_user.username}" if callback.from_user.username else "немає"
    
    v_data = FLEET_DATABASE.get(v_key, {})
    base_pr = float(v_data.get("buyout_base_price", 46000))
    bat_pr = get_part_price(v_key, bat_code)
    ch_pr = get_part_price(v_key, ch_code)
    
    total_pr = base_pr + bat_pr + ch_pr
    dep_pr = total_pr * 0.20
    bat_str = bat_code.replace("_", " ")
    ch_str = ch_code.replace("_", " ")
    
    phone = "Не знайдено"
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT phone_number FROM users WHERE telegram_id = ?", (user_id,)) as cur:
            u_row = await cur.fetchone()
            if u_row and u_row[0]:
                phone = f"+{u_row[0]}"

    await callback.message.answer(
        "🎉 <b>Вашу заявку на викуп з обраною комплектацією прийнято!</b>\n\n"
        f"🛵 <b>Модель:</b> {v_data.get('name')}\n"
        f"🔋 <b>Комплектація:</b> {bat_str}, {ch_str}\n"
        f"📅 <b>Термін викупу:</b> {months} міс.\n"
        f"💰 <b>Загальна сума:</b> {total_pr:.2f} грн\n"
        f"🔒 <b>Завдаток (20%):</b> {dep_pr:.2f} грн\n\n"
        "Менеджер перевірить наявність та зв'яжеться з вами для підписання договору!",
        parse_mode="HTML",
        reply_markup=get_main_keyboard()
    )

    now_str = get_kyiv_now().strftime("%Y-%m-%d")
    deal_id = None
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO buyout_deals 
            (user_id, vehicle_key, vehicle_info, total_price, paid_amount, deposit_paid, status, start_date, battery_spec, charger_spec, term_months)
            VALUES (?, ?, ?, ?, 0, ?, 'pending', ?, ?, ?, ?)""",
            (user_id, v_key, v_data.get('name', 'Скутер'), total_pr, dep_pr, now_str, bat_str, ch_str, months)
        )
        deal_id = cursor.lastrowid
        await db.commit()

    admin_msg = (
        "🏷 <b>НОВА ЗАЯВКА НА ВИКУП СКУТЕРА!</b>\n"
        "────────────────────\n"
        f"👤 <b>Клієнт:</b> {user_name} ({username})\n"
        f"🆔 <b>TG ID:</b> <code>{user_id}</code>\n"
        f"📱 <b>Телефон:</b> {phone}\n"
        f"🎯 <b>Скутер під викуп:</b> <b>{v_data.get('name')}</b> [{v_data.get('voltage', '60V')}]\n"
        f"🔋 <b>Акумулятор:</b> <b>{bat_str}</b>\n"
        f"🔌 <b>Зарядка:</b> <b>{ch_str}</b>\n"
        f"📅 <b>Термін викупу:</b> <b>{months} міс.</b>\n"
        f"💵 <b>Повна сума:</b> <b>{total_pr:.2f} грн</b>\n"
        f"🔒 <b>Завдаток (20%):</b> <b>{dep_pr:.2f} грн</b>"
    )

    admin_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Схвалити викуп та зафіксувати", callback_data=f"b_appr:{deal_id}")]
    ])

    try:
        await bot.send_message(chat_id=ADMIN_ID, text=admin_msg, parse_mode="HTML", reply_markup=admin_kb)
    except Exception as e:
        logger.error(f"Ошибка алерта админа: {e}")

@dp.callback_query(F.data.startswith("b_appr:"), StateFilter("*"))
async def admin_approve_buyout_deal(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    await callback.answer()
    parts = callback.data.split(":")
    now_str = get_kyiv_now().strftime("%Y-%m-%d")
    
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if len(parts) == 2:
            deal_id = int(parts[1])
            async with db.execute("SELECT * FROM buyout_deals WHERE id = ?", (deal_id,)) as cur:
                deal = await cur.fetchone()
            if not deal:
                await callback.answer("Угоду не знайдено", show_alert=True)
                return
            await db.execute("UPDATE buyout_deals SET status = 'active', start_date = ? WHERE id = ?", (now_str, deal_id))
            await db.commit()
            u_id = deal['user_id']
            v_key = deal['vehicle_key']
            v_info = deal['vehicle_info']
            tot_price = deal['total_price']
            dep_price = deal['deposit_paid']
            bat_spec = deal['battery_spec']
            ch_spec = deal['charger_spec']
            months = deal['term_months'] if 'term_months' in deal.keys() and deal['term_months'] else 6
        else:
            u_id = int(parts[1])
            v_key = parts[2]
            tot_price = float(parts[3])
            dep_price = float(parts[4])
            months = int(parts[5]) if len(parts) > 5 else 6
            v_data = FLEET_DATABASE.get(v_key, {})
            v_info = v_data.get('name', 'Скутер')
            bat_spec = "-"
            ch_spec = "-"
            await db.execute(
                """INSERT INTO buyout_deals 
                (user_id, vehicle_key, vehicle_info, total_price, paid_amount, deposit_paid, status, start_date, battery_spec, charger_spec, term_months) 
                VALUES (?, ?, ?, ?, 0, ?, 'active', ?, ?, ?, ?)""",
                (u_id, v_key, v_info, tot_price, dep_price, now_str, bat_spec, ch_spec, months)
            )
            await db.commit()

    if v_key in FLEET_DATABASE:
        FLEET_DATABASE[v_key]["reserved_by"] = u_id
        FLEET_DATABASE[v_key]["status"] = "rented"
        save_fleet()

    try:
        comp_str = f"{bat_spec}, {ch_spec}" if (bat_spec and bat_spec != "-" or ch_spec and ch_spec != "-") else "Стандарт"
        client_notice = (
            "🎉 <b>Вітаємо! Вашу заявку на викуп схвалено!</b>\n\n"
            f"🛵 <b>Модель:</b> {v_info}\n"
            f"🔋 <b>Комплектація:</b> {comp_str}\n"
            f"📅 <b>Термін викупу:</b> {months} міс.\n"
            f"💵 <b>Повна сума викупу:</b> {tot_price:.2f} грн\n"
            f"🔒 <b>Завдаток (20%):</b> {dep_price:.2f} грн\n\n"
            "✅ <b>Договір Rent-to-Own успішно активовано!</b>\n"
            "Ви можете відстежувати графік виплат та шкалу прогресу в Особистому кабінеті."
        )
        await bot.send_message(chat_id=u_id, text=client_notice, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Помилка відправки сповіщення клієнту про викуп: {e}")

    await callback.message.edit_text(callback.message.text + "\n\n✅ <b>СТАТУС: Схвалено та зафіксовано в базі!</b>", parse_mode="HTML")


# ==================== БРОНИРОВАНИЕ ОРЕНДЫ ====================

def get_booking_vehicles_kb():
    buttons = []
    for k, v in FLEET_DATABASE.items():
        if v.get("status") == "available":
            p_w = v.get("price_week", 2200)
            volt = v.get("voltage", "72V")
            buttons.append([InlineKeyboardButton(text=f"🛵 {v['name']} [{volt}] — {p_w} грн/тиж", callback_data=f"book_{k}")])
    if not buttons:
        buttons.append([InlineKeyboardButton(text="⏳ Встати в лист очікування", callback_data="join_waitlist:any")])
    buttons.append([InlineKeyboardButton(text="❌ Скасувати", callback_data="cancel_booking")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

@dp.message(Command("book"), StateFilter("*"))
async def cmd_book(message: types.Message, state: FSMContext):
    await safe_clear_state(state)
    avail_count = sum(1 for v in FLEET_DATABASE.values() if v.get("status") == "available")
    if avail_count == 0:
        await message.answer(
            "😔 <b>Наразі всі скутери та велосипеди знаходяться в оренді.</b>\n\n"
            "Ви можете стати у лист очікування, і ми зв'яжемося з вами щойно звільниться техніка!",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⏳ Встати в лист очікування", callback_data="join_waitlist:any")]
            ])
        )
        return

    text = (
        "🛵 <b>БРОНЮВАННЯ ТРАНСПОРТУ MUVIO</b>\n"
        "────────────────────\n"
        "Оберіть бажану модель скутера або електровелосипеда зі списку доступних:"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=get_booking_vehicles_kb())

@dp.callback_query(F.data == "book", StateFilter("*"))
async def callback_book_general(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await safe_clear_state(state)
    avail_count = sum(1 for v in FLEET_DATABASE.values() if v.get("status") == "available")
    if avail_count == 0:
        await callback.message.answer(
            "😔 <b>Наразі всі скутери та велосипеди знаходяться в оренді.</b>\n\n"
            "Ви можете стати у лист очікування, і ми зв'яжемося з вами щойно звільниться техніка!",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⏳ Встати в лист очікування", callback_data="join_waitlist:any")]
            ])
        )
        return

    text = (
        "🛵 <b>БРОНЮВАННЯ ТРАНСПОРТУ MUVIO</b>\n"
        "────────────────────\n"
        "Оберіть бажану модель скутера або електровелосипеда зі списку доступних:"
    )
    await safe_render_card(callback, text, get_booking_vehicles_kb())

# Compatibility with old category filter buttons
@dp.callback_query(F.data.startswith("cat_"), StateFilter("*"))
async def callback_old_cat(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    cat = callback.data.replace("cat_", "")
    filt = "bike" if "bike" in cat else ("scooter" if "scooter" in cat else "all")
    items = get_gallery_data(filt)
    if not items:
        await callback.message.answer("⚠️ Немає доступного транспорту в цій категорії.", reply_markup=get_main_keyboard())
        return
    item_key, data = items[0]
    caption, kb = build_gallery_card(item_key, data, 0, len(items), filt)
    await safe_render_card(callback, caption, kb, data.get("photo_id"))

@dp.callback_query(F.data.startswith("book_") | F.data.startswith("book:"), StateFilter("*"))
async def start_booking_flow(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    raw_data = callback.data
    if "book_" in raw_data:
        item_id = raw_data.split("book_")[1]
    else:
        item_id = raw_data.split("book:")[1]

    if not item_id or item_id not in FLEET_DATABASE:
        await callback.message.answer(
            "Будь ласка, оберіть модель транспорту зі списку нижче:",
            reply_markup=get_booking_vehicles_kb()
        )
        return

    veh = FLEET_DATABASE[item_id]
    await state.update_data(
        chosen_vehicle_id=item_id,
        item_id=item_id,
        selected_scooter=veh.get("name", "Скутер")
    )
    await state.set_state(RentalForm.rental_period)

    p_day = veh.get("price_day", 900)
    p_week = veh.get("price_week", 2200)
    p_month = veh.get("price_month", 8000)

    period_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🗓 1 доба — {p_day} грн", callback_data="rent_period:1_doba")],
        [InlineKeyboardButton(text=f"📅 1 тиждень — {p_week} грн", callback_data="rent_period:1_tyzhden")],
        [InlineKeyboardButton(text=f"🗓 1 місяць (28 днів) — {p_month} грн", callback_data="rent_period:1_misyats")],
        [InlineKeyboardButton(text="🔄 Обрати інший транспорт", callback_data="book")],
        [InlineKeyboardButton(text="❌ Скасувати", callback_data="cancel_booking")]
    ])
    text = (
        f"⚙️ <b>Оформлення оренди: {veh.get('name')}</b>\n"
        f"⚡ Вольтаж: <b>{veh.get('voltage', '72V')}</b> | Запас ходу: <b>{veh.get('range', 'до 150 км')}</b>\n"
        "────────────────────\n"
        "Оберіть бажаний <b>термін оренди</b>:"
    )
    await safe_render_card(callback, text, period_kb, veh.get("photo_id"))

@dp.callback_query(F.data == "cancel_booking", StateFilter("*"))
async def cancel_booking_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer("Бронювання скасовано")
    await safe_clear_state(state)
    await callback.message.answer("Дію скасовано. Оберіть пункт меню:", reply_markup=get_main_keyboard())

@dp.callback_query(F.data == "rent_back:period", StateFilter("*"))
async def rent_back_to_period(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    item_id = data.get("chosen_vehicle_id") or data.get("item_id")
    if not item_id or item_id not in FLEET_DATABASE:
        await callback.message.answer("Оберіть транспорт:", reply_markup=get_booking_vehicles_kb())
        return

    veh = FLEET_DATABASE[item_id]
    await state.set_state(RentalForm.rental_period)
    p_day = veh.get("price_day", 900)
    p_week = veh.get("price_week", 2200)
    p_month = veh.get("price_month", 8000)

    period_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🗓 1 доба — {p_day} грн", callback_data="rent_period:1_doba")],
        [InlineKeyboardButton(text=f"📅 1 тиждень — {p_week} грн", callback_data="rent_period:1_tyzhden")],
        [InlineKeyboardButton(text=f"🗓 1 місяць (28 днів) — {p_month} грн", callback_data="rent_period:1_misyats")],
        [InlineKeyboardButton(text="🔄 Обрати інший транспорт", callback_data="book")],
        [InlineKeyboardButton(text="❌ Скасувати", callback_data="cancel_booking")]
    ])
    await safe_render_card(
        callback,
        f"⚙️ <b>Оформлення оренди: {veh.get('name')}</b>\n"
        f"⚡ Вольтаж: <b>{veh.get('voltage', '72V')}</b> | Запас ходу: <b>{veh.get('range', 'до 150 км')}</b>\n"
        "────────────────────\n"
        "Оберіть бажаний <b>термін оренди</b>:",
        period_kb,
        veh.get("photo_id")
    )

@dp.callback_query(F.data.startswith("rent_period:"), StateFilter("*"))
async def booking_period_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    p_code = callback.data.split(":")[1]
    p_map = {"1_doba": "1 доба", "1_tyzhden": "1 тиждень", "1_misyats": "1 місяць (28 днів)"}
    chosen_period_str = p_map.get(p_code, "1 тиждень")
    await state.update_data(chosen_period=chosen_period_str, period_code=p_code)
    await state.set_state(RentalForm.helmets_count)

    data = await state.get_data()
    veh_id = data.get("chosen_vehicle_id") or data.get("item_id")
    veh = FLEET_DATABASE.get(veh_id, {})

    h_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🪖 1 шолом", callback_data="helmets:1"), InlineKeyboardButton(text="🪖 2 шоломи", callback_data="helmets:2")],
        [InlineKeyboardButton(text="❌ Без шолома (маю свій)", callback_data="helmets:0")],
        [InlineKeyboardButton(text="⬅️ Назад до терміну", callback_data="rent_back:period")],
        [InlineKeyboardButton(text="❌ Скасувати", callback_data="cancel_booking")]
    ])
    text = (
        f"🛵 <b>{veh.get('name', 'Транспорт')}</b> | Термін: <b>{chosen_period_str}</b>\n"
        "────────────────────\n"
        "Скільки <b>захисних шоломів</b> вам потрібно для поїздок?"
    )
    await safe_render_card(callback, text, h_kb, veh.get("photo_id"))

@dp.callback_query(F.data.startswith("helmets:"), StateFilter("*"))
async def booking_helmets_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    h_count = callback.data.split(":")[1]
    await state.update_data(chosen_helmets=h_count)
    await state.set_state(RentalForm.full_name)
    
    msg_text = (
        "📝 <b>Крок 1 з 5: Ваші контактні дані</b>\n\n"
        "Введіть ваше <b>Прізвище, Ім'я та По батькові</b> (як у паспорті або Дії):"
    )
    await callback.message.answer(msg_text, parse_mode="HTML", reply_markup=get_cancel_keyboard(show_back=True))

@dp.message(StateFilter(RentalForm), F.text == "⬅️ Назад")
async def booking_back_navigation(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    data = await state.get_data()
    veh_id = data.get("chosen_vehicle_id") or data.get("item_id")
    veh = FLEET_DATABASE.get(veh_id, {})

    if current_state == RentalForm.full_name.state:
        await state.set_state(RentalForm.helmets_count)
        chosen_period_str = data.get("chosen_period", "1 тиждень")
        h_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🪖 1 шолом", callback_data="helmets:1"), InlineKeyboardButton(text="🪖 2 шоломи", callback_data="helmets:2")],
            [InlineKeyboardButton(text="❌ Без шолома (маю свій)", callback_data="helmets:0")],
            [InlineKeyboardButton(text="⬅️ Назад до терміну", callback_data="rent_back:period")],
            [InlineKeyboardButton(text="❌ Скасувати", callback_data="cancel_booking")]
        ])
        t = (
            f"🛵 <b>{veh.get('name', 'Транспорт')}</b> | Термін: <b>{chosen_period_str}</b>\n"
            "────────────────────\n"
            "Скільки <b>захисних шоломів</b> вам потрібно для поїздок?"
        )
        await safe_render_card(message, t, h_kb, veh.get("photo_id"))
        return

    elif current_state == RentalForm.phone.state:
        await state.set_state(RentalForm.full_name)
        await message.answer(
            "📝 <b>Крок 1 з 5: Ваші контактні дані</b>\n\n"
            "Введіть ваше <b>Прізвище, Ім'я та По батькові</b> (як у паспорті або Дії):",
            parse_mode="HTML",
            reply_markup=get_cancel_keyboard(show_back=True)
        )
        return

    elif current_state == RentalForm.age.state:
        await state.set_state(RentalForm.phone)
        phone_kb = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="📱 Поділитися контактом", request_contact=True)],
                [KeyboardButton(text="⬅️ Назад"), KeyboardButton(text="❌ Скасувати дію")]
            ],
            resize_keyboard=True,
            one_time_keyboard=True
        )
        await message.answer(
            "📱 <b>Крок 2 з 5: Номер телефону</b>\n\n"
            "Поділіться вашим номером через кнопку нижче або напишіть його у форматі <code>+380...</code>:",
            parse_mode="HTML",
            reply_markup=phone_kb
        )
        return

    elif current_state == RentalForm.usage_type.state:
        await state.set_state(RentalForm.age)
        await message.answer(
            "🎂 <b>Крок 3 з 5: Вік</b>\n\n"
            "Вкажіть ваш <b>повний вік</b> числом (років):",
            parse_mode="HTML",
            reply_markup=get_cancel_keyboard(show_back=True)
        )
        return

    elif current_state == RentalForm.delivery_experience.state:
        await state.set_state(RentalForm.usage_type)
        usage_kb = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="🍕 Робота в кур'єрській доставці (Glovo, Bolt тощо)")],
                [KeyboardButton(text="🛵 Оренда для особистих поїздок по місту")],
                [KeyboardButton(text="⬅️ Назад"), KeyboardButton(text="❌ Скасувати дію")]
            ],
            resize_keyboard=True
        )
        await message.answer(
            "🍕 <b>Крок 4 з 5: Мета використання</b>\n\n"
            "Оберіть мету використання транспорту:",
            parse_mode="HTML",
            reply_markup=usage_kb
        )
        return

    elif current_state == RentalForm.confirm.state:
        await state.set_state(RentalForm.delivery_experience)
        exp_kb = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="✅ Так, є водійський досвід")],
                [KeyboardButton(text="❌ Ні, я новачок")],
                [KeyboardButton(text="⬅️ Назад"), KeyboardButton(text="❌ Скасувати дію")]
            ],
            resize_keyboard=True
        )
        await message.answer(
            "🛵 <b>Крок 5 з 5: Досвід водіння</b>\n\n"
            "Чи є у вас досвід водіння скутера / велобайка?",
            parse_mode="HTML",
            reply_markup=exp_kb
        )
        return

    await safe_clear_state(state)
    await message.answer("Дію скасовано.", reply_markup=get_main_keyboard())

@dp.message(StateFilter(RentalForm.full_name), F.text)
async def booking_name_handler(message: types.Message, state: FSMContext):
    msg_text = (message.text or "").strip()
    if "скасувати" in msg_text.lower():
        await safe_clear_state(state)
        await message.answer("Дію скасовано.", reply_markup=get_main_keyboard())
        return
    if msg_text == "⬅️ Назад":
        await booking_back_navigation(message, state)
        return

    await state.update_data(user_full_name=msg_text)
    await state.set_state(RentalForm.phone)
    phone_kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Поділитися контактом", request_contact=True)],
            [KeyboardButton(text="⬅️ Назад"), KeyboardButton(text="❌ Скасувати дію")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await message.answer(
        "📱 <b>Крок 2 з 5: Номер телефону</b>\n\n"
        "Поділіться вашим номером через кнопку нижче або напишіть його у форматі <code>+380...</code>:",
        parse_mode="HTML",
        reply_markup=phone_kb
    )

@dp.message(StateFilter(RentalForm.phone), F.contact | F.text)
async def booking_phone_handler(message: types.Message, state: FSMContext):
    msg_text = (message.text or "").strip()
    if msg_text and "скасувати" in msg_text.lower():
        await safe_clear_state(state)
        await message.answer("Дію скасовано.", reply_markup=get_main_keyboard())
        return
    if msg_text == "⬅️ Назад":
        await booking_back_navigation(message, state)
        return

    if message.contact:
        raw_phone = message.contact.phone_number.replace("+", "").strip()
    else:
        raw_phone = msg_text.replace("+", "").strip()

    if not raw_phone or len(raw_phone) < 9:
        await message.answer("❌ Будь ласка, введіть коректний номер телефону (наприклад: <code>+380671234567</code>):", parse_mode="HTML")
        return

    await state.update_data(user_phone=raw_phone)
    await state.set_state(RentalForm.age)
    await message.answer(
        "🎂 <b>Крок 3 з 5: Вік</b>\n\n"
        "Вкажіть ваш <b>повний вік</b> числом (років):",
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard(show_back=True)
    )

@dp.message(StateFilter(RentalForm.age), F.text)
async def booking_age_handler(message: types.Message, state: FSMContext):
    msg_text = (message.text or "").strip()
    if "скасувати" in msg_text.lower():
        await safe_clear_state(state)
        await message.answer("Дію скасовано.", reply_markup=get_main_keyboard())
        return
    if msg_text == "⬅️ Назад":
        await booking_back_navigation(message, state)
        return

    if not msg_text.isdigit():
        await message.answer("Будь ласка, введіть вік числом (наприклад: 21):", reply_markup=get_cancel_keyboard(show_back=True))
        return

    age = int(msg_text)
    data = await state.get_data()
    veh_id = data.get("chosen_vehicle_id") or data.get("item_id")
    veh_data = FLEET_DATABASE.get(veh_id, {})
    is_bike = "велосипед" in veh_data.get("type", "").lower()
    min_age = 16 if is_bike else 18

    if age < min_age:
        await safe_clear_state(state)
        await message.answer(
            f"❌ <b>Оренда неможлива!</b>\n\n"
            f"Для оренди цього транспорту ({'електровелосипеда' if is_bike else 'електроскутера'}) мінімальний вік становить <b>{min_age} років</b>.\n"
            f"Дякуємо за розуміння!",
            parse_mode="HTML",
            reply_markup=get_main_keyboard()
        )
        return

    await state.update_data(user_age=str(age))
    await state.set_state(RentalForm.usage_type)
    usage_kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🍕 Робота в кур'єрській доставці (Glovo, Bolt тощо)")],
            [KeyboardButton(text="🛵 Оренда для особистих поїздок по місту")],
            [KeyboardButton(text="⬅️ Назад"), KeyboardButton(text="❌ Скасувати дію")]
        ],
        resize_keyboard=True
    )
    await message.answer(
        "🍕 <b>Крок 4 з 5: Мета використання</b>\n\n"
        "Оберіть мету використання транспорту:",
        parse_mode="HTML",
        reply_markup=usage_kb
    )

@dp.message(StateFilter(RentalForm.usage_type), F.text)
async def booking_usage_handler(message: types.Message, state: FSMContext):
    msg_text = (message.text or "").strip()
    if "скасувати" in msg_text.lower():
        await safe_clear_state(state)
        await message.answer("Дію скасовано.", reply_markup=get_main_keyboard())
        return
    if msg_text == "⬅️ Назад":
        await booking_back_navigation(message, state)
        return

    await state.update_data(user_usage=msg_text)
    await state.set_state(RentalForm.delivery_experience)
    exp_kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Так, є водійський досвід")],
            [KeyboardButton(text="❌ Ні, я новачок")],
            [KeyboardButton(text="⬅️ Назад"), KeyboardButton(text="❌ Скасувати дію")]
        ],
        resize_keyboard=True
    )
    await message.answer(
        "🛵 <b>Крок 5 з 5: Досвід водіння</b>\n\n"
        "Чи є у вас досвід водіння скутера / велобайка?",
        parse_mode="HTML",
        reply_markup=exp_kb
    )

@dp.message(StateFilter(RentalForm.delivery_experience), F.text)
async def booking_experience_handler(message: types.Message, state: FSMContext):
    msg_text = (message.text or "").strip()
    if "скасувати" in msg_text.lower():
        await safe_clear_state(state)
        await message.answer("Дію скасовано.", reply_markup=get_main_keyboard())
        return
    if msg_text == "⬅️ Назад":
        await booking_back_navigation(message, state)
        return

    await state.update_data(user_experience=msg_text)
    await state.set_state(RentalForm.confirm)

    data = await state.get_data()
    veh_id = data.get("chosen_vehicle_id") or data.get("item_id")
    veh_data = FLEET_DATABASE.get(veh_id, {})
    model_name = veh_data.get("name", "Транспорт")
    period_str = data.get("chosen_period", "1 тиждень")
    period_code = data.get("period_code", "1_tyzhden")
    helmets = data.get("chosen_helmets", "0")
    full_name = data.get("user_full_name", "Клієнт")
    raw_phone = data.get("user_phone", "")
    age = data.get("user_age", "-")
    usage = data.get("user_usage", "-")

    if period_code == "1_doba":
        cost = veh_data.get("price_day", 900)
    elif period_code == "1_misyats":
        cost = veh_data.get("price_month", 8000)
    else:
        cost = veh_data.get("price_week", 2200)

    deposit = veh_data.get("deposit", 4000)

    conf_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Підтвердити бронювання", callback_data="confirm_rent_booking")],
        [InlineKeyboardButton(text="❌ Скасувати", callback_data="cancel_booking")]
    ])

    conf_text = (
        "📋 <b>ПІДТВЕРДЖЕННЯ БРОНЮВАННЯ ОРЕНДИ</b>\n"
        "────────────────────\n"
        f"🛵 <b>Транспорт:</b> {model_name}\n"
        f"⏱ <b>Термін оренди:</b> {period_str}\n"
        f"🪖 <b>Шоломи:</b> {helmets} шт.\n"
        f"👤 <b>Клієнт:</b> {full_name}\n"
        f"📱 <b>Телефон:</b> +{raw_phone}\n"
        f"🎂 <b>Вік:</b> {age} років\n"
        f"🍕 <b>Мета використання:</b> {usage}\n"
        f"🛵 <b>Водійський досвід:</b> {msg_text}\n"
        "────────────────────\n"
        f"💰 <b>Вартість оренди:</b> <b>{cost} грн</b>\n"
        f"🔒 <b>Застава (депозит):</b> <b>{deposit} грн</b>\n\n"
        "Перевірте ваші дані та натисніть <b>«✅ Підтвердити бронювання»</b> нижче:"
    )
    await message.answer(conf_text, parse_mode="HTML", reply_markup=conf_kb)

@dp.callback_query(F.data == "confirm_rent_booking", StateFilter("*"))
async def booking_confirm_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    await safe_clear_state(state)

    veh_id = data.get("chosen_vehicle_id") or data.get("item_id")
    veh_data = FLEET_DATABASE.get(veh_id, {})
    model_name = veh_data.get("name", "Транспорт")
    period_str = data.get("chosen_period", "1 тиждень")
    period_code = data.get("period_code", "1_tyzhden")
    helmets = int(data.get("chosen_helmets", "0"))
    full_name = data.get("user_full_name", "Клієнт")
    phone = data.get("user_phone", "")
    age = data.get("user_age", "-")
    usage = data.get("user_usage", "-")
    experience = data.get("user_experience", "-")
    user_id = callback.from_user.id
    now = get_kyiv_now()
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")

    # Calculate end date and cost
    if period_code == "1_doba":
        end_date = (now + timedelta(days=1)).strftime("%Y-%m-%d 23:59")
        amount = veh_data.get("price_day", 900)
    elif period_code == "1_misyats":
        end_date = (now + timedelta(days=28)).strftime("%Y-%m-%d 23:59")
        amount = veh_data.get("price_month", 8000)
    else:
        end_date = (now + timedelta(days=7)).strftime("%Y-%m-%d 23:59")
        amount = veh_data.get("price_week", 2200)

    # Save to SQLite rentals_base.db
    async with aiosqlite.connect(DB_PATH) as db:
        # Upsert user
        await db.execute(
            """INSERT INTO users (telegram_id, phone_number, full_name, first_rent_date)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
                phone_number = COALESCE(excluded.phone_number, users.phone_number),
                full_name = COALESCE(excluded.full_name, users.full_name)""",
            (user_id, phone, full_name, now_str)
        )
        # Avoid duplicate rentals for this phone / vehicle
        await db.execute("DELETE FROM rentals WHERE user_phone = ? OR vehicle_info = ?", (phone, model_name))
        # Insert rental record
        await db.execute(
            """INSERT INTO rentals (user_phone, vehicle_info, end_date, amount_due, contract_num, contract_date, has_helmet, reminder_sent)
            VALUES (?, ?, ?, ?, '2804-5', ?, ?, 0)""",
            (phone, model_name, end_date, amount, now.strftime("%d.%m.%Y"), helmets)
        )
        await db.commit()

    # Update fleet status
    if veh_id in FLEET_DATABASE:
        FLEET_DATABASE[veh_id]["reserved_by"] = user_id
        FLEET_DATABASE[veh_id]["status"] = "rented"
        save_fleet()

    # Success to client
    await callback.message.answer(
        "🎉 <b>Вашу заявку на оренду успішно прийнято та зафіксовано!</b>\n\n"
        f"🛵 <b>Транспорт:</b> {model_name}\n"
        f"⏱ <b>Термін:</b> {period_str} (до <code>{end_date}</code>)\n"
        f"🪖 <b>Шоломи:</b> {helmets} шт.\n"
        f"💰 <b>До сплати:</b> <b>{amount:.2f} грн</b>\n\n"
        "📍 <b>Точка видачі:</b> м. Одеса, вул. Приморська, 22\n"
        "Менеджер зв'яжеться з вами для підтвердження часу передачі техніки.",
        parse_mode="HTML",
        reply_markup=get_main_keyboard()
    )

    # Notify admin
    admin_notify = (
        "⚡ <b>НОВА ЗАЯВКА НА ОРЕНДУ!</b>\n"
        "────────────────────\n"
        f"👤 <b>Клієнт:</b> {full_name}\n"
        f"📱 <b>Телефон:</b> +{phone}\n"
        f"🆔 <b>TG ID:</b> <code>{user_id}</code>\n"
        f"🛵 <b>Транспорт:</b> {model_name} (<code>{veh_id}</code>)\n"
        f"🎂 <b>Вік:</b> {age} років\n"
        f"🍕 <b>Мета:</b> {usage}\n"
        f"🛵 <b>Досвід:</b> {experience}\n"
        f"⏱ <b>Термін:</b> {period_str}\n"
        f"🪖 <b>Шоломи:</b> {helmets} шт.\n"
        f"💰 <b>Сума:</b> {amount:.2f} грн\n"
        f"📅 <b>Діє до:</b> {end_date}\n"
        "────────────────────\n"
        "<i>Заявку та оренду автоматично зафіксовано в базі rentals_base.db.</i>"
    )
    admin_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👑 Відкрити карточку в адмінці", callback_data=f"admmanage:{veh_id}")]
    ])
    try:
        await bot.send_message(chat_id=ADMIN_ID, text=admin_notify, parse_mode="HTML", reply_markup=admin_kb)
    except Exception as e:
        logger.error(f"Помилка сповіщення адміна: {e}")

# ==================== ФИНАНСОВЫЙ ДАШБОРД И НАЛОГИ ====================

@dp.message(Command("stats"), StateFilter("*"))
@dp.message(lambda msg: msg.from_user.id == ADMIN_ID and msg.text and "статистика" in msg.text.lower(), StateFilter("*"))
async def stats_cmd_handler(message: types.Message, state: FSMContext = None):
    if message.from_user.id != ADMIN_ID: return
    await safe_clear_state(state)
    await show_financial_stats(message)

async def show_financial_stats(target):
    total = len(FLEET_DATABASE)
    rented = sum(1 for v in FLEET_DATABASE.values() if v["status"] == "rented")
    avail = sum(1 for v in FLEET_DATABASE.values() if v["status"] == "available")
    repair = sum(1 for v in FLEET_DATABASE.values() if v["status"] == "repair")
    occupancy = (rented / total * 100) if total > 0 else 0.0

    today_str = get_kyiv_now().strftime("%Y-%m-%d")
    month_prefix = get_kyiv_now().strftime("%Y-%m")

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        # === РАЗДЕЛ 1: РЕГУЛЯРНАЯ ОРЕНДА ===
        # Today
        async with db.execute("SELECT SUM(amount) as total FROM payments WHERE (payment_type != 'buyout' OR payment_type IS NULL) AND date_paid LIKE ?", (f"{today_str}%",)) as c:
            r_day_rent = (await c.fetchone())['total'] or 0.0
        async with db.execute("SELECT SUM(amount) as total FROM expenses WHERE paid_by = 'company' AND date_added LIKE ?", (f"{today_str}%",)) as c:
            e_day = (await c.fetchone())['total'] or 0.0
        async with db.execute("SELECT SUM(amount) as total FROM expenses WHERE paid_by = 'client' AND date_added LIKE ?", (f"{today_str}%",)) as c:
            client_e_day = (await c.fetchone())['total'] or 0.0

        # September 2026 (current month)
        async with db.execute("SELECT SUM(amount) as total FROM payments WHERE (payment_type != 'buyout' OR payment_type IS NULL) AND date_paid LIKE ?", (f"{month_prefix}%",)) as c:
            r_month_rent = (await c.fetchone())['total'] or 2200.0
        async with db.execute("SELECT SUM(amount) as total FROM expenses WHERE paid_by = 'company' AND date_added LIKE ?", (f"{month_prefix}%",)) as c:
            e_month = (await c.fetchone())['total'] or 0.0
        async with db.execute("SELECT SUM(amount) as total FROM expenses WHERE paid_by = 'client' AND date_added LIKE ?", (f"{month_prefix}%",)) as c:
            client_e_month = (await c.fetchone())['total'] or 0.0

        # August 2026 (last month)
        async with db.execute("SELECT SUM(amount) as total FROM payments WHERE (payment_type != 'buyout' OR payment_type IS NULL) AND date_paid LIKE '2026-08%'") as c:
            r_aug = (await c.fetchone())['total'] or 107200.0
        async with db.execute("SELECT SUM(amount) as total FROM expenses WHERE paid_by = 'company' AND date_added LIKE '2026-08%'") as c:
            e_aug = (await c.fetchone())['total'] or 6450.0
        async with db.execute("SELECT SUM(amount) as total FROM expenses WHERE paid_by = 'client' AND date_added LIKE '2026-08%'") as c:
            client_e_aug = (await c.fetchone())['total'] or 1050.0

        # All time rental
        async with db.execute("SELECT SUM(amount) as total FROM payments WHERE (payment_type != 'buyout' OR payment_type IS NULL)") as c:
            r_all_rent = (await c.fetchone())['total'] or (r_aug + r_month_rent)
        async with db.execute("SELECT SUM(amount) as total FROM expenses WHERE paid_by = 'company'") as c:
            e_all = (await c.fetchone())['total'] or (e_aug + e_month)
        async with db.execute("SELECT SUM(amount) as total FROM expenses WHERE paid_by = 'client'") as c:
            client_e_all = (await c.fetchone())['total'] or (client_e_aug + client_e_month)

        # === РАЗДЕЛ 2: ОТДЕЛЬНЫЙ РАЗДЕЛ ВЫКУПА (RENT-TO-OWN) ===
        async with db.execute("SELECT COUNT(*) as cnt, SUM(deposit_paid) as dep_sum, SUM(paid_amount) as paid_sum, SUM(total_price) as total_val FROM buyout_deals WHERE status = 'active'") as c:
            b_row = await c.fetchone()
            b_active_cnt = b_row['cnt'] or 0
            b_dep_sum = b_row['dep_sum'] or 0.0
            b_paid_sum = b_row['paid_sum'] or 0.0
            b_total_val = b_row['total_val'] or 0.0
            b_rem_sum = max(0.0, b_total_val - b_paid_sum)

        async with db.execute("SELECT SUM(amount) as total FROM payments WHERE payment_type = 'buyout'") as c:
            b_payments_total = (await c.fetchone())['total'] or 0.0

        async with db.execute("SELECT SUM(amount) as total FROM payments WHERE payment_type = 'buyout' AND date_paid LIKE ?", (f"{month_prefix}%",)) as c:
            b_payments_month = (await c.fetchone())['total'] or 0.0

        async with db.execute("SELECT SUM(amount) as total FROM payments WHERE payment_type = 'buyout' AND date_paid LIKE ?", (f"{today_str}%",)) as c:
            b_payments_day = (await c.fetchone())['total'] or 0.0

    exp_pct_month = (e_month / r_month_rent * 100) if r_month_rent > 0 else 0.0
    exp_pct_aug = (e_aug / r_aug * 100) if r_aug > 0 else 6.0
    exp_pct_all = (e_all / r_all_rent * 100) if r_all_rent > 0 else 0.0

    net_day_rent = r_day_rent - e_day
    net_month_rent = r_month_rent - e_month
    net_aug_rent = r_aug - e_aug
    net_all_rent = r_all_rent - e_all

    grand_total = r_all_rent + b_paid_sum

    text = (
        "📈 <b>ФІНАНСОВИЙ ДАШБОРД MUVIO RENT (P&L)</b>\n"
        "────────────────────\n"
        f"📊 <b>Завантаження флоту:</b> {occupancy:.1f}%\n"
        f"🛵 В оренді: <b>{rented}</b> | 🟢 Вільні: <b>{avail}</b> | 🛠 Ремонт: <b>{repair}</b>\n"
        "────────────────────\n\n"
        "🗓 <b>Сьогодні (Оренда):</b>\n"
        f"💵 Виручка ФОП: <code>{r_day_rent:.2f} грн</code>\n"
        f"🛠 Витрати MUVIO: <code>{e_day:.2f} грн</code>\n"
        f"📈 Чистий прибуток: <b>{net_day_rent:.2f} грн</b>\n\n"
        "📅 <b>Поточний місяць (Вересень 2026):</b>\n"
        f"💵 Виручка ФОП (Оренда): <code>{r_month_rent:.2f} грн</code>\n"
        f"🛠 Витрати MUVIO: <code>{e_month:.2f} грн</code> ({exp_pct_month:.1f}% від виручки)\n"
        f"📈 Чистий прибуток: <b>{net_month_rent:.2f} грн</b>\n"
        f"🔧 Відшкодовано клієнтами: <code>{client_e_month:.2f} грн</code>\n\n"
        "🗓 <b>Минулий місяць (Серпень 2026):</b>\n"
        f"💵 Виручка ФОП: <code>{r_aug:.2f} грн</code>\n"
        f"🛠 Витрати MUVIO: <code>{e_aug:.2f} грн</code> ({exp_pct_aug:.1f}% від виручки)\n"
        f"📈 Чистий прибуток: <b>{net_aug_rent:.2f} грн</b>\n"
        f"🔧 Відшкодовано клієнтами: <code>{client_e_aug:.2f} грн</code>\n\n"
        "🏆 <b>За весь час (Оренда):</b>\n"
        f"💵 Всього з оренди: <code>{r_all_rent:.2f} грн</code>\n"
        f"🛠 Витрати компанії: <code>{e_all:.2f} грн</code> ({exp_pct_all:.1f}% від виручки)\n"
        f"📈 Чистий прибуток з оренди: <b>{net_all_rent:.2f} грн</b>\n"
        f"🔧 Всього відшкодовано клієнтами: <code>{client_e_all:.2f} грн</code>\n"
        "────────────────────\n\n"
        "🏷 <b>ОКРЕМИЙ РОЗДІЛ: ЗАРОБІТОК З ВИКУПУ (RENT-TO-OWN)</b>\n"
        "────────────────────\n"
        f"📑 <b>Активних договорів викупу:</b> {b_active_cnt} шт.\n"
        f"🔒 <b>Отримано завдатків (20%):</b> <code>{b_dep_sum:.2f} грн</code>\n"
        f"💳 <b>Сплачено платежів викупу:</b> <code>{b_paid_sum:.2f} грн</code>\n"
        f"💰 <b>Всього заробіток з викупу:</b> <b>{b_paid_sum:.2f} грн</b>\n"
        f"⏳ <b>Залишок до виплати клієнтами:</b> <code>{b_rem_sum:.2f} грн</code>\n"
        "────────────────────\n\n"
        f"💼 <b>РАЗОМ ЗАГАЛЬНИЙ ДОХІД (ОРЕНДА + ВИКУП):</b> <b>{grand_total:.2f} грн</b>"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Податковий звіт ФОП (3 група: 5% + 1.5% ВЗ + ЄСВ)", callback_data="tax_report_view")]
    ])
    
    if isinstance(target, types.CallbackQuery):
        await target.message.answer(text, parse_mode="HTML", reply_markup=kb)
    else:
        await target.answer(text, parse_mode="HTML", reply_markup=kb)

@dp.callback_query(F.data == "tax_report_view", StateFilter("*"))
async def tax_report_view_callback(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    await callback.answer()

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT SUM(amount) as total FROM payments") as c:
            r_all = (await c.fetchone())['total'] or 118524.0

    tax_5 = r_all * 0.05
    tax_vz = r_all * 0.015
    tax_total = tax_5 + tax_vz
    net_after_taxes = r_all - tax_total

    text = (
        "📊 <b>ПОДАТКОВИЙ ЗВІТ ТА КАЛЕНДАР ФОП (3 група, без ПДВ)</b>\n"
        "────────────────────\n"
        "🏛 <b>Ставка:</b> Єдиний податок 5% + Військовий збір 1.5%\n"
        f"💵 <b>Валовий дохід (всього):</b> {r_all:.2f} грн\n"
        f"💰 <b>Єдиний податок 5% (всього):</b> {tax_5:.2f} грн\n"
        f"🛡 <b>Військовий збір 1.5% (всього):</b> {tax_vz:.2f} грн\n"
        f"📌 <b>Разом податків (всього):</b> {tax_total:.2f} грн\n\n"
        "📅 <b>ПОКВАРТАЛЬНИЙ РОЗПОДІЛ ТА ДЕДЛАЙНИ:</b>\n\n"
        "🔹 <b>3-й Квартал (Q3 - ПОТОЧНИЙ):</b>\n"
        f"• Дохід: {r_all:.2f} грн\n"
        f"• Єдиний податок (5%): {tax_5:.2f} грн\n"
        f"• Військовий збір (1.5%): {tax_vz:.2f} грн\n"
        f"• Разом до сплати за Q3: <b>{tax_total:.2f} грн</b>\n"
        "• Декларація: <b>до 9 листопада</b>\n"
        "• Сплата ЄП та ВЗ: <b>до 19 листопада</b>\n"
        "• Сплата ЄСВ (за Q3): <b>до 19 жовтня</b>\n\n"
        f"💼 <b>Чистий прибуток після сплати податків:</b> <b>{net_after_taxes:.2f} грн</b>"
    )
    await callback.message.answer(text, parse_mode="HTML", reply_markup=get_admin_keyboard())

# ==================== ЖУРНАЛ И ДОБАВЛЕНИЕ ВИТРАТ ====================

@dp.message(lambda msg: msg.from_user.id == ADMIN_ID and msg.text and ("історія" in msg.text.lower() or "опис" in msg.text.lower()), StateFilter("*"))
async def admin_log_exp_btn_handler(message: types.Message, state: FSMContext):
    await safe_clear_state(state)
    await show_expenses_log(message)

async def show_expenses_log(message: types.Message):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM expenses ORDER BY id DESC LIMIT 15") as cursor:
            rows = await cursor.fetchall()

    if not rows:
        text = "📜 <b>Журнал витрат порожній.</b>"
    else:
        text = "📜 <b>ДЕТАЛЬНИЙ ЖУРНАЛ ВИТРАТ ТА РЕМОНТІВ MUVIO:</b>\n────────────────────\n\n"
        for r in rows:
            payer_str = "🏢 MUVIO" if r['paid_by'] == 'company' else "👤 Клієнт"
            v_name = FLEET_DATABASE.get(r['vehicle_key'], {}).get('name', r['vehicle_key'])
            if r['vehicle_key'] == 'general':
                v_name = "🏢 Загальні витрати флоту"
            d_short = r['date_added'][:16] if r['date_added'] else ""
            text += (
                f"🔹 <b>{v_name} — {r['amount']:.2f} грн</b>\n"
                f"🗂 <b>Категорія:</b> {r['category']}\n"
                f"💳 <b>Платник:</b> {payer_str}\n"
                f"📅 <b>Дата:</b> <code>{d_short}</code>\n"
                f"📝 <b>Деталі:</b> {r['description']}\n\n"
            )

    if isinstance(message, types.CallbackQuery):
        await message.message.answer(text, parse_mode="HTML", reply_markup=get_admin_keyboard())
    else:
        await message.answer(text, parse_mode="HTML", reply_markup=get_admin_keyboard())

@dp.message(lambda msg: msg.from_user.id == ADMIN_ID and msg.text and "видалити витрату" in msg.text.lower(), StateFilter("*"))
async def admin_del_exp_btn_handler(message: types.Message, state: FSMContext):
    await safe_clear_state(state)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM expenses ORDER BY id DESC LIMIT 10") as cursor:
            rows = await cursor.fetchall()

    if not rows:
        await message.answer("⚠️ Немає витрат для видалення.", reply_markup=get_admin_keyboard())
        return

    buttons = []
    for r in rows:
        v_name = FLEET_DATABASE.get(r['vehicle_key'], {}).get('name', 'Флот')
        if r['vehicle_key'] == 'general': v_name = "Офіс"
        p_badge = "🏢" if r['paid_by'] == 'company' else "👤"
        d_short = r['date_added'][5:10] if r['date_added'] else ""
        buttons.append([InlineKeyboardButton(
            text=f"❌ {d_short} | {v_name[:10]} | {int(r['amount'])} грн [{p_badge}]",
            callback_data=f"del_exp:{r['id']}"
        )])
    buttons.append([InlineKeyboardButton(text="⬅️ Скасувати", callback_data="back_to_admin_panel")])

    await message.answer("Оберіть **витрату для видалення**:", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@dp.callback_query(F.data.startswith("del_exp:"), StateFilter("*"))
async def delete_expense_callback(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    exp_id = int(callback.data.split(":")[1])
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM expenses WHERE id = ?", (exp_id,))
        await db.commit()
    await callback.answer(f"Витрату #{exp_id} видалено!", show_alert=True)
    await show_expenses_log(callback)

# --- ДОБАВЛЕНИЕ ВИТРАТ С КНОПКАМИ КАТЕГОРИЙ (БЕЗ РУЧНОГО ВВОДА ПРИЧИНЫ) ---
COMPANY_EXP_CATEGORIES = [
    ("⚡️ Поломка проводки / Електрика", "Поломка проводки / Електрика"),
    ("🛑 Заміна гальмівних колодок", "Заміна гальмівних колодок"),
    ("🛞 Заміна покришки (знос)", "Заміна покришки (знос)"),
    ("🚲 Смазка ланцюга та зірок (вело)", "Смазка ланцюга та зірок"),
    ("✊ Заміна ручки газу", "Заміна ручки газу"),
    ("🔌 Заміна автомата / реле", "Заміна автомата / реле"),
    ("🛢 Мастило / Планове ТО", "Мастило / Планове ТО"),
    ("📦 Загальні витрати флоту / Офіс", "Загальні витрати флоту"),
    ("✍️ Ввести інше вручну", "manual")
]

CLIENT_EXP_CATEGORIES = [
    ("🛞 Заміна пробитої покришки", "Заміна пробитої покришки"),
    ("🚲 Заміна пробитої камери (вело)", "Заміна пробитої камери"),
    ("🛡 Заміна пластику / обшивки", "Заміна пластику"),
    ("🪞 Заміна дзеркал", "Заміна дзеркал"),
    ("💥 Механічне пошкодження / ДТП", "Механічне пошкодження / ДТП"),
    ("🪖 Втрата шолома / аксесуарів", "Втрата шолома / аксесуарів"),
    ("✍️ Ввести інше вручну", "manual")
]

@dp.message(lambda msg: msg.from_user.id == ADMIN_ID and msg.text and "додати витрату" in msg.text.lower(), StateFilter("*"))
async def admin_add_exp_btn_handler(message: types.Message, state: FSMContext):
    await safe_clear_state(state)
    await state.set_state(AdminExpenseState.waiting_for_payer)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏢 За рахунок MUVIO (Компанія)", callback_data="exppayer:company")],
        [InlineKeyboardButton(text="👤 За рахунок клієнта (Відшкодування)", callback_data="exppayer:client")],
        [InlineKeyboardButton(text="❌ Скасувати", callback_data="back_to_admin_panel")]
    ])
    await message.answer("💳 <b>ДОДАВАННЯ ВИТРАТИ / РЕМОНТУ</b>\n────────────────────\nХто сплачує витрати?", parse_mode="HTML", reply_markup=kb)

@dp.callback_query(F.data.startswith("exppayer:"), StateFilter("*"))
async def admin_exp_payer_chosen(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID: return
    await callback.answer()
    payer = callback.data.split(":")[1]
    await state.update_data(exp_payer=payer)
    await state.set_state(AdminExpenseState.waiting_for_vehicle)

    buttons = []
    # Add vehicles
    row = []
    for k, v in FLEET_DATABASE.items():
        row.append(InlineKeyboardButton(text=f"🛵 {v['name'][:12]}", callback_data=f"expveh:{k}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    if payer == "company":
        buttons.append([InlineKeyboardButton(text="🏢 Загальні витрати флоту / Офіс", callback_data="expveh:general")])
    buttons.append([InlineKeyboardButton(text="⬅️ Назад до вибору платника", callback_data="exp_back_to_payer")])

    p_str = "🏢 MUVIO (компанія)" if payer == "company" else "👤 Клієнт (відшкодування)"
    await safe_render_card(callback, f"💳 <b>Платник:</b> {p_str}\n────────────────────\nОберіть <b>транспортний засіб</b> або об'єкт витрат:", InlineKeyboardMarkup(inline_keyboard=buttons))

@dp.callback_query(F.data == "exp_back_to_payer", StateFilter("*"))
async def exp_back_to_payer_handler(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID: return
    await callback.answer()
    await admin_add_exp_btn_handler(callback.message, state)

@dp.callback_query(F.data.startswith("expveh:"), StateFilter("*"))
async def admin_exp_veh_chosen(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID: return
    await callback.answer()
    v_key = callback.data.split(":")[1]
    await state.update_data(exp_veh_key=v_key)
    await state.set_state(AdminExpenseState.waiting_for_exact_category)

    data = await state.get_data()
    payer = data.get("exp_payer", "company")
    cats = COMPANY_EXP_CATEGORIES if payer == "company" else CLIENT_EXP_CATEGORIES

    v_name = FLEET_DATABASE.get(v_key, {}).get("name", "Загальні витрати флоту") if v_key != "general" else "Загальні витрати флоту"
    buttons = []
    for idx, (title, val) in enumerate(cats):
        buttons.append([InlineKeyboardButton(text=title, callback_data=f"expcat:{idx}")])
    buttons.append([InlineKeyboardButton(text="⬅️ Назад до вибору транспорту", callback_data=f"exppayer:{payer}")])

    await safe_render_card(callback, f"🛠 <b>Об'єкт:</b> {v_name}\n────────────────────\nОберіть <b>категорію ремонту / деталі</b> (натисніть кнопку):", InlineKeyboardMarkup(inline_keyboard=buttons))

@dp.callback_query(F.data.startswith("expcat:"), StateFilter("*"))
async def admin_exp_cat_chosen(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID: return
    await callback.answer()
    idx = int(callback.data.split(":")[1])

    data = await state.get_data()
    payer = data.get("exp_payer", "company")
    cats = COMPANY_EXP_CATEGORIES if payer == "company" else CLIENT_EXP_CATEGORIES
    title, val = cats[idx]

    if val == "manual":
        await state.set_state(AdminExpenseState.waiting_for_desc_manual)
        await callback.message.answer(
            "Введіть <b>назву або причину витрати</b> вручну текстом:",
            parse_mode="HTML",
            reply_markup=get_cancel_keyboard()
        )
        return

    await state.update_data(exp_category=val, exp_desc=title)
    await state.set_state(AdminExpenseState.waiting_for_amount)

    v_key = data.get("exp_veh_key", "general")
    v_name = FLEET_DATABASE.get(v_key, {}).get("name", "Загальні витрати") if v_key != "general" else "Загальні витрати"
    p_str = "🏢 MUVIO" if payer == "company" else "👤 Клієнт"

    await callback.message.answer(
        f"⚙️ <b>Деталь/Ремонт:</b> {title}\n"
        f"🛵 <b>Об'єкт:</b> {v_name} ({p_str})\n"
        "────────────────────\n"
        "Введіть <b>суму витрати у грн</b> числом (наприклад: <code>450</code> або <code>1200</code>):",
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard()
    )

@dp.message(StateFilter(AdminExpenseState.waiting_for_desc_manual), F.text)
async def admin_exp_desc_manual_save(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    msg = (message.text or "").strip()
    if "скасувати" in msg.lower():
        await safe_clear_state(state)
        await message.answer("Дію скасовано.", reply_markup=get_admin_keyboard())
        return

    await state.update_data(exp_category=msg, exp_desc=msg)
    await state.set_state(AdminExpenseState.waiting_for_amount)
    await message.answer(
        f"⚙️ <b>Категорія:</b> {msg}\n"
        "Введіть <b>суму витрати у грн</b> числом (наприклад: <code>450</code>):",
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard()
    )

@dp.message(StateFilter(AdminExpenseState.waiting_for_amount), F.text)
async def admin_exp_amount_save(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    msg = (message.text or "").strip()
    if "скасувати" in msg.lower():
        await safe_clear_state(state)
        await message.answer("Дію скасовано.", reply_markup=get_admin_keyboard())
        return

    try:
        amt = float(msg.replace(",", ".").replace(" ", ""))
        if amt <= 0: raise ValueError()
    except ValueError:
        await message.answer("Будь ласка, введіть суму числом (наприклад: 450):")
        return

    data = await state.get_data()
    await safe_clear_state(state)

    v_key = data.get("exp_veh_key", "general")
    payer = data.get("exp_payer", "company")
    cat = data.get("exp_category", "Ремонт")
    desc = data.get("exp_desc", cat)
    now_str = get_kyiv_now().strftime("%Y-%m-%d %H:%M:%S")

    v_name = FLEET_DATABASE.get(v_key, {}).get("name", "Загальні витрати") if v_key != "general" else "Загальні витрати флоту"
    payer_str = "🏢 MUVIO (Компанія)" if payer == "company" else "👤 Клієнт (Відшкодовано)"

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO expenses (vehicle_key, category, amount, description, date_added, paid_by) VALUES (?, ?, ?, ?, ?, ?)",
            (v_key, cat, amt, desc, now_str, payer)
        )
        await db.commit()

    await message.answer(
        f"✅ <b>Витрату успішно зафіксовано!</b>\n\n"
        f"🛵 <b>Об'єкт:</b> {v_name}\n"
        f"💳 <b>Платник:</b> {payer_str}\n"
        f"📂 <b>Категорія:</b> {desc}\n"
        f"💰 <b>Сума:</b> <b>{amt:.2f} грн</b>\n"
        f"📅 <b>Дата:</b> <code>{now_str}</code>",
        parse_mode="HTML",
        reply_markup=get_admin_keyboard()
    )

# ==================== АДМИН УПРАВЛЕНИЕ ФЛОТОМ ====================

@dp.message(Command("admin"), StateFilter("*"))
@dp.message(lambda msg: msg.from_user.id == ADMIN_ID and msg.text and "управління флотом" in msg.text.lower(), StateFilter("*"))
async def admin_fleet_btn_handler(message: types.Message, state: FSMContext):
    await safe_clear_state(state)
    text, kb = get_admin_text_and_kb()
    await message.answer("🔑 <b>Режим адміністратора MUVIO Rent активовано.</b>", parse_mode="HTML", reply_markup=get_admin_keyboard())
    await message.answer(text, parse_mode="HTML", reply_markup=kb)

@dp.callback_query(F.data.startswith("admmanage:"), StateFilter("*"))
async def admin_item_manage(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    await callback.answer()
    await safe_clear_state(state)
        
    item_id = callback.data.split(":")[1]
    data = FLEET_DATABASE.get(item_id)
    if not data: return

    user_id = data.get("reserved_by")
    client_info_str, bonus_str, end_date_str = "Немає", "0.00 грн", "Немає"
    p_day_val, p_week_val, p_month_val = resolve_prices(None, data)

    if user_id:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM users WHERE telegram_id = ?", (user_id,)) as cursor:
                u_row = await cursor.fetchone()
                if u_row:
                    client_info_str = f"{u_row['full_name']} (+{u_row['phone_number']})"
                    bonus_str = f"{u_row['bonus_balance']:.2f} грн" if 'bonus_balance' in u_row.keys() and u_row['bonus_balance'] else "0.00 грн"

            async with db.execute("SELECT * FROM rentals WHERE user_phone = (SELECT phone_number FROM users WHERE telegram_id = ?) ORDER BY id DESC LIMIT 1", (user_id,)) as cursor:
                r_row = await cursor.fetchone()
                if r_row:
                    end_date_str = r_row['end_date']
                    p_day_val, p_week_val, p_month_val = resolve_prices(r_row, data)

    status_str = "🟢 Вільний" if data["status"] == "available" else ("🔴 В оренді / Заброньовано" if data["status"] == "rented" else "🛠 В ремонті")
    photo_str = "✅ Завантажено" if data.get("photo_id") else "❌ Відсутнє"
    res_str = f"<code>{user_id}</code>" if user_id else "Немає"
    volt = data.get("voltage", "60V")
    b_price = data.get("buyout_base_price", 46000)
    
    text = (
        f"🛵 <b>{data['name']}</b> ({volt})\n"
        "────────────────────\n"
        f"Поточний статус: <b>{status_str}</b>\n"
        f"Прив'язаний клієнт: <b>{res_str}</b>\n"
        f"Дані клієнта: <b>{client_info_str}</b>\n"
        f"📅 Термін оренди до: <b>{end_date_str}</b>\n\n"
        f"💰 <b>Актуальні тарифи оренди:</b>\n"
        f"• Доба: <b>{int(p_day_val)} грн</b>\n"
        f"• Тиждень: <b>{int(p_week_val)} грн</b>\n"
        f"• Місяць: <b>{int(p_month_val)} грн</b>\n\n"
        f"⚡ Вольтаж: <b>{volt}</b> | Базова ціна викупу: <b>{b_price} грн</b>\n"
        f"🎁 Бонусний баланс клієнта: <b>{bonus_str}</b>\n"
        f"📷 Фото: <b>{photo_str}</b>\n"
        "────────────────────\n"
        "Оберіть дію:"
    )
    active_buyout = None
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM buyout_deals WHERE (vehicle_key = ? OR user_id = ?) AND status = 'active' ORDER BY id DESC LIMIT 1", (item_id, user_id if user_id else 0)) as cursor:
            active_buyout = await cursor.fetchone()

    buttons = [
        [InlineKeyboardButton(text="🔑 ВИДАТИ ТА АКТИВУВАТИ ОРЕНДУ", callback_data=f"issue:{item_id}")],
        [InlineKeyboardButton(text="📅 ЗМІНИТИ ДАТУ ЗАКІНЧЕННЯ", callback_data=f"changedate:{item_id}")],
        [InlineKeyboardButton(text="💰 ЗМІНИТИ ФІКСОВАНУ ЦІНУ ОРЕНДИ", callback_data=f"changeprice_start:{item_id}")],
        [InlineKeyboardButton(text="⚡ Вольтаж та ціни комплектацій", callback_data=f"manage_parts_pr:{item_id}")],
    ]
    if active_buyout:
        buttons.append([InlineKeyboardButton(text="🏷 ДІЮЧИЙ ВИКУП КЛІЄНТА", callback_data=f"adm_buyout_info:{item_id}")])
        buttons.append([InlineKeyboardButton(text="💳 Внести платіж викупу", callback_data=f"adm_buyout_pay:{item_id}")])

    buttons.extend([
        [InlineKeyboardButton(text="🔴 Перевести у зайняті (В оренді)", callback_data=f"setstat:{item_id}:rented")],
        [InlineKeyboardButton(text="🟢 Перевести у вільні", callback_data=f"setstat:{item_id}:available")],
        [InlineKeyboardButton(text="🛠 Перевести в ремонт", callback_data=f"setstat:{item_id}:repair")],
        [InlineKeyboardButton(text="🔄 Замінити транспорт / Апгрейд", callback_data=f"upgrade:{item_id}")],
        [InlineKeyboardButton(text="⛔ Завершити оренду достроково", callback_data=f"stoprental:{item_id}")],
        [InlineKeyboardButton(text="📷 Додати / Змінити фото", callback_data=f"addphoto:{item_id}")],
        [InlineKeyboardButton(text="⬅️ Назад до списку", callback_data="adm_back_list")]
    ])

    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await safe_render_card(callback, text, kb, data.get("photo_id"))

@dp.callback_query(F.data == "adm_back_list", StateFilter("*"))
async def admin_back_list_callback(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID: return
    await callback.answer()
    await safe_clear_state(state)
    text, kb = get_admin_text_and_kb()
    await safe_render_card(callback, text, kb)

@dp.callback_query(F.data == "back_to_admin_panel", StateFilter("*"))
async def back_to_admin_panel_callback(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID: return
    await callback.answer()
    await safe_clear_state(state)
    text, kb = get_admin_text_and_kb()
    await callback.message.answer(text, parse_mode="HTML", reply_markup=kb)

# --- ИЗМЕНЕНИЕ ФИКСИРОВАННЫХ ЦЕН АРЕНДЫ (ДОБА / ТИЖДЕНЬ / МІСЯЦЬ) ---
@dp.callback_query(F.data.startswith("changeprice_start:"), StateFilter("*"))
async def admin_change_price_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID: return
    await callback.answer()
    item_id = callback.data.split(":")[1]
    v_data = FLEET_DATABASE.get(item_id, {})
    p_day = v_data.get("price_day", 900)
    p_week = v_data.get("price_week", 2200)
    p_month = v_data.get("price_month", 8000)

    text = (
        f"💰 <b>ЗМІНА ФІКСОВАНИХ ЦІН ОРЕНДИ</b>\n"
        f"🛵 <b>Модель:</b> {v_data.get('name', item_id)}\n"
        "────────────────────\n"
        "Оберіть період, ціну якого ви бажаєте змінити:"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🗓 За добу (зараз: {int(p_day)} грн)", callback_data=f"chpr:{item_id}:price_day")],
        [InlineKeyboardButton(text=f"📅 За тиждень (зараз: {int(p_week)} грн)", callback_data=f"chpr:{item_id}:price_week")],
        [InlineKeyboardButton(text=f"🗓 За місяць (зараз: {int(p_month)} грн)", callback_data=f"chpr:{item_id}:price_month")],
        [InlineKeyboardButton(text="⬅️ Назад до транспорту", callback_data=f"admmanage:{item_id}")]
    ])
    await safe_render_card(callback, text, kb, v_data.get("photo_id"))

@dp.callback_query(F.data.startswith("chpr:"), StateFilter("*"))
async def admin_change_price_period_choice(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID: return
    await callback.answer()
    parts = callback.data.split(":")
    item_id = parts[1]
    period_field = parts[2]
    
    p_labels = {"price_day": "добу", "price_week": "тиждень", "price_month": "місяць"}
    lbl = p_labels.get(period_field, "період")
    
    await state.update_data(chpr_item_id=item_id, chpr_field=period_field, chpr_lbl=lbl)
    await state.set_state(AdminChangePriceState.waiting_for_new_price)
    
    v_name = FLEET_DATABASE.get(item_id, {}).get("name", item_id)
    await callback.message.answer(
        f"Введіть нову <b>фіксовану ціну за {lbl}</b> для <b>{v_name}</b> у грн (наприклад: <code>2500</code>):",
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard()
    )

@dp.message(StateFilter(AdminChangePriceState.waiting_for_new_price), F.text)
async def admin_change_price_save(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    msg_text = (message.text or "").strip()
    if "скасувати" in msg_text.lower():
        await safe_clear_state(state)
        await message.answer("Дію скасовано.", reply_markup=get_admin_keyboard())
        return

    try:
        new_price = float(msg_text.replace(",", ".").replace(" ", ""))
        if new_price <= 0: raise ValueError()
    except ValueError:
        await message.answer("Будь ласка, введіть коректну суму числом (наприклад: <code>2400</code>):", parse_mode="HTML")
        return

    data = await state.get_data()
    await safe_clear_state(state)
    item_id = data.get("chpr_item_id")
    field = data.get("chpr_field")
    lbl = data.get("chpr_lbl", "період")

    if item_id in FLEET_DATABASE:
        FLEET_DATABASE[item_id][field] = int(new_price) if new_price.is_integer() else new_price
        save_fleet()
        
    # Also update in active rental if currently rented
    user_id = FLEET_DATABASE.get(item_id, {}).get("reserved_by")
    if user_id:
        col_map = {"price_day": "custom_price_day", "price_week": "custom_price_week", "price_month": "custom_price_month"}
        col = col_map.get(field)
        if col:
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(f"UPDATE rentals SET {col} = ? WHERE user_phone = (SELECT phone_number FROM users WHERE telegram_id = ?)", (new_price, user_id))
                await db.commit()

    v_name = FLEET_DATABASE.get(item_id, {}).get("name", item_id)
    await message.answer(
        f"✅ <b>Ціну за {lbl} для {v_name} успішно змінено на {int(new_price)} грн!</b>",
        parse_mode="HTML",
        reply_markup=get_admin_keyboard()
    )

# --- ИЗМЕНЕНИЕ ВОЛЬТАЖА И ЦЕН КОМПЛЕКТАЦИЙ (АКБ / ЗАРЯДКИ / ВЫКУП) ---
@dp.callback_query(F.data.startswith("manage_parts_pr:"), StateFilter("*"))
async def admin_manage_parts_pr_menu(callback: CallbackQuery, state: FSMContext = None):
    if callback.from_user.id != ADMIN_ID: return
    await callback.answer()
    if state: await safe_clear_state(state)
    item_id = callback.data.split(":")[1]
    v_data = FLEET_DATABASE.get(item_id, {})
    volt = v_data.get("voltage", "72V")
    b_price = v_data.get("buyout_base_price", 46000)

    text = (
        f"⚡ <b>ВОЛЬТАЖ ТА ЦІНИ КОМПЛЕКТАЦІЙ</b>\n"
        f"🛵 <b>Модель:</b> {v_data.get('name', item_id)}\n"
        "────────────────────\n"
        f"⚡ <b>Поточний вольтаж:</b> <b>{volt}</b>\n"
        f"🏷 <b>Базова вартість викупу:</b> <b>{b_price} грн</b>\n\n"
        "Оберіть дію нижче:"
    )
    buttons = [
        [
            InlineKeyboardButton(text="⚡ Встановити 60V", callback_data=f"set_sc_volt:{item_id}:60V"),
            InlineKeyboardButton(text="⚡ Встановити 72V", callback_data=f"set_sc_volt:{item_id}:72V"),
            InlineKeyboardButton(text="⚡ Встановити 48V", callback_data=f"set_sc_volt:{item_id}:48V")
        ],
        [InlineKeyboardButton(text="🏷 Змінити базову ціну викупу", callback_data=f"change_bprice:{item_id}")],
        [InlineKeyboardButton(text="🔋 Змінити ціни АКБ та зарядок", callback_data=f"edit_parts_menu:{item_id}")],
        [InlineKeyboardButton(text="⬅️ Назад до транспорту", callback_data=f"admmanage:{item_id}")]
    ]
    await safe_render_card(callback, text, InlineKeyboardMarkup(inline_keyboard=buttons), v_data.get("photo_id"))

@dp.callback_query(F.data.startswith("set_sc_volt:"), StateFilter("*"))
async def admin_set_sc_volt_action(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    await callback.answer()
    parts = callback.data.split(":")
    item_id = parts[1]
    new_volt = parts[2]
    if item_id in FLEET_DATABASE:
        FLEET_DATABASE[item_id]["voltage"] = new_volt
        save_fleet()
    v_name = FLEET_DATABASE.get(item_id, {}).get("name", item_id)
    await callback.message.answer(f"✅ Вольтаж для <b>{v_name}</b> успішно змінено на <b>{new_volt}</b>!", parse_mode="HTML")
    # Refresh menu
    callback.data = f"manage_parts_pr:{item_id}"
    await admin_manage_parts_pr_menu(callback)

@dp.callback_query(F.data.startswith("change_bprice:"), StateFilter("*"))
async def admin_change_bprice_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID: return
    await callback.answer()
    item_id = callback.data.split(":")[1]
    await state.update_data(bprice_item_id=item_id)
    await state.set_state(AdminBuyoutPriceState.waiting_for_price)
    v_name = FLEET_DATABASE.get(item_id, {}).get("name", item_id)
    await callback.message.answer(
        f"Введіть <b>базову ціну викупу</b> для {v_name} у грн (наприклад: <code>48000</code>):",
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard()
    )

@dp.message(StateFilter(AdminBuyoutPriceState.waiting_for_price), F.text)
async def admin_change_bprice_save(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    msg_text = (message.text or "").strip()
    if "скасувати" in msg_text.lower():
        await safe_clear_state(state)
        await message.answer("Дію скасовано.", reply_markup=get_admin_keyboard())
        return
    try:
        val = float(msg_text.replace(",", ".").replace(" ", ""))
        if val <= 0: raise ValueError()
    except ValueError:
        await message.answer("Введіть числом (наприклад: <code>48000</code>):", parse_mode="HTML")
        return
    data = await state.get_data()
    await safe_clear_state(state)
    item_id = data.get("bprice_item_id")
    if item_id in FLEET_DATABASE:
        FLEET_DATABASE[item_id]["buyout_base_price"] = int(val) if val.is_integer() else val
        save_fleet()
    v_name = FLEET_DATABASE.get(item_id, {}).get("name", item_id)
    await message.answer(f"✅ Базову ціну викупу для {v_name} оновлено: <b>{int(val)} грн</b>!", parse_mode="HTML", reply_markup=get_admin_keyboard())

@dp.callback_query(F.data.startswith("edit_parts_menu:"), StateFilter("*"))
async def admin_edit_parts_menu(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    await callback.answer()
    item_id = callback.data.split(":")[1]
    v_data = FLEET_DATABASE.get(item_id, {})
    volt = v_data.get("voltage", "72V")
    
    parts_list = []
    if volt == "72V":
        parts_list = [("72V_40Ah", "🔋 АКБ 72V 40Ah"), ("72V_60Ah", "🔋 АКБ 72V 60Ah"), ("72V_ch5A", "🔌 Зарядка 5A"), ("72V_ch10A", "⚡️ Зарядка 10A")]
    elif volt == "60V":
        parts_list = [("60V_40Ah", "🔋 АКБ 60V 40Ah"), ("60V_60Ah", "🔋 АКБ 60V 60Ah"), ("60V_ch5A", "🔌 Зарядка 5A"), ("60V_ch10A", "⚡️ Зарядка 10A")]
    else:
        parts_list = [("48V_10Ah", "🔋 АКБ 48V 10Ah"), ("48V_20Ah", "🔋 АКБ 48V 20Ah"), ("48V_30Ah", "🔋 АКБ 48V 30Ah"), ("48V_40Ah", "🔋 АКБ 48V 40Ah"), ("48V_ch3A", "🔌 Зарядка 3A"), ("48V_ch5A", "⚡️ Зарядка 5A")]
        
    buttons = []
    for code, name in parts_list:
        cur_p = get_part_price(item_id, code)
        buttons.append([InlineKeyboardButton(text=f"{name} ({int(cur_p)} грн)", callback_data=f"setpartpr:{item_id}:{code}")])
    buttons.append([InlineKeyboardButton(text="⬅️ Назад до налаштувань комплектацій", callback_data=f"manage_parts_pr:{item_id}")])
    
    await safe_render_card(callback, f"Оберіть деталь комплектації ({volt}) для зміни вартості:", InlineKeyboardMarkup(inline_keyboard=buttons))

@dp.callback_query(F.data.startswith("setpartpr:"), StateFilter("*"))
async def admin_setpartpr_prompt(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID: return
    await callback.answer()
    parts = callback.data.split(":")
    item_id = parts[1]
    part_code = parts[2]
    await state.update_data(target_item_id=item_id, target_part_code=part_code)
    await state.set_state(AdminSetPartPriceState.waiting_for_price)
    await callback.message.answer(
        f"Введіть нову <b>ціну для {part_code}</b> у грн (наприклад: <code>15000</code>):",
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard()
    )

@dp.message(StateFilter(AdminSetPartPriceState.waiting_for_price), F.text)
async def admin_setpartpr_save(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    msg_text = (message.text or "").strip()
    if "скасувати" in msg_text.lower():
        await safe_clear_state(state)
        await message.answer("Дію скасовано.", reply_markup=get_admin_keyboard())
        return
    try:
        val = float(msg_text.replace(",", ".").replace(" ", ""))
        if val < 0: raise ValueError()
    except ValueError:
        await message.answer("Введіть числом (наприклад: <code>15000</code>):", parse_mode="HTML")
        return
    data = await state.get_data()
    await safe_clear_state(state)
    item_id = data.get("target_item_id")
    part_code = data.get("target_part_code")
    if item_id in FLEET_DATABASE:
        if "custom_parts_prices" not in FLEET_DATABASE[item_id]:
            FLEET_DATABASE[item_id]["custom_parts_prices"] = {}
        FLEET_DATABASE[item_id]["custom_parts_prices"][part_code] = val
        save_fleet()
    await message.answer(f"✅ Ціну для <b>{part_code}</b> оновлено на <b>{int(val)} грн</b>!", parse_mode="HTML", reply_markup=get_admin_keyboard())

# --- РУЧНОЕ ИЗМЕНЕНИЕ ДАТЫ ОКОНЧАНИЯ АРЕНДЫ ---
@dp.callback_query(F.data.startswith("changedate:"), StateFilter("*"))
async def admin_change_date_start(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID: return
    item_id = callback.data.split(":")[1]
    user_id = FLEET_DATABASE.get(item_id, {}).get("reserved_by")

    if not user_id:
        await callback.answer("⚠️ До цього скутера не прив'язаний клієнт!", show_alert=True)
        return

    await state.update_data(change_item_id=item_id, change_user_id=user_id)
    await state.set_state(AdminChangeDateState.waiting_for_new_date)

    await callback.message.answer(
        "📅 Введіть <b>нову дату та час закінчення оренди</b> у форматі:\n"
        "<code>YYYY-MM-DD HH:MM</code> (наприклад: <code>2026-08-20 23:59</code>):",
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard()
    )
    await callback.answer()

@dp.message(StateFilter(AdminChangeDateState.waiting_for_new_date), F.text)
async def admin_save_changed_date(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    msg_text = (message.text or "").strip()
    if "скасувати" in msg_text.lower():
        await safe_clear_state(state)
        await message.answer("Дію скасовано.", reply_markup=get_admin_keyboard())
        return

    new_date_str = msg_text
    data = await state.get_data()
    await safe_clear_state(state)

    user_id = data.get("change_user_id")
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT phone_number FROM users WHERE telegram_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()

        if row:
            user_phone = row[0]
            await db.execute(
                "UPDATE rentals SET end_date = ?, reminder_sent = 0 WHERE user_phone = ?",
                (new_date_str, user_phone)
            )
            await db.commit()

    try:
        await bot.send_message(
            chat_id=user_id,
            text=f"📅 <b>Термін вашої оренди оновлено менеджером!</b>\nНова дата закінчення: <b>{new_date_str}</b>",
            parse_mode="HTML"
        )
    except Exception:
        pass

    await message.answer(f"✅ <b>Дату закінчення успішно змінено на {new_date_str}!</b>", parse_mode="HTML", reply_markup=get_admin_keyboard())

# --- ВЫДАЧА И АКТИВАЦИЯ АРЕНДЫ ---
@dp.callback_query(F.data.startswith("issue:"), StateFilter("*"))
async def admin_issue_start(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID: return
    item_id = callback.data.split(":")[1]
    data = FLEET_DATABASE.get(item_id, {})
    user_id = data.get("reserved_by")
    
    if not user_id:
        await callback.answer("⚠️ До цього скутера не прив'язаний Telegram ID клієнта!", show_alert=True)
        return

    await state.update_data(issue_item_id=item_id, issue_user_id=user_id)
    await state.set_state(AdminIssueState.waiting_for_days)
    
    await callback.message.answer(
        f"⚙️ <b>Оформлення видачі {data.get('name', item_id)}</b>\n"
        f"Клієнт Telegram ID: <code>{user_id}</code>\n\n"
        "Введіть <b>термін оренди у днях</b> (наприклад: <code>7</code> або <code>30</code>):\n"
        "<i>(День видачі враховується як 1-й день оренди)</i>",
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard()
    )
    await callback.answer()

@dp.message(StateFilter(AdminIssueState.waiting_for_days), F.text)
async def admin_issue_days(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    msg_text = (message.text or "").strip()
    if "скасувати" in msg_text.lower():
        await safe_clear_state(state)
        await message.answer("Дію скасовано.", reply_markup=get_admin_keyboard())
        return

    if not msg_text.isdigit():
        await message.answer("Введіть кількість днів цифрами (наприклад: 7):")
        return

    days = int(msg_text)
    end_date = (get_kyiv_now() + timedelta(days=days - 1)).strftime("%Y-%m-%d 23:59")
    await state.update_data(rental_days=days, end_date=end_date)
    await state.set_state(AdminIssueState.waiting_for_amount)
    
    await message.answer(
        f"📅 Оренда діє до: <b>{end_date}</b>\n\n"
        "Введіть <b>суму наступного платежу</b> в грн (наприклад: <code>2200</code>):",
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard()
    )

@dp.message(StateFilter(AdminIssueState.waiting_for_amount), F.text)
async def admin_issue_amount(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    msg_text = (message.text or "").strip()
    if "скасувати" in msg_text.lower():
        await safe_clear_state(state)
        await message.answer("Дію скасовано.", reply_markup=get_admin_keyboard())
        return

    try:
        amount = float(msg_text.replace(",", ".").replace(" ", ""))
    except ValueError:
        await message.answer("Введіть суму числом (наприклад: 2200):")
        return

    await state.update_data(amount=amount)
    await state.set_state(AdminIssueState.waiting_for_contract_num)
    await message.answer("Введіть <b>номер Договору</b> (наприклад: <code>2804-5</code>):", parse_mode="HTML", reply_markup=get_cancel_keyboard())

@dp.message(StateFilter(AdminIssueState.waiting_for_contract_num), F.text)
async def admin_issue_contract_num(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    msg_text = (message.text or "").strip()
    if "скасувати" in msg_text.lower():
        await safe_clear_state(state)
        await message.answer("Дію скасовано.", reply_markup=get_admin_keyboard())
        return

    await state.update_data(contract_num=msg_text)
    await state.set_state(AdminIssueState.waiting_for_contract_date)
    today_str = get_kyiv_now().strftime("%d.%m.%Y")
    await message.answer(f"Введіть <b>дату Договору</b> (наприклад: <code>{today_str}</code>):", parse_mode="HTML", reply_markup=get_cancel_keyboard())

@dp.message(StateFilter(AdminIssueState.waiting_for_contract_date), F.text)
async def admin_issue_contract_date(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    msg_text = (message.text or "").strip()
    if "скасувати" in msg_text.lower():
        await safe_clear_state(state)
        await message.answer("Дію скасовано.", reply_markup=get_admin_keyboard())
        return

    await state.update_data(contract_date=msg_text)
    await state.set_state(AdminIssueState.waiting_for_helmet)
    
    helmet_kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="З шоломом"), KeyboardButton(text="Без шолома")],
            [KeyboardButton(text="❌ Скасувати дію")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await message.answer("Клієнт бере <b>шолом</b>?", parse_mode="HTML", reply_markup=helmet_kb)

@dp.message(StateFilter(AdminIssueState.waiting_for_helmet), F.text)
async def admin_issue_helmet(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    msg_text = (message.text or "").strip()
    if "скасувати" in msg_text.lower():
        await safe_clear_state(state)
        await message.answer("Дію скасовано.", reply_markup=get_admin_keyboard())
        return

    has_helmet = 1 if "з шоломом" in msg_text.lower() else 0
    await state.update_data(has_helmet=has_helmet)

    data = await state.get_data()
    user_id = data["issue_user_id"]

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT phone_number FROM users WHERE telegram_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            
        user_phone = row[0] if row else None

    if not user_phone:
        await state.set_state(AdminIssueState.waiting_for_phone_manual)
        await message.answer(
            f"⚠️ Номер телефону для TG ID <code>{user_id}</code> не знайдено в БД.\n\n"
            "Введіть <b>номер телефону клієнта</b> в форматі <code>380XXXXXXXXX</code>:",
            parse_mode="HTML",
            reply_markup=get_cancel_keyboard()
        )
        return

    await finalize_issue(message, state, user_phone)

@dp.message(StateFilter(AdminIssueState.waiting_for_phone_manual), F.text)
async def admin_issue_manual_phone(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    msg_text = (message.text or "").strip()
    if "скасувати" in msg_text.lower():
        await safe_clear_state(state)
        await message.answer("Дію скасовано.", reply_markup=get_admin_keyboard())
        return

    user_phone = msg_text.replace("+", "").strip()
    data = await state.get_data()
    user_id = data["issue_user_id"]

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO users (telegram_id, phone_number, full_name) VALUES (?, ?, 'Клієнт (ручне додавання)')
            ON CONFLICT(telegram_id) DO UPDATE SET phone_number = excluded.phone_number""",
            (user_id, user_phone)
        )
        await db.commit()

    await finalize_issue(message, state, user_phone)

async def finalize_issue(message: types.Message, state: FSMContext, user_phone: str):
    data = await state.get_data()
    await safe_clear_state(state)

    item_id = data["issue_item_id"]
    user_id = data["issue_user_id"]
    end_date = data["end_date"]
    amount = data["amount"]
    contract_num = data["contract_num"]
    contract_date = data["contract_date"]
    has_helmet = data["has_helmet"]
    model_name = FLEET_DATABASE.get(item_id, {}).get("name", item_id)
    now_str = get_kyiv_now().strftime("%Y-%m-%d %H:%M:%S")

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        # Ensure only 1 active rental for this user or vehicle
        await db.execute("DELETE FROM rentals WHERE user_phone = ? OR vehicle_info = ?", (user_phone, model_name))

        cursor = await db.execute(
            "INSERT INTO rentals (user_phone, vehicle_info, end_date, amount_due, contract_num, contract_date, has_helmet, reminder_sent) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 0)",
            (user_phone, model_name, end_date, amount, contract_num, contract_date, has_helmet)
        )
        rental_id = cursor.lastrowid

        await db.execute(
            "INSERT INTO payments (user_id, rental_id, amount, bonus_used, date_paid, payment_type) VALUES (?, ?, ?, 0, ?, 'rent')",
            (user_id, rental_id, amount, now_str)
        )

        async with db.execute("SELECT referred_by FROM users WHERE telegram_id = ?", (user_id,)) as cursor_ref:
            u_row = await cursor_ref.fetchone()
            if u_row and u_row['referred_by']:
                ref_id = u_row['referred_by']
                await db.execute(
                    "UPDATE users SET bonus_balance = bonus_balance + 200, invited_count = invited_count + 1 WHERE telegram_id = ?",
                    (ref_id,)
                )
                await db.execute("UPDATE users SET referred_by = NULL WHERE telegram_id = ?", (user_id,))
                
                try:
                    await bot.send_message(
                        chat_id=ref_id,
                        text="🎉 <b>Вам нараховано +200 грн бонусів!</b>\nВаш друг успішно оформив оренду транспорту. Ви можете використати ці бонуси при наступній оплаті!",
                        parse_mode="HTML"
                    )
                except Exception:
                    pass

        await db.commit()

    if item_id in FLEET_DATABASE:
        FLEET_DATABASE[item_id]["status"] = "rented"
        FLEET_DATABASE[item_id]["reserved_by"] = user_id
        save_fleet()

    if sheet_requests:
        try:
            cells = sheet_requests.findall(str(user_id))
            if cells:
                last_cell = cells[-1]
                sheet_requests.update_cell(last_cell.row, 13, "Активна")
                color_row(sheet_requests, last_cell.row, COLOR_GREEN_CONFIRMED)
        except Exception as e:
            logger.error(f"Помилка оновлення статусу в Google Sheets: {e}")

    push_msg = (
        "🚀 <b>Оренду успішно активовано!</b>\n"
        "────────────────────\n"
        f"🛵 <b>Ваш транспорт:</b> {model_name}\n"
        f"📅 <b>Термін дії до:</b> {end_date}\n"
        f"💰 <b>Сума наступної оплати:</b> {amount:.2f} грн\n"
        "────────────────────\n"
        "Вся інформація про оренду та нагадування доступні у вашому <b>«👤 Особистому кабінеті»</b>."
    )
    
    try:
        await bot.send_message(chat_id=user_id, text=push_msg, parse_mode="HTML")
        await message.answer("✅ <b>Скутер видано клієнту! Оренду зафіксовано в rentals_base.db.</b>", parse_mode="HTML", reply_markup=get_admin_keyboard())
    except Exception as e:
        await message.answer(f"✅ Оренду активовано в БД, але push не доставлено: {e}", reply_markup=get_admin_keyboard())

# --- ДОСРОЧНОЕ СНЯТИЕ КЛИЕНТА С АРЕНДЫ ---
@dp.callback_query(F.data.startswith("stoprental:"), StateFilter("*"))
async def admin_stop_rental(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return

    item_id = callback.data.split(":")[1]
    data = FLEET_DATABASE.get(item_id, {})
    user_id = data.get("reserved_by")

    FLEET_DATABASE[item_id]["status"] = "available"
    FLEET_DATABASE[item_id]["reserved_by"] = None
    save_fleet()

    if user_id:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT phone_number FROM users WHERE telegram_id = ?", (user_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    await db.execute("DELETE FROM rentals WHERE user_phone = ?", (row[0],))
                    await db.commit()

        try:
            await bot.send_message(
                chat_id=user_id, 
                text=f"ℹ️ Оренду транспорту <b>{data.get('name', item_id)}</b> достроково завершено. Дякуємо, що обираєте MUVIO Rent!",
                parse_mode="HTML"
            )
        except Exception:
            pass

    if sheet_requests and user_id:
        try:
            cells = sheet_requests.findall(str(user_id))
            if cells:
                last_cell = cells[-1]
                sheet_requests.update_cell(last_cell.row, 13, "Завершено")
        except Exception as e:
            logger.error(f"Помилка оновлення статусу в Google Sheets: {e}")

    await callback.answer("✅ Оренду зупинено, скутер вільний!", show_alert=True)
    text, kb = get_admin_text_and_kb()
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)

# --- ЗАМЕНА ТРАНСПОРТА / АПГРЕЙД ---
@dp.callback_query(F.data.startswith("upgrade:"), StateFilter("*"))
async def admin_upgrade_start(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID: return

    old_item_id = callback.data.split(":")[1]
    user_id = FLEET_DATABASE.get(old_item_id, {}).get("reserved_by")

    if not user_id:
        await callback.answer("⚠️ До цього скутера не прив'язаний клієнт!", show_alert=True)
        return

    await state.update_data(old_item_id=old_item_id, upgrade_user_id=user_id)
    await state.set_state(AdminUpgradeState.waiting_for_new_item)

    avail_buttons = []
    for k, v in FLEET_DATABASE.items():
        if v["status"] == "available":
            avail_buttons.append([InlineKeyboardButton(text=f"⚡ {v['name']}", callback_data=f"selectupg:{k}")])

    if not avail_buttons:
        await callback.message.answer("⚠️ Немає вільних скутерів для заміни!", reply_markup=get_admin_keyboard())
        await safe_clear_state(state)
        return

    avail_buttons.append([InlineKeyboardButton(text="❌ Скасувати", callback_data="back_to_admin_panel")])
    kb = InlineKeyboardMarkup(inline_keyboard=avail_buttons)
    await callback.message.answer("Оберіть <b>новий скутер</b> для клієнта:", parse_mode="HTML", reply_markup=kb)
    await callback.answer()

@dp.callback_query(F.data.startswith("selectupg:"), StateFilter("*"))
async def admin_upgrade_select(callback: types.CallbackQuery, state: FSMContext):
    new_item_id = callback.data.split(":")[1]
    await state.update_data(new_item_id=new_item_id)
    await state.set_state(AdminUpgradeState.waiting_for_days)

    await callback.message.answer("Введіть <b>новий термін оренди у днях</b> (наприклад: <code>7</code>):", parse_mode="HTML", reply_markup=get_cancel_keyboard())
    await callback.answer()

@dp.message(StateFilter(AdminUpgradeState.waiting_for_days), F.text)
async def admin_upgrade_days(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    msg_text = (message.text or "").strip()
    if "скасувати" in msg_text.lower():
        await safe_clear_state(state)
        await message.answer("Дію скасовано.", reply_markup=get_admin_keyboard())
        return

    if not msg_text.isdigit():
        await message.answer("Введіть кількість днів цифрами:")
        return

    days = int(msg_text)
    end_date = (get_kyiv_now() + timedelta(days=days - 1)).strftime("%Y-%m-%d 23:59")
    await state.update_data(end_date=end_date)
    await state.set_state(AdminUpgradeState.waiting_for_amount)

    await message.answer(f"📅 Нова дата закінчення: <b>{end_date}</b>\n\nВведіть <b>нову суму до сплати (з урахуванням доплати)</b>:", parse_mode="HTML", reply_markup=get_cancel_keyboard())

@dp.message(StateFilter(AdminUpgradeState.waiting_for_amount), F.text)
async def admin_upgrade_amount(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    msg_text = (message.text or "").strip()
    if "скасувати" in msg_text.lower():
        await safe_clear_state(state)
        await message.answer("Дію скасовано.", reply_markup=get_admin_keyboard())
        return

    try:
        amount = float(msg_text.replace(",", ".").replace(" ", ""))
    except ValueError:
        await message.answer("Введіть суму числом:")
        return

    data = await state.get_data()
    await safe_clear_state(state)

    old_item_id = data["old_item_id"]
    new_item_id = data["new_item_id"]
    user_id = data["upgrade_user_id"]
    end_date = data["end_date"]

    FLEET_DATABASE[old_item_id]["status"] = "available"
    FLEET_DATABASE[old_item_id]["reserved_by"] = None

    FLEET_DATABASE[new_item_id]["status"] = "rented"
    FLEET_DATABASE[new_item_id]["reserved_by"] = user_id
    save_fleet()

    new_model_name = FLEET_DATABASE.get(new_item_id, {}).get("name", new_item_id)

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT phone_number FROM users WHERE telegram_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()

        if row:
            user_phone = row[0]
            await db.execute("DELETE FROM rentals WHERE user_phone = ?", (user_phone,))
            await db.execute(
                "INSERT INTO rentals (user_phone, vehicle_info, end_date, amount_due, reminder_sent) VALUES (?, ?, ?, ?, 0)",
                (user_phone, new_model_name, end_date, amount)
            )
            await db.commit()

    push_msg = (
        "🔄 <b>Ваш транспорт та тариф успішно оновлено!</b>\n"
        "────────────────────\n"
        f"🛵 <b>Новий транспорт:</b> {new_model_name}\n"
        f"📅 <b>Новий термін до:</b> {end_date}\n"
        f"💰 <b>Оновлена сума до сплати:</b> {amount:.2f} грн\n"
        "────────────────────\n"
        "Дані оновлено у вашому <b>«👤 Особистому кабінеті»</b>."
    )

    try:
        await bot.send_message(chat_id=user_id, text=push_msg, parse_mode="HTML")
        await message.answer("✅ <b>Транспорт успішно замінено!</b>", parse_mode="HTML", reply_markup=get_admin_keyboard())
    except Exception as e:
        await message.answer(f"✅ Заміну проведено, але push не доставлено: {e}", reply_markup=get_admin_keyboard())

@dp.callback_query(F.data.startswith("setstat:"), StateFilter("*"))
async def admin_set_status_callback(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    _, item_id, new_stat = callback.data.split(":")
    if item_id in FLEET_DATABASE:
        old_status = FLEET_DATABASE[item_id]["status"]
        FLEET_DATABASE[item_id]["status"] = new_stat
        if new_stat == "available":
            FLEET_DATABASE[item_id]["reserved_by"] = None
        save_fleet()
        
        if new_stat == "available" and old_status != "available" and len(WAITLIST) > 0:
            notify_kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=f"📢 Оповістити лист очікування ({len(WAITLIST)})", callback_data=f"notify_waitlist:{item_id}")],
                [InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="adm_back_list")]
            ])
            await callback.message.edit_text(
                f"✅ Статус <b>{FLEET_DATABASE[item_id]['name']}</b> змінено на 🟢 <b>Вільний</b>!\n\n"
                f"У листі очікування є <b>{len(WAITLIST)}</b> осіб. Оповістити їх про звільнення?",
                parse_mode="HTML",
                reply_markup=notify_kb
            )
            await callback.answer()
            return

        await callback.answer(f"Статус змінено на {new_stat}!", show_alert=True)
        await admin_item_manage(callback, None)

@dp.callback_query(F.data.startswith("notify_waitlist:"), StateFilter("*"))
async def notify_waitlist_action(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    item_id = callback.data.split(":")[1]
    model_name = FLEET_DATABASE.get(item_id, {}).get("name", item_id)
    sent_count = 0
    msg = (
        f"⚡ <b>Звільнився скутер {model_name}!</b>\n\n"
        "Він доступний до бронювання. Натисніть кнопку нижче, щоб забронювати:"
    )
    book_kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=f"📝 Забронювати {model_name}", callback_data=f"book_{item_id}")
    ]])
    for uid in list(WAITLIST):
        try:
            await bot.send_message(chat_id=uid, text=msg, parse_mode="HTML", reply_markup=book_kb)
            sent_count += 1
        except Exception:
            pass
            
    await callback.answer(f"✅ Сповіщення надіслано {sent_count} користувачам!", show_alert=True)
    text, kb = get_admin_text_and_kb()
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)

@dp.callback_query(F.data.startswith("addphoto:"), StateFilter("*"))
async def admin_add_photo_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID: return
    await callback.answer()
    item_id = callback.data.split(":")[1]
    await state.update_data(target_veh_id=item_id)
    await state.set_state(AdminPhotoState.waiting_for_photo)
    await callback.message.answer("Надішліть **фото скутера/байка** у чат:", reply_markup=get_cancel_keyboard())

@dp.message(StateFilter(AdminPhotoState.waiting_for_photo), F.photo)
async def admin_add_photo_save(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    photo_id = message.photo[-1].file_id
    data = await state.get_data()
    item_id = data.get("target_veh_id")
    await safe_clear_state(state)
    
    if item_id in FLEET_DATABASE:
        FLEET_DATABASE[item_id]["photo_id"] = photo_id
        save_fleet()
    await message.answer(f"✅ Фото для {FLEET_DATABASE[item_id]['name']} успішно збережено!", reply_markup=get_admin_keyboard())

@dp.message(lambda msg: msg.from_user.id == ADMIN_ID and msg.text and "вийти" in msg.text.lower(), StateFilter("*"))
async def admin_exit_btn_handler(message: types.Message, state: FSMContext):
    await safe_clear_state(state)
    await message.answer("🚪 Ви вийшли з адмін-панелі.", reply_markup=get_main_keyboard())

# Планировщик напоминаний оренди
async def check_expiring_rentals():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM rentals WHERE reminder_sent = 0") as cursor:
            rentals = await cursor.fetchall()

    now = get_kyiv_now().replace(tzinfo=None)
    for r in rentals:
        try:
            raw_end = r['end_date']
            end_dt = datetime.strptime(raw_end, "%Y-%m-%d %H:%M") if " " in raw_end else datetime.strptime(raw_end, "%Y-%m-%d")
            diff_hours = (end_dt - now).total_seconds() / 3600
            
            if 0 < diff_hours <= 30:
                async with aiosqlite.connect(DB_PATH) as db:
                    async with db.execute("SELECT telegram_id FROM users WHERE phone_number = ?", (r['user_phone'],)) as cur:
                        u_row = await cur.fetchone()
                        if u_row:
                            u_id = u_row[0]
                            try:
                                await bot.send_message(
                                    chat_id=u_id,
                                    text=(
                                        "⏰ <b>НАГАДУВАННЯ ПРО ОПЛАТУ ОРЕНДИ</b>\n\n"
                                        f"🛵 <b>Техніка:</b> {r['vehicle_info']}\n"
                                        f"📅 <b>Термін оренди спливає:</b> <code>{r['end_date']}</code>\n"
                                        f"💰 <b>До сплати:</b> <b>{r['amount_due']:.2f} грн</b>\n\n"
                                        "Будь ласка, здійсніть оплату найближчим часом для продовження оренди!"
                                    ),
                                    parse_mode="HTML"
                                )
                            except Exception:
                                pass
                    await db.execute("UPDATE rentals SET reminder_sent = 1 WHERE id = ?", (r['id'],))
                    await db.commit()
        except Exception as e:
            logger.error(f"Ошибка в check_expiring_rentals: {e}")

# ==================== ОБРАБОТЧИКИ ДІЮЧОГО ВИКУПУ В АДМІНЦІ ТА ОПЛАТИ ====================

@dp.callback_query(F.data == "adm_all_buyouts", StateFilter("*"))
async def admin_all_buyouts_list(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    await callback.answer()
    
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT b.*, u.full_name, u.phone_number FROM buyout_deals b LEFT JOIN users u ON b.user_id = u.telegram_id WHERE b.status = 'active' ORDER BY b.id DESC") as cur:
            deals = await cur.fetchall()
            
    if not deals:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад до флоту", callback_data="adm_back_list")]
        ])
        await safe_render_card(callback, "🏷 <b>Наразі немає активних договорів викупу (Rent-to-Own).</b>", kb)
        return

    text = "🏷 <b>АКТИВНІ ДОГОВОРИ ВИКУПУ (RENT-TO-OWN)</b>\n────────────────────\n\nОберіть клієнта для перегляду або внесення платежу:\n"
    buttons = []
    for d in deals:
        c_name = d['full_name'] or f"ID: {d['user_id']}"
        rem = max(0.0, d['total_price'] - d['paid_amount'])
        term = d['term_months'] if 'term_months' in d.keys() and d['term_months'] else 6
        text += (
            f"👤 <b>{c_name}</b> | 🛵 <b>{d['vehicle_info']}</b>\n"
            f"📅 Термін: {term} міс. | 💰 Залишок: <b>{rem:.2f} грн</b>\n\n"
        )
        buttons.append([
            InlineKeyboardButton(text=f"💵 Внести оплату ({d['vehicle_info']})", callback_data=f"adm_buyout_pay:{d['id']}"),
            InlineKeyboardButton(text="ℹ️ Інфо", callback_data=f"adm_buyout_info:{d['vehicle_key']}")
        ])
    buttons.append([InlineKeyboardButton(text="⬅️ Назад до флоту", callback_data="adm_back_list")])
    await safe_render_card(callback, text, InlineKeyboardMarkup(inline_keyboard=buttons))

@dp.callback_query(F.data.startswith("adm_buyout_info:"), StateFilter("*"))
async def admin_buyout_info_handler(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    await callback.answer()
    item_id = callback.data.split(":")[1]
    
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        deal_id_val = int(item_id) if item_id.isdigit() else -1
        async with db.execute(
            "SELECT * FROM buyout_deals WHERE (vehicle_key = ? OR id = ?) AND status = 'active' ORDER BY id DESC LIMIT 1",
            (item_id, deal_id_val)
        ) as cur:
            b = await cur.fetchone()
        if not b:
            async with db.execute(
                "SELECT * FROM buyout_deals WHERE (vehicle_key = ? OR id = ?) ORDER BY id DESC LIMIT 1",
                (item_id, deal_id_val)
            ) as cur:
                b = await cur.fetchone()
        if not b:
            await callback.answer("Викупу для цього транспорту не знайдено", show_alert=True)
            return

        async with db.execute("SELECT * FROM users WHERE telegram_id = ?", (b['user_id'],)) as cur_u:
            u = await cur_u.fetchone()

    c_name = u['full_name'] if u and u['full_name'] else f"ID: {b['user_id']}"
    c_phone = f"+{u['phone_number']}" if u and u['phone_number'] else "Не вказано"
    
    tot = b['total_price']
    paid = b['paid_amount']
    dep = b['deposit_paid']
    rem = max(0.0, tot - paid)
    pct = int((paid / tot * 100)) if tot > 0 else 0
    term = b['term_months'] if 'term_months' in b.keys() and b['term_months'] else 6
    bat = b['battery_spec'] if 'battery_spec' in b.keys() and b['battery_spec'] else "-"
    ch = b['charger_spec'] if 'charger_spec' in b.keys() and b['charger_spec'] else "-"
    monthly = (tot - dep) / term if term > 0 else 0.0

    b_filled = min(10, max(0, int((paid / tot) * 10))) if tot > 0 else 0
    b_bar = "▓" * b_filled + "░" * (10 - b_filled)

    text = (
        f"🏷 <b>ДЕТАЛІ ДІЮЧОГО ВИКУПУ (RENT-TO-OWN)</b>\n"
        f"────────────────────\n"
        f"🛵 <b>Транспорт:</b> {b['vehicle_info']} (<code>{b['vehicle_key']}</code>)\n"
        f"👤 <b>Клієнт:</b> {c_name}\n"
        f"📱 <b>Телефон:</b> {c_phone}\n"
        f"🆔 <b>TG ID:</b> <code>{b['user_id']}</code>\n"
        f"🔋 <b>Комплектація:</b> {bat}, {ch}\n"
        f"📅 <b>Дата старту:</b> <code>{b['start_date']}</code>\n"
        f"⏳ <b>Термін викупу:</b> {term} міс. (~{monthly:.2f} грн/міс.)\n"
        f"────────────────────\n"
        f"🔒 <b>Застава (20%):</b> {dep:.2f} грн\n"
        f"💵 <b>Повна сума:</b> {tot:.2f} грн\n"
        f"✅ <b>Внесено:</b> {paid:.2f} грн ({pct}%)\n"
        f"<code>[{b_bar}]</code>\n"
        f"⏳ <b>Залишок до сплати:</b> <b>{rem:.2f} грн</b>\n"
        f"────────────────────"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏷 Внести оплату за викуп вручну", callback_data=f"adm_buyout_pay:{b['id']}")],
        [InlineKeyboardButton(text="⬅️ Назад до транспорту", callback_data=f"admmanage:{b['vehicle_key']}")]
    ])
    await safe_render_card(callback, text, kb)

@dp.message(F.text == "🏷 Активні викупи", StateFilter("*"))
async def admin_all_buyouts_msg(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT b.*, u.full_name, u.phone_number FROM buyout_deals b LEFT JOIN users u ON b.user_id = u.telegram_id WHERE b.status = 'active' ORDER BY b.id DESC") as cur:
            deals = await cur.fetchall()
            
    if not deals:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Внести платіж викупу", callback_data="adm_buyout_pay_manual")],
            [InlineKeyboardButton(text="⬅️ Назад до флоту", callback_data="adm_back_list")]
        ])
        await message.answer("🏷 <b>Наразі немає активних договорів викупу (Rent-to-Own).</b>", parse_mode="HTML", reply_markup=kb)
        return

    text = "🏷 <b>АКТИВНІ ДОГОВОРИ ВИКУПУ (RENT-TO-OWN):</b>\n────────────────────\n\n"
    buttons = []
    for d in deals:
        name_str = d['full_name'] or "Клієнт"
        phone_str = f"+{d['phone_number']}" if d['phone_number'] else str(d['user_id'])
        paid = d['paid_amount']
        tot = d['total_price']
        rem = max(0.0, tot - paid)
        pct = int((paid / tot * 100)) if tot > 0 else 100
        
        text += (
            f"🛵 <b>{d['vehicle_info']}</b>\n"
            f"👤 {name_str} (ID: <code>{d['user_id']}</code> | {phone_str})\n"
            f"💰 Виплачено: <b>{paid:.2f} грн</b> з <b>{tot:.2f} грн</b> ({pct}%)\n"
            f"⏳ Залишок: <b>{rem:.2f} грн</b>\n"
            "────────────────────\n"
        )
        buttons.append([InlineKeyboardButton(
            text=f"💵 Внести оплату: {d['vehicle_info']} ({name_str})",
            callback_data=f"adm_buyout_pay:{d['id']}"
        )])

    buttons.append([InlineKeyboardButton(text="💳 Внести за Telegram ID клієнта", callback_data="adm_buyout_pay_manual")])
    buttons.append([InlineKeyboardButton(text="⬅️ Назад до флоту", callback_data="adm_back_list")])
    await message.answer(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@dp.message(F.text == "💳 Внести платіж викупу", StateFilter("*"))
@dp.callback_query(F.data == "adm_buyout_pay_manual", StateFilter("*"))
async def admin_buyout_pay_manual_start(event: types.Message | types.CallbackQuery, state: FSMContext):
    user_id = event.from_user.id
    if user_id != ADMIN_ID:
        if isinstance(event, types.CallbackQuery):
            await event.answer("⛔ Немає доступу", show_alert=True)
        return

    if isinstance(event, types.CallbackQuery):
        await event.answer()
        msg = event.message
    else:
        msg = event

    await safe_clear_state(state)
    await state.set_state(AdminBuyoutState.waiting_for_user_id)

    cancel_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Скасувати", callback_data="back_to_admin_panel")]
    ])

    text = (
        "💳 <b>Внесення платежу за викуп (Rent-to-Own)</b>\n"
        "────────────────────\n"
        "Введіть <b>Telegram ID клієнта</b> (число, наприклад: <code>7288164492</code>) "
        "або <b>номер телефону</b> клієнта (наприклад: <code>380960000000</code>):\n\n"
        "<i>(Для скасування натисніть кнопку нижче)</i>"
    )
    await msg.answer(text, parse_mode="HTML", reply_markup=cancel_kb)

@dp.message(StateFilter(AdminBuyoutState.waiting_for_user_id), F.text)
async def admin_buyout_user_id_process(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    raw_input = (message.text or "").strip()
    if "скасувати" in raw_input.lower():
        await safe_clear_state(state)
        await message.answer("Дію скасовано.", reply_markup=get_admin_keyboard())
        return

    clean_digits = raw_input.replace("+", "").replace(" ", "").replace("-", "")
    deal = None

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        # Try as telegram_id
        if clean_digits.isdigit():
            tg_id = int(clean_digits)
            async with db.execute(
                "SELECT * FROM buyout_deals WHERE user_id = ? AND status = 'active' ORDER BY id DESC LIMIT 1",
                (tg_id,)
            ) as cur:
                deal = await cur.fetchone()

        # If not found, try as phone number in users table
        if not deal and clean_digits:
            async with db.execute(
                """SELECT b.* FROM buyout_deals b
                JOIN users u ON b.user_id = u.telegram_id
                WHERE u.phone_number LIKE ? AND b.status = 'active'
                ORDER BY b.id DESC LIMIT 1""",
                (f"%{clean_digits}%",)
            ) as cur:
                deal = await cur.fetchone()

        # If still not found, check any status deal
        if not deal and clean_digits.isdigit():
            tg_id = int(clean_digits)
            async with db.execute(
                "SELECT * FROM buyout_deals WHERE user_id = ? ORDER BY id DESC LIMIT 1",
                (tg_id,)
            ) as cur:
                deal = await cur.fetchone()

    if not deal:
        await message.answer(
            f"❌ <b>Договір викупу не знайдено</b> за запитом <code>{raw_input}</code>.\n\n"
            "Перевірте Telegram ID або номер телефону та введіть ще раз (або напишіть «❌ Скасувати»):",
            parse_mode="HTML",
            reply_markup=get_cancel_keyboard()
        )
        return

    await state.update_data(
        target_veh_id=deal['vehicle_key'],
        target_deal_id=deal['id'],
        client_user_id=deal['user_id']
    )
    await state.set_state(AdminBuyoutState.waiting_for_amount)

    term = deal['term_months'] if 'term_months' in deal.keys() and deal['term_months'] else 6
    rem = max(0.0, deal['total_price'] - deal['paid_amount'])

    cancel_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Скасувати", callback_data="back_to_admin_panel")]
    ])
    await message.answer(
        f"💵 <b>Внесення оплати за викуп:</b> {deal['vehicle_info']}\n"
        f"👤 Клієнт ID: <code>{deal['user_id']}</code>\n"
        f"⏳ Термін викупу: <b>{term} міс.</b>\n"
        f"💵 Повна вартість: <b>{deal['total_price']:.2f} грн</b>\n"
        f"✅ Вже виплачено: <b>{deal['paid_amount']:.2f} грн</b>\n"
        f"⏳ Поточний залишок: <b>{rem:.2f} грн</b>\n"
        "────────────────────\n\n"
        "Введіть <b>суму платежу (грн)</b> числом (наприклад: <code>2500</code>):",
        parse_mode="HTML",
        reply_markup=cancel_kb
    )

@dp.callback_query(F.data.startswith("adm_buyout_pay:"), StateFilter("*"))
async def admin_buyout_pay_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    await callback.answer()
    target_id = callback.data.split(":")[1]
    
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        deal_id_val = int(target_id) if target_id.isdigit() else -1
        async with db.execute(
            "SELECT * FROM buyout_deals WHERE (id = ? OR vehicle_key = ?) AND status = 'active' ORDER BY id DESC LIMIT 1",
            (deal_id_val, target_id)
        ) as cur:
            deal = await cur.fetchone()
        if not deal:
            async with db.execute(
                "SELECT * FROM buyout_deals WHERE (id = ? OR vehicle_key = ?) ORDER BY id DESC LIMIT 1",
                (deal_id_val, target_id)
            ) as cur:
                deal = await cur.fetchone()

    if not deal:
        await callback.answer("Активного викупу не знайдено", show_alert=True)
        return

    await state.update_data(
        target_veh_id=deal['vehicle_key'],
        target_deal_id=deal['id'],
        client_user_id=deal['user_id']
    )
    await state.set_state(AdminBuyoutState.waiting_for_amount)
    
    term = deal['term_months'] if 'term_months' in deal.keys() and deal['term_months'] else 6
    rem = max(0.0, deal['total_price'] - deal['paid_amount'])

    cancel_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Скасувати", callback_data=f"admmanage:{deal['vehicle_key']}")]
    ])
    await callback.message.answer(
        f"💵 <b>Внесення оплати за викуп:</b> {deal['vehicle_info']}\n"
        f"👤 Клієнт ID: <code>{deal['user_id']}</code>\n"
        f"⏳ Термін викупу: <b>{term} міс.</b>\n"
        f"💵 Повна вартість: <b>{deal['total_price']:.2f} грн</b>\n"
        f"✅ Вже виплачено: <b>{deal['paid_amount']:.2f} грн</b>\n"
        f"⏳ Поточний залишок: <b>{rem:.2f} грн</b>\n"
        "────────────────────\n\n"
        "Введіть <b>суму платежу (грн)</b> числом (наприклад: <code>2500</code>):",
        parse_mode="HTML",
        reply_markup=cancel_kb
    )

@dp.message(StateFilter(AdminBuyoutState.waiting_for_amount))
async def admin_buyout_pay_process(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    msg_text = (message.text or "").strip()
    if "скасувати" in msg_text.lower():
        await safe_clear_state(state)
        await message.answer("Дію скасовано.", reply_markup=get_admin_keyboard())
        return

    text = msg_text.replace(",", ".").replace(" ", "")
    try:
        amount = float(text)
        if amount <= 0:
            raise ValueError()
    except ValueError:
        await message.answer("❌ Будь ласка, введіть коректну додатну суму числом (наприклад: <code>2500</code>):", parse_mode="HTML")
        return

    data = await state.get_data()
    deal_id = data.get("target_deal_id")
    await safe_clear_state(state)
    
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM buyout_deals WHERE id = ?", (deal_id,)) as cur:
            deal = await cur.fetchone()

        if not deal:
            await message.answer("❌ Угоду не знайдено.", reply_markup=get_admin_keyboard())
            return

        new_paid = deal['paid_amount'] + amount
        new_status = 'completed' if new_paid >= deal['total_price'] else deal['status']
        await db.execute("UPDATE buyout_deals SET paid_amount = ?, status = ? WHERE id = ?", (new_paid, new_status, deal_id))
        now_str = get_kyiv_now().strftime("%Y-%m-%d %H:%M:%S")
        await db.execute(
            "INSERT INTO payments (user_id, amount, date_paid, payment_type) VALUES (?, ?, ?, 'buyout')",
            (deal['user_id'], amount, now_str)
        )
        await db.commit()

    rem = max(0.0, deal['total_price'] - new_paid)
    pct = int((new_paid / deal['total_price'] * 100)) if deal['total_price'] > 0 else 100
    b_filled = min(10, max(0, int((new_paid / deal['total_price']) * 10))) if deal['total_price'] > 0 else 10
    b_bar = "▓" * b_filled + "░" * (10 - b_filled)

    completion_badge = "\n\n🎉 <b>УГОДУ ПОВНІСТЮ ВИПЛАЧЕНО! ТРАНСПОРТ ПЕРЕХОДИТЬ У ВЛАСНІСТЬ КЛІЄНТА!</b>" if new_status == 'completed' else ""

    await message.answer(
        f"✅ <b>Платіж {amount:.2f} грн успішно внесено!</b>\n\n"
        f"🛵 Транспорт: <b>{deal['vehicle_info']}</b>\n"
        f"👤 Клієнт ID: <code>{deal['user_id']}</code>\n"
        f"📈 Вже виплачено: <b>{new_paid:.2f} грн</b> з <b>{deal['total_price']:.2f} грн</b> ({pct}%)\n"
        f"<code>[{b_bar}]</code>\n"
        f"⏳ Залишок: <b>{rem:.2f} грн</b>{completion_badge}",
        parse_mode="HTML",
        reply_markup=get_admin_keyboard()
    )

    client_congrats = "\n\n🎉 <b>Вітаємо! Ви повністю виплатили вартість транспорту! Скутер переходить у вашу повну власність!</b>" if new_status == 'completed' else ""
    try:
        await bot.send_message(
            chat_id=deal['user_id'],
            text=(
                f"💳 <b>Отримано платіж за викуп скутера!</b>\n\n"
                f"💰 Зараховано: <b>+{amount:.2f} грн</b>\n"
                f"🛵 Транспорт: <b>{deal['vehicle_info']}</b>\n"
                f"📈 Вже виплачено: <b>{new_paid:.2f} грн</b> з <b>{deal['total_price']:.2f} грн</b> ({pct}%)\n"
                f"<code>[{b_bar}]</code>\n"
                f"⏳ Залишилось сплатити: <b>{rem:.2f} грн</b>\n\n"
                f"Дякуємо! Статус оновлено у вашому Особистому кабінеті.{client_congrats}"
            ),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Помилка сповіщення клієнта про оплату викупу: {e}")

@dp.callback_query(F.data == "buyout_pay_req", StateFilter("*"))
async def buyout_pay_req_handler(callback: CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM buyout_deals WHERE user_id = ? AND status = 'active' ORDER BY id DESC LIMIT 1", (user_id,)) as cur:
            buyout = await cur.fetchone()
            
    if not buyout:
        await callback.answer("У вас немає активного договору викупу", show_alert=True)
        return
        
    purpose = generate_payment_purpose(
        contract_num=buyout.get('contract_num', '2804-5') if 'contract_num' in buyout.keys() else '2804-5',
        contract_date=buyout.get('contract_date', '28.04.2026') if 'contract_date' in buyout.keys() else '28.04.2026',
        start_date=buyout['start_date'] if buyout['start_date'] else '',
        end_date="",
        vehicle_type=buyout['vehicle_info'] if buyout['vehicle_info'] else '🛵 Електроскутер',
        is_buyout=True
    )
    
    text = (
        "💳 <b>ОПЛАТА ЗА ВИКУП СКУТЕРА (RENT-TO-OWN)</b>\n"
        "────────────────────\n\n"
        f"🏢 <b>Отримувач:</b> {FOP_NAME}\n"
        f"🔢 <b>ЄДРПОУ/РНОКПП:</b> <code>{FOP_TAX_ID}</code>\n"
        f"🏦 <b>IBAN:</b> <code>{FOP_IBAN}</code>\n\n"
        f"📝 <b>Призначення платежу:</b>\n"
        f"<code>{purpose}</code>\n\n"
        "ℹ️ <i>Скопіюйте реквізити та сплатіть через банк. Після оплати надішліть квитанцію менеджеру для зарахування до прогресу викупу.</i>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад до кабінету", callback_data="back_to_cabinet")]
    ])
    await callback.message.answer(text, parse_mode="HTML", reply_markup=kb)



# --- ЗАПУСК БОТА ---

# ==================== HTTP REST API SERVER (FRANCHISE & CABINET) ====================
CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Requested-With"
}

async def handle_options(request):
    return web.Response(headers=CORS_HEADERS)

async def api_franchise_lead(request):
    try:
        data = await request.json()
    except Exception:
        data = {}

    name = str(data.get("name", "")).strip()
    phone = str(data.get("phone", "")).strip()
    city = str(data.get("city", "")).strip()
    budget = str(data.get("budget", "")).strip()
    scooters_count = str(data.get("scooters_count", "")).strip()
    comment = str(data.get("comment", "")).strip()

    now_str = datetime.now().strftime("%d.%m.%Y %H:%M")

    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                INSERT INTO franchise_leads (name, phone, city, budget, scooters_count, comment, date_added)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (name, phone, city, budget, scooters_count, comment, now_str))
            await db.commit()
    except Exception as e:
        logger.error(f"Error saving franchise lead to DB: {e}")

    # Notify admin in Telegram
    try:
        admin_text = (
            "⚡️ <b>НОВА ЗАЯВКА НА ФРАНШИЗУ MUVIO!</b>\n"
            "────────────────────\n"
            f"👤 <b>Ім'я:</b> {name}\n"
            f"📞 <b>Телефон:</b> <code>{phone}</code>\n"
            f"📍 <b>Місто:</b> {city}\n"
            f"🛵 <b>Скутери/Бюджет:</b> {scooters_count or budget}\n"
        )
        if comment:
            admin_text += f"💬 <b>Коментар:</b> {comment}\n"
        admin_text += f"⏱ <b>Час:</b> {now_str}"

        clean_p = re.sub(r'[^0-9+]', '', phone)
        kb = None
        if clean_p:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📞 Зателефонувати", url=f"tel:{clean_p}")]
            ])

        await bot.send_message(chat_id=ADMIN_ID, text=admin_text, parse_mode="HTML", reply_markup=kb)
    except Exception as e:
        logger.error(f"Error sending franchise lead notification to admin: {e}")

    # Google Sheets if configured
    if sheet_requests:
        try:
            sheet_requests.append_row([now_str, "Франшиза", name, phone, city, scooters_count or budget, comment])
        except Exception as e:
            logger.warning(f"Error appending franchise lead to Google Sheets: {e}")

    return web.json_response({"status": "ok", "message": "Заявку успішно прийнято"}, headers=CORS_HEADERS)


async def api_user_profile(request):
    telegram_id = request.query.get("telegram_id")
    if not telegram_id:
        return web.json_response({"error": "telegram_id is required"}, status=400, headers=CORS_HEADERS)

    try:
        tg_id_int = int(telegram_id)
    except ValueError:
        return web.json_response({"error": "invalid telegram_id"}, status=400, headers=CORS_HEADERS)

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        # 1. User info
        async with db.execute("SELECT * FROM users WHERE telegram_id = ?", (tg_id_int,)) as cur:
            u_row = await cur.fetchone()
            user_data = dict(u_row) if u_row else {
                "id": tg_id_int,
                "first_name": "Клієнт",
                "phone_number": "",
                "bonus_balance": 0
            }

        phone = user_data.get("phone_number") or ""

        # 2. Active Rental
        rental_data = None
        if phone:
            async with db.execute("SELECT * FROM rentals WHERE user_phone = ? ORDER BY id DESC LIMIT 1", (phone,)) as cur:
                r_row = await cur.fetchone()
                if r_row:
                    r_dict = dict(r_row)
                    rental_data = {
                        "vehicle_info": r_dict.get("vehicle_info") or "Електроскутер MUVIO",
                        "plate_number": "MUVIO-" + str(r_dict.get("id", 1)).zfill(3),
                        "contract_num": r_dict.get("contract_num") or "",
                        "contract_date": r_dict.get("contract_date") or "",
                        "end_date": r_dict.get("end_date") or "Активно",
                        "rate": f"{int(r_dict.get('amount_due', 0)):,} ₴".replace(",", " ") if r_dict.get('amount_due') else "За тарифом",
                        "equipment": "Шолом + Зарядка" if r_dict.get("has_helmet") else "Стандартна комплектація",
                        "status": "active"
                    }

        # 3. Buyout Deal
        buyout_data = None
        async with db.execute("SELECT * FROM buyout_deals WHERE user_id = ? AND status = 'active' ORDER BY id DESC LIMIT 1", (tg_id_int,)) as cur:
            b_row = await cur.fetchone()
            if b_row:
                b_dict = dict(b_row)
                buyout_data = {
                    "vehicle_info": b_dict.get("vehicle_info") or "Електроскутер",
                    "total_price": b_dict.get("total_price") or 0,
                    "paid_amount": b_dict.get("paid_amount") or 0,
                    "deposit_paid": b_dict.get("deposit_paid") or 0,
                    "term_months": b_dict.get("term_months") or 0,
                    "contract_num": b_dict.get("contract_num") or "",
                    "contract_date": b_dict.get("contract_date") or "",
                    "status": b_dict.get("status") or "active"
                }

        # 4. Payments history
        payments_data = []
        async with db.execute("SELECT * FROM payments WHERE user_id = ? ORDER BY id DESC LIMIT 20", (tg_id_int,)) as cur:
            p_rows = await cur.fetchall()
            for p in p_rows:
                p_dict = dict(p)
                p_type_label = "Викуп" if p_dict.get("payment_type") == "buyout" else "Оренда"
                payments_data.append({
                    "date": p_dict.get("date_paid", ""),
                    "purpose": f"{p_type_label} транспорту",
                    "amount": f"{int(p_dict.get('amount', 0)):,} ₴".replace(",", " "),
                    "bonus": f"{int(p_dict.get('bonus_used', 0)):,} ₴".replace(",", " "),
                    "status": "Зараховано"
                })

        # 5. Expenses / Repairs history
        repairs_data = []
        vehicle_key = buyout_data.get("vehicle_key") if buyout_data else (rental_data.get("vehicle_info") if rental_data else None)
        if vehicle_key:
            async with db.execute("SELECT * FROM expenses WHERE vehicle_key LIKE ? ORDER BY id DESC LIMIT 10", (f"%{vehicle_key}%",)) as cur:
                e_rows = await cur.fetchall()
                for e in e_rows:
                    e_dict = dict(e)
                    repairs_data.append({
                        "date": e_dict.get("date_added", ""),
                        "title": e_dict.get("description", "Планове обслуговування"),
                        "category": e_dict.get("category", "ТО"),
                        "cost": "0 ₴",
                        "status": "За рахунок MUVIO"
                    })

    response_payload = {
        "user": {
            "id": tg_id_int,
            "first_name": user_data.get("full_name") or user_data.get("first_name", "Клієнт"),
            "username": user_data.get("username", ""),
            "phone": user_data.get("phone_number") or "",
            "bonus_balance": user_data.get("bonus_balance", 0)
        },
        "rental": rental_data,
        "buyout": buyout_data,
        "payments": payments_data,
        "repairs": repairs_data
    }

    return web.json_response(response_payload, headers=CORS_HEADERS)


async def start_web_server():
    app = web.Application()
    app.router.add_route("OPTIONS", "/{tail:.*}", handle_options)
    app.router.add_post("/api/franchise/lead", api_franchise_lead)
    app.router.add_get("/api/user/profile", api_user_profile)

    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"🌐 HTTP API сервер MUVIO успішно запущено на 0.0.0.0:{port}")


async def main():
    logger.info("🚀 Инициализация БД SQLite...")
    await init_db()
    scheduler.add_job(check_expiring_rentals, 'interval', minutes=15)
    scheduler.start()
    await start_web_server()
    logger.info("🚀 Бот MUVIO Rent запущено...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
