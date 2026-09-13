#!/usr/bin/env python3
"""
MUVIO Google Sheets Analytics Migration Script
Retroactively cleans existing rows in 'Аналітика нових клієнтів' / 'Аналитика нових клієнтів' in MUVIO_Rent_CRM.
- Maps raw developer callbacks in Column D to clean Ukrainian labels
- Infers proper Category in Column C (Навігація, Каталог, Бронювання, Кабінет)
- Drops useless 'ignore_pagination' rows
- Batch-updates Google Sheet in a single request to avoid 429 quota limits
"""

import os
import sys
import json
import logging
import gspread
from oauth2client.service_account import ServiceAccountCredentials

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("migration")

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CREDENTIALS_FILE = os.path.join(BASE_DIR, "credentials.json")
FLEET_FILE = os.path.join(BASE_DIR, "fleet.json")
SPREADSHEET_NAME = "MUVIO_Rent_CRM"
SHEET_CANDIDATE_NAMES = ["Аналітика нових клієнтів", "Аналитика нових клієнтів"]

# Load fleet for accurate model names
FLEET = {}
if os.path.exists(FLEET_FILE):
    try:
        with open(FLEET_FILE, "r", encoding="utf-8") as f:
            FLEET = json.load(f)
    except Exception as e:
        logger.warning(f"Could not load fleet.json: {e}")

def get_model_name(slug: str) -> str:
    slug_norm = slug.lower().replace("-", "_").strip()
    if slug_norm in FLEET:
        return FLEET[slug_norm].get("name", slug.replace("_", " ").title())
    for k, v in FLEET.items():
        if k.replace("-", "_") == slug_norm:
            return v.get("name", slug.replace("_", " ").title())
    return slug.replace("_", " ").replace("-", " ").title()

CAT_MAP = {
    "all": "Всі моделі",
    "available": "В наявності",
    "scooter": "Скутери",
    "bike": "Електровелосипеди",
}

PERIOD_MAP = {
    "1_doba": "1 доба",
    "1_tyzhden": "1 тиждень",
    "1_misyats": "1 місяць (28 днів)",
    "1": "1 доба",
    "7": "1 тиждень",
    "28": "1 місяць",
}

def map_analytics_event(col_c: str, raw_action: str):
    """
    Maps raw callback / action and previous category into (category, action_text).
    Returns None if the event should be dropped (e.g. ignore_pagination).
    """
    raw = str(raw_action).strip() if raw_action is not None else ""
    
    # 1. Noise Filter: drop empty or ignore_pagination
    if not raw or raw == "ignore_pagination":
        return None

    category = "Навігація"
    action_text = raw

    # 2. Known explicit callbacks
    if raw == "confirm_rent_booking":
        category = "Бронювання"
        action_text = "✅ Підтвердив бронювання оренди"
    elif raw == "cancel_booking":
        category = "Бронювання"
        action_text = "❌ Скасував бронювання"
    elif raw == "usr_rent_request":
        category = "Бронювання"
        action_text = "📝 Натиснув: Залишити заявку на оренду"
    elif raw.startswith("book_") or raw == "book":
        category = "Бронювання"
        if raw == "book":
            action_text = "🛵 Забронювати"
        else:
            model_slug = raw[5:]
            m_name = get_model_name(model_slug)
            action_text = f"🛵 Обрав модель: {m_name}"
    elif raw.startswith("gallery_filter:"):
        category = "Каталог"
        parts = raw.split(":")
        c_code = parts[1] if len(parts) > 1 else "all"
        c_name = CAT_MAP.get(c_code, c_code.replace("_", " ").title())
        action_text = f"🔍 Фільтр каталогу: {c_name}"
    elif raw.startswith("gallery_next:"):
        category = "Каталог"
        parts = raw.split(":")
        c_code = parts[1] if len(parts) > 1 else "all"
        idx = parts[2] if len(parts) > 2 else "0"
        c_name = CAT_MAP.get(c_code, c_code.replace("_", " ").title())
        p_num = int(idx) + 1 if idx.isdigit() else idx
        action_text = f"➡️ Гортає каталог ({c_name}, стор. {p_num})"
    elif raw.startswith("gallery_prev:"):
        category = "Каталог"
        parts = raw.split(":")
        c_code = parts[1] if len(parts) > 1 else "all"
        idx = parts[2] if len(parts) > 2 else "0"
        c_name = CAT_MAP.get(c_code, c_code.replace("_", " ").title())
        p_num = int(idx) + 1 if idx.isdigit() else idx
        action_text = f"⬅️ Гортає каталог ({c_name}, стор. {p_num})"
    elif raw.startswith("rent_period:"):
        category = "Бронювання"
        period_key = raw.split(":", 1)[1]
        p_text = PERIOD_MAP.get(period_key, period_key.replace("_", " "))
        action_text = f"⏱ Період оренди: {p_text}"
    elif raw.startswith("helmets:"):
        category = "Бронювання"
        h_val = raw.split(":", 1)[1]
        if h_val == "0":
            action_text = "🪖 Шоломи: Без шолома (маю свій)"
        elif h_val == "1":
            action_text = "🪖 Шоломи: 1 шолом"
        elif h_val == "2":
            action_text = "🪖 Шоломи: 2 шоломи"
        else:
            action_text = f"🪖 Шоломи: {h_val}"
    elif raw.startswith("join_waitlist:"):
        category = "Каталог"
        w_item = raw.split(":", 1)[1]
        w_name = get_model_name(w_item) if w_item != "any" else "Будь-яка модель"
        action_text = f"⏳ Встати в лист очікування: {w_name}"
    elif raw.startswith("c_calc:"):
        category = "Бронювання"
        action_text = "🤝 Заявка на викуп з сайту"
    elif "Особистий кабінет" in raw or raw.startswith("cabinet_") or raw in ["back_to_cabinet", "client_buyout_menu"]:
        category = "Кабінет"
        action_text = raw if any(ord(c) > 127 for c in raw) else raw.replace("_", " ").title()
    elif "Каталог" in raw:
        category = "Каталог"
        action_text = raw
    elif "доставка" in raw or "новачок" in raw or "досвід" in raw or raw.startswith("🍕") or raw.startswith("🐣") or raw.startswith("🛵 Так"):
        category = "Бронювання"
        action_text = raw
    elif raw == "/start":
        category = "Навігація"
        action_text = "🚀 Запуск бота (/start)"
    elif any(ord(c) > 127 for c in raw):
        # Existing valid Ukrainian label
        if col_c and col_c not in ["—", "start", "-", ""]:
            category = col_c
        else:
            low = raw.lower()
            if "умови" in low or "правил" in low or "меню" in low:
                category = "Навігація"
            elif "каталог" in low or "модел" in low or "скутер" in low:
                category = "Каталог"
            elif "кабінет" in low or "профіль" in low:
                category = "Кабінет"
            else:
                category = "Бронювання"
        action_text = raw
    else:
        # Fallback for unmapped developer strings or inputs
        if raw.isdigit():
            category = "Бронювання"
            action_text = f"Введення віку/значення: {raw}"
        else:
            category = "Навігація" if "menu" in raw or "back" in raw else "Бронювання"
            action_text = raw.replace("_", " ").strip().capitalize()

    return category, action_text

def run_migration():
    if not os.path.exists(CREDENTIALS_FILE):
        logger.error(f"Credentials file not found at {CREDENTIALS_FILE}")
        sys.exit(1)

    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
    client = gspread.authorize(creds)

    logger.info(f"Connecting to Google Spreadsheet '{SPREADSHEET_NAME}'...")
    spreadsheet = client.open(SPREADSHEET_NAME)

    worksheet = None
    for name in SHEET_CANDIDATE_NAMES:
        try:
            worksheet = spreadsheet.worksheet(name)
            logger.info(f"Found worksheet: '{name}'")
            break
        except gspread.WorksheetNotFound:
            continue

    if not worksheet:
        logger.error(f"Worksheet not found. Checked candidate names: {SHEET_CANDIDATE_NAMES}")
        sys.exit(1)

    all_rows = worksheet.get_all_values()
    logger.info(f"Retrieved {len(all_rows)} rows from sheet (including header).")

    if not all_rows:
        logger.warning("Worksheet is empty. Nothing to migrate.")
        return

    # Backup existing data to json file
    backup_file = os.path.join(BASE_DIR, "analytics_sheet_backup.json")
    with open(backup_file, "w", encoding="utf-8") as bf:
        json.dump(all_rows, bf, ensure_ascii=False, indent=2)
    logger.info(f"Saved local backup to {backup_file}")

    cleaned_rows = []
    dropped_count = 0

    for idx, row in enumerate(all_rows[1:], start=2):
        ts = row[0] if len(row) > 0 else ""
        user = row[1] if len(row) > 1 else ""
        col_c = row[2] if len(row) > 2 else "—"
        col_d = row[3] if len(row) > 3 else ""

        mapped = map_analytics_event(col_c, col_d)
        if mapped is None:
            dropped_count += 1
            logger.info(f"Row {idx}: DROPPED useless row ('{col_d}')")
            continue

        cat, act = mapped
        cleaned_rows.append([ts, user, cat, act])

    new_header = ["Час", "Користувач (ID / @username)", "Категорія", "Дія"]
    logger.info(f"Migration summary: {len(all_rows)-1} original data rows -> {dropped_count} dropped, {len(cleaned_rows)} cleaned rows.")

    # Batch update to Google Sheets
    logger.info("Executing batch update to Google Sheets in place...")
    worksheet.clear()
    data_to_write = [new_header] + cleaned_rows
    worksheet.update(values=data_to_write, range_name=f"A1:D{len(data_to_write)}")

    logger.info("Batch update completed successfully!")

    # Verify
    verify_rows = worksheet.get_all_values()
    logger.info(f"Verification: sheet now has {len(verify_rows)} rows. Header: {verify_rows[0]}")
    logger.info("Sample cleaned rows:")
    for r in verify_rows[1:6]:
        logger.info(f"  {r}")

if __name__ == "__main__":
    run_migration()
