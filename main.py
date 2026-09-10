import asyncio
import sqlite3
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
import aiohttp
from datetime import datetime
from aiogram import Router
import json
import sys

# Устанавливаем кодировку UTF-8 для всего приложения
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# ============================================================================
# ⚙️ КОНФИГУРАЦИЯ
# ============================================================================

API_TOKEN = '8897276602:AAEPkqv_eGeY3PSk6uyC0zj5yfz389KFJxs'
ADMIN_IDS = [6305430094]  # ID администраторов через запятую

# 🏦 ЮKassa
YOOKASSA_SHOP_ID = 'ВАШ_SHOP_ID_ЮКАССА'
YOOKASSA_SECRET_KEY = 'ВАШ_СЕКРЕТНЫЙ_КЛЮЧ_ЮКАССА'

# Настройка таймаутов для Windows
TIMEOUT = aiohttp.ClientTimeout(total=30, connect=10, sock_read=25, sock_connect=10)

# Инициализация бота
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()
dp.include_router(router)

# ============================================================================
# 🗃️ БАЗА ДАННЫХ
# ============================================================================

def init_database():
    """Инициализация и обновление базы данных"""
    conn = sqlite3.connect('telegram_stars.db', check_same_thread=False, timeout=30)
    cursor = conn.cursor()
    
    # Проверяем существование таблиц
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        full_name TEXT,
        reg_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Создаем таблицу purchases
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS purchases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        order_id TEXT UNIQUE,
        stars_count INTEGER,
        amount_rub INTEGER,
        payment_id TEXT,
        payment_method TEXT DEFAULT 'yookassa',
        status TEXT DEFAULT 'waiting_payment',
        admin_notified INTEGER DEFAULT 0,
        admin_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        completed_at TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (user_id)
    )
    ''')
    
    conn.commit()
    return conn

# Инициализируем базу данных
conn = init_database()
cursor = conn.cursor()

# ============================================================================
# 📝 ЛОГИРОВАНИЕ
# ============================================================================

# Логирование с UTF-8
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================================================================
# 🎨 ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================================

def format_price(price: int) -> str:
    """Форматирование цены"""
    return f"{price:,}".replace(',', ' ')

# ============================================================================
# 🚀 ОСНОВНЫЕ КОМАНДЫ
# ============================================================================

@router.message(Command("start"))
async def cmd_start(message: Message):
    try:
        user_id = message.from_user.id
        username = message.from_user.username or ""
        full_name = message.from_user.full_name or ""
        
        # Регистрация пользователя
        cursor.execute(
            'INSERT OR IGNORE INTO users (user_id, username, full_name) VALUES (?, ?, ?)',
            (user_id, username, full_name)
        )
        conn.commit()
        
        # Главное меню
        keyboard = types.ReplyKeyboardMarkup(
            keyboard=[
                [types.KeyboardButton(text="⭐️ Купить Telegram Stars")],
                [types.KeyboardButton(text="📋 Мои заказы")],
                [types.KeyboardButton(text="💳 Способы оплаты")]
            ],
            resize_keyboard=True
        )
        
        if user_id in ADMIN_IDS:
            keyboard.keyboard.append([types.KeyboardButton(text="👑 Админ-панель")])
        
        await message.answer(
            "🌟 <b>Добро пожаловать в магазин Telegram Stars!</b>\n\n"
            "Здесь вы можете приобрести Stars для Telegram-каналов.\n"
            "После оплаты администратор вручную выдаст вам звёзды.\n\n"
            "<b>✅ Доступные способы оплаты:</b>\n"
            "• 💳 Банковская карта (ЮKassa)\n"
            "• 🤝 Перевод на карту",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Ошибка в cmd_start: {e}")
        await message.answer("❌ Произошла ошибка. Пожалуйста, попробуйте позже.")

@router.message(F.text == "💳 Способы оплаты")
async def show_payment_methods(message: Message):
    """Показать способы оплаты"""
    payment_info = (
        "<b>💳 СПОСОБЫ ОПЛАТЫ</b>\n\n"
        
        "<b>1️⃣ ЮKassa (банковские карты)</b>\n"
        "• 💳 Visa, Mastercard, Мир\n"
        "• 🏦 Карты любых банков\n"
        "• 🔒 Безопасно и защищено\n"
        "• ⚡ Мгновенное подтверждение\n\n"
        
        "<b>2️⃣ Перевод на карту</b>\n"
        "• 🏦 Ручной перевод на карту\n"
        "• 👤 Контакт с администратором\n"
        "• 📞 Персональный подход\n\n"
        
        "<b>🎯 Рекомендуем:</b>\n"
        "• ЮKassa для быстрой оплаты картой\n"
        "• Перевод на карту для анонимных покупок\n\n"
        
        "<b>👇 Выберите способ при оформлении заказа!</b>"
    )
    
    await message.answer(payment_info, parse_mode="HTML")

# ============================================================================
# 🛒 КАТАЛОГ И ЗАКАЗЫ
# ============================================================================

@router.message(F.text == "⭐️ Купить Telegram Stars")
async def show_stars_packs(message: Message):
    try:
        # Пакеты звезд
        packs = [
            ("100 Stars - 115 руб.", 100, 115),
            ("250 Stars - 275 руб.", 250, 275),
            ("500 Stars - 525 руб.", 500, 525),
            ("1000 Stars - 1050 руб.", 1000, 1050),
            ("2500 Stars - 2625 руб.", 2500, 2625),
            ("5000 Stars - 5250 руб.", 5000, 5250),
        ]
        
        buttons = []
        for pack_name, stars, price in packs:
            callback_data = f"buy_pack_{stars}_{price}"
            buttons.append([types.InlineKeyboardButton(
                text=pack_name, 
                callback_data=callback_data
            )])
        
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=buttons)
        
        await message.answer(
            "<b>🎁 Выберите пакет Telegram Stars:</b>\n\n"
            "<b>💎 Stars - это внутренняя валюта Telegram для поддержки авторов</b>\n"
            "<b>1 Star ≈ 1.15 руб.</b>\n\n"
            "После оплаты администратор свяжется с вами для выдачи Stars.",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Ошибка в show_stars_packs: {e}")
        await message.answer("❌ Произошла ошибка при загрузке пакетов.")

# ============================================================================
# 🔄 ОБРАБОТКА ВЫБОРА ПАКЕТА И СПОСОБА ОПЛАТЫ
# ============================================================================

@router.callback_query(F.data.startswith('buy_pack_'))
async def process_pack_selection(callback_query: CallbackQuery):
    """Обработка выбора пакета звезд"""
    try:
        data_parts = callback_query.data.split('_')
        stars = int(data_parts[2])
        price = int(data_parts[3])
        
        # Предлагаем выбрать способ оплаты
        payment_keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="💳 Банковская карта (ЮKassa)", callback_data=f"method_yookassa_{stars}_{price}")],
            [types.InlineKeyboardButton(text="🤝 Перевод на карту", callback_data=f"method_card_{stars}_{price}")]
        ])
        
        await callback_query.message.answer(
            f"<b>✅ Вы выбрали: {stars} Stars за {format_price(price)} руб.</b>\n\n"
            "<b>💳 Выберите способ оплаты:</b>\n\n"
            "<b>• 💳 Банковская карта</b> - оплата картой через ЮKassa\n"
            "<b>• 🤝 Перевод на карту</b> - ручной перевод (контакт с админом)",
            reply_markup=payment_keyboard,
            parse_mode="HTML"
        )
        
        await callback_query.answer()
        
    except Exception as e:
        logger.error(f"Ошибка в process_pack_selection: {e}")
        await callback_query.message.answer("❌ Произошла ошибка при обработке заказа.")
        await callback_query.answer()

# ============================================================================
# 💳 ОПЛАТА ЧЕРЕЗ ЮKASSA (БАНКОВСКИЕ КАРТЫ)
# ============================================================================

@router.callback_query(F.data.startswith('method_yookassa_'))
async def process_yookassa_payment(callback_query: CallbackQuery):
    """Обработка оплаты через ЮKassa"""
    try:
        data_parts = callback_query.data.split('_')
        stars = int(data_parts[2])
        price = int(data_parts[3])
        user_id = callback_query.from_user.id
        
        # Создаем запись о покупке
        order_id = f"YK_{user_id}_{int(datetime.now().timestamp())}"
        
        cursor.execute(
            '''INSERT INTO purchases 
               (user_id, order_id, stars_count, amount_rub, payment_method, status) 
               VALUES (?, ?, ?, ?, ?, ?)''',
            (user_id, order_id, stars, price, 'yookassa', 'creating_payment')
        )
        conn.commit()
        
        purchase_id = cursor.lastrowid
        
        # Создаем платеж в ЮKassa
        payment_data = {
            "amount": {
                "value": f"{price}.00",
                "currency": "RUB"
            },
            "capture": True,
            "confirmation": {
                "type": "redirect",
                "return_url": f"https://t.me/{callback_query.from_user.username}" if callback_query.from_user.username else "https://t.me"
            },
            "description": f"Покупка {stars} Telegram Stars",
            "metadata": {
                "purchase_id": purchase_id,
                "user_id": user_id,
                "order_id": order_id
            }
        }
        
        headers = {
            "Content-Type": "application/json",
            "Idempotence-Key": str(purchase_id)
        }
        
        auth = aiohttp.BasicAuth(YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY)
        
        await callback_query.message.answer("<b>⏳ Создаем платеж через ЮKassa...</b>", parse_mode="HTML")
        
        async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
            try:
                async with session.post(
                    "https://api.yookassa.ru/v3/payments",
                    json=payment_data,
                    headers=headers,
                    auth=auth
                ) as resp:
                    if resp.status == 200:
                        payment_info = await resp.json()
                        payment_id = payment_info['id']
                        confirmation_url = payment_info['confirmation']['confirmation_url']
                        
                        # Обновляем запись
                        cursor.execute(
                            'UPDATE purchases SET payment_id = ?, status = ? WHERE id = ?',
                            (payment_id, 'waiting_payment', purchase_id)
                        )
                        conn.commit()
                        
                        # Отправляем ссылку на оплату
                        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
                            [types.InlineKeyboardButton(text="💳 Перейти к оплате", url=confirmation_url)],
                            [types.InlineKeyboardButton(text="✅ Проверить оплату", callback_data=f"check_yk_{purchase_id}")]
                        ])
                        
                        await callback_query.message.answer(
                            f"<b>💳 ОПЛАТА ЧЕРЕЗ ЮKASSA</b>\n\n"
                            f"<b>🛒 Заказ #{purchase_id}</b>\n"
                            f"<b>⭐️ {stars} Telegram Stars</b>\n"
                            f"<b>💰 {format_price(price)} руб.</b>\n\n"
                            f"<b>👇 Нажмите кнопку для оплаты:</b>\n"
                            f"• Поддерживаются Visa, Mastercard, Мир\n"
                            f"• Оплата защищена ЮKassa\n"
                            f"• Подтверждение мгновенно",
                            reply_markup=keyboard,
                            parse_mode="HTML"
                        )
                    else:
                        error_text = await resp.text()
                        logger.error(f"Ошибка ЮKassa: {error_text}")
                        await callback_query.message.answer(
                            "❌ Ошибка при создании платежа. Попробуйте другой способ оплаты."
                        )
                        
                        # Предлагаем другие способы оплаты
                        retry_keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
                            [types.InlineKeyboardButton(text="🤝 Перевод на карту", callback_data=f"method_card_{stars}_{price}")]
                        ])
                        await callback_query.message.answer("Выберите другой способ оплаты:", reply_markup=retry_keyboard)
                        
            except asyncio.TimeoutError:
                await callback_query.message.answer("<b>⏰ Превышено время ожидания. Попробуйте другой способ оплаты.</b>", parse_mode="HTML")
            except Exception as e:
                logger.error(f"Ошибка соединения с ЮKassa: {e}")
                await callback_query.message.answer("❌ Ошибка соединения. Попробуйте другой способ оплаты.")
        
        await callback_query.answer()
        
    except Exception as e:
        logger.error(f"Ошибка в process_yookassa_payment: {e}")
        await callback_query.message.answer("❌ Произошла ошибка при создании платежа.")
        await callback_query.answer()

# ============================================================================
# 🤝 ПЕРЕВОД НА КАРТУ (МАНУАЛЬНЫЙ СПОСОБ)
# ============================================================================

@router.callback_query(F.data.startswith('method_card_'))
async def process_card_transfer(callback_query: CallbackQuery):
    """Обработка оплаты переводом на карту"""
    try:
        data_parts = callback_query.data.split('_')
        stars = int(data_parts[2])
        price = int(data_parts[3])
        user_id = callback_query.from_user.id
        
        # Создаем запись о покупке
        order_id = f"CARD_{user_id}_{int(datetime.now().timestamp())}"
        
        cursor.execute(
            '''INSERT INTO purchases 
               (user_id, order_id, stars_count, amount_rub, payment_method, status) 
               VALUES (?, ?, ?, ?, ?, ?)''',
            (user_id, order_id, stars, price, 'card_transfer', 'waiting_payment')
        )
        conn.commit()
        
        purchase_id = cursor.lastrowid
        
        # Получаем информацию о пользователе
        cursor.execute(
            'SELECT username, full_name FROM users WHERE user_id = ?',
            (user_id,)
        )
        user_info = cursor.fetchone()
        username = user_info[0] if user_info and user_info[0] else "Нет username"
        full_name = user_info[1] if user_info else ""
        
        # Уведомление администраторам о новом заказе с оплатой на карту
        admin_message = (
            f"<b>🤝 НОВЫЙ ЗАКАЗ С ОПЛАТОЙ НА КАРТУ</b>\n\n"
            f"<b>🛒 Заказ #{purchase_id}</b>\n"
            f"<b>⭐️ {stars} Telegram Stars</b>\n"
            f"<b>💰 {format_price(price)} руб.</b>\n\n"
            f"<b>👤 Покупатель:</b>\n"
            f"• Имя: {full_name}\n"
            f"• Юзернейм: @{username}\n"
            f"• ID: {user_id}\n\n"
            f"<b>💳 Ожидает перевода на карту</b>\n"
            f"<b>📅 Время: {datetime.now().strftime('%H:%M %d.%m.%Y')}</b>\n\n"
            f"<b>🎯 Действия:</b>\n"
            f"1. Отправьте реквизиты карты покупателю\n"
            f"2. После оплаты подтвердите заказ\n"
            f"3. Выдайте Stars через меню канала"
        )
        
        admin_keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="✅ Подтвердить оплату", callback_data=f"confirm_card_{purchase_id}")],
            [types.InlineKeyboardButton(text="❌ Отменить заказ", callback_data=f"cancel_card_{purchase_id}")]
        ])
        
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(admin_id, admin_message, reply_markup=admin_keyboard, parse_mode="HTML")
            except Exception as e:
                logger.error(f"Не удалось отправить админу {admin_id}: {e}")
        
        # Инструкции для пользователя
        user_instructions = (
            f"<b>🤝 ОПЛАТА ПЕРЕВОДОМ НА КАРТУ</b>\n\n"
            f"<b>🛒 Заказ #{purchase_id}</b>\n"
            f"<b>⭐️ {stars} Telegram Stars</b>\n"
            f"<b>💰 {format_price(price)} руб.</b>\n\n"
            f"<b>✅ Ваш заказ принят!</b>\n\n"
            f"<b>📞 Далее вам нужно:</b>\n"
            f"1. Администратор свяжется с вами в ближайшее время\n"
            f"2. Вы получите реквизиты карты для оплаты\n"
            f"3. Совершите перевод на указанную карту\n"
            f"4. Отправьте скриншот чека администратору\n"
            f"5. Получите подтверждение оплаты\n"
            f"6. Администратор выдаст вам Stars\n\n"
            f"<b>⏳ Обычно это занимает 10-30 минут</b>\n\n"
            f"<b>📱 Статус заказа:</b> Ожидает связи с администратором\n\n"
            f"<b>🎯 Номер заказа для связи:</b> <code>#{purchase_id}</code>"
        )
        
        await callback_query.message.answer(user_instructions, parse_mode="HTML")
        
        await callback_query.answer()
        
    except Exception as e:
        logger.error(f"Ошибка в process_card_transfer: {e}")
        await callback_query.message.answer("❌ Произошла ошибка при создании заказа.")
        await callback_query.answer()

# ============================================================================
# ✅ ПРОВЕРКА ОПЛАТЫ ЮKASSA
# ============================================================================

@router.callback_query(F.data.startswith('check_yk_'))
async def check_yookassa_payment(callback_query: CallbackQuery):
    """Проверка оплаты через ЮKassa"""
    try:
        purchase_id = int(callback_query.data.split('_')[2])
        user_id = callback_query.from_user.id
        
        # Получаем информацию о покупке
        cursor.execute(
            'SELECT payment_id, status, stars_count, amount_rub FROM purchases WHERE id = ? AND user_id = ?',
            (purchase_id, user_id)
        )
        purchase = cursor.fetchone()
        
        if not purchase:
            await callback_query.answer("Покупка не найдена", show_alert=True)
            return
        
        payment_id, status, stars, amount = purchase
        
        if status == 'completed':
            await callback_query.answer("✅ Оплата уже подтверждена", show_alert=True)
            return
        
        if status != 'waiting_payment':
            await callback_query.answer("Статус платежа неизвестен", show_alert=True)
            return
        
        # Проверяем статус в ЮKassa
        auth = aiohttp.BasicAuth(YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY)
        
        async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
            try:
                async with session.get(
                    f"https://api.yookassa.ru/v3/payments/{payment_id}",
                    auth=auth
                ) as resp:
                    if resp.status == 200:
                        payment_info = await resp.json()
                        payment_status = payment_info['status']
                        
                        if payment_status == 'succeeded':
                            # Обновляем статус
                            cursor.execute(
                                'UPDATE purchases SET status = ? WHERE id = ?',
                                ('paid', purchase_id)
                            )
                            conn.commit()
                            
                            # Уведомляем пользователя
                            await callback_query.message.answer(
                                f"<b>✅ Оплата подтверждена!</b>\n\n"
                                f"<b>🛒 Покупка #{purchase_id}</b>\n"
                                f"<b>⭐️ {stars} Telegram Stars</b>\n"
                                f"<b>💰 {amount} руб.</b>\n\n"
                                f"<b>📞 Администратор получил уведомление и скоро выдаст вам Stars.</b>\n"
                                f"Обычно это занимает 5-15 минут.",
                                parse_mode="HTML"
                            )
                            
                            # Уведомляем всех администраторов
                            admin_keyboard = types.InlineKeyboardMarkup(inline_keyboard=[[
                                types.InlineKeyboardButton(
                                    text="✅ Stars выданы",
                                    callback_data=f"admin_complete_{purchase_id}"
                                )
                            ]])
                            
                            admin_message = (
                                f"<b>💳 НОВАЯ ОПЛАТА ЧЕРЕЗ ЮKASSA</b>\n\n"
                                f"<b>🛒 Заказ #{purchase_id}</b>\n"
                                f"<b>👤 Покупатель: @{callback_query.from_user.username or 'нет юзернейма'}</b>\n"
                                f"<b>🆔 ID: {user_id}</b>\n"
                                f"<b>⭐️ Количество: {stars} Stars</b>\n"
                                f"<b>💰 Сумма: {amount} руб.</b>\n"
                                f"<b>📅 Время: {datetime.now().strftime('%H:%M %d.%m.%Y')}</b>\n\n"
                                f"<b>✅ Оплата прошла успешно через ЮKassa!</b>\n\n"
                                f"Выдайте пользователю {stars} Telegram Stars\n"
                                f"через меню канала, затем нажмите кнопку ниже."
                            )
                            
                            for admin_id in ADMIN_IDS:
                                try:
                                    await bot.send_message(
                                        admin_id,
                                        admin_message,
                                        reply_markup=admin_keyboard,
                                        parse_mode="HTML"
                                    )
                                except Exception as e:
                                    logger.error(f"Не удалось отправить админу {admin_id}: {e}")
                            
                            await callback_query.answer(
                                "✅ Оплата подтверждена! Администратор уведомлен.",
                                show_alert=True
                            )
                        
                        elif payment_status == 'pending':
                            await callback_query.answer(
                                "⏳ Платеж в обработке. Подождите несколько минут и проверьте снова.",
                                show_alert=True
                            )
                        else:
                            await callback_query.answer(
                                f"Статус платежа: {payment_status}",
                                show_alert=True
                            )
                    else:
                        await callback_query.answer(
                            "Ошибка при проверке платежа. Попробуйте позже.",
                            show_alert=True
                        )
            except Exception as e:
                logger.error(f"Ошибка проверки платежа ЮKassa: {e}")
                await callback_query.answer(
                    "Ошибка при проверке платежа. Попробуйте позже.",
                    show_alert=True
                )
                
    except Exception as e:
        logger.error(f"Ошибка в check_yookassa_payment: {e}")
        await callback_query.answer(
            "Произошла ошибка. Попробуйте позже.",
            show_alert=True
        )

# ============================================================================
# 👑 АДМИН-ПАНЕЛЬ
# ============================================================================

@router.callback_query(F.data.startswith('confirm_card_'), F.from_user.id.in_(ADMIN_IDS))
async def admin_confirm_card_payment(callback_query: CallbackQuery):
    """Админ подтверждает оплату переводом на карту"""
    try:
        purchase_id = int(callback_query.data.split('_')[2])
        
        # Получаем информацию о покупке
        cursor.execute('''
            SELECT p.user_id, p.stars_count, p.amount_rub, u.username, u.full_name 
            FROM purchases p
            JOIN users u ON p.user_id = u.user_id
            WHERE p.id = ? AND p.status = 'waiting_payment'
        ''', (purchase_id,))
        
        purchase = cursor.fetchone()
        
        if not purchase:
            await callback_query.answer("Покупка не найдена или уже обработана", show_alert=True)
            return
        
        user_id, stars, amount, username, full_name = purchase
        
        # Обновляем статус
        cursor.execute(
            'UPDATE purchases SET status = ?, admin_id = ?, completed_at = CURRENT_TIMESTAMP WHERE id = ?',
            ('completed', callback_query.from_user.id, purchase_id)
        )
        conn.commit()
        
        # Уведомляем покупателя
        try:
            await bot.send_message(
                user_id,
                f"<b>🎉 ОПЛАТА ПОДТВЕРЖДЕНА!</b>\n\n"
                f"<b>✅ Администратор получил ваш перевод на карту.</b>\n"
                f"<b>🛒 Номер покупки: #{purchase_id}</b>\n"
                f"<b>⭐️ Количество: {stars} Telegram Stars</b>\n"
                f"<b>💰 Сумма: {format_price(amount)} руб.</b>\n\n"
                f"Администратор выдал вам {stars} Telegram Stars.\n\n"
                f"<b>Спасибо за покупку! 🚀</b>",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Не удалось уведомить пользователя {user_id}: {e}")
        
        # Обновляем сообщение админу
        await callback_query.message.edit_text(
            text=f"<b>✅ ОПЛАТА НА КАРТУ ПОДТВЕРЖДЕНА</b>\n\n"
                 f"<b>📋 Заказ #{purchase_id}</b>\n"
                 f"<b>👤 {full_name} (@{username})</b>\n"
                 f"<b>⭐️ {stars} Stars выданы</b>\n"
                 f"<b>💰 {format_price(amount)} руб.</b>\n"
                 f"<b>👑 Подтвердил: @{callback_query.from_user.username or 'админ'}</b>\n"
                 f"<b>⏰ {datetime.now().strftime('%H:%M %d.%m.%Y')}</b>",
            reply_markup=None,
            parse_mode="HTML"
        )
        
        await callback_query.answer("✅ Оплата на карту подтверждена")
        
    except Exception as e:
        logger.error(f"Ошибка в admin_confirm_card_payment: {e}")
        await callback_query.answer("❌ Произошла ошибка", show_alert=True)

@router.callback_query(F.data.startswith('cancel_card_'), F.from_user.id.in_(ADMIN_IDS))
async def admin_cancel_card_payment(callback_query: CallbackQuery):
    """Админ отменяет заказ с оплатой на карту"""
    try:
        purchase_id = int(callback_query.data.split('_')[2])
        
        # Обновляем статус
        cursor.execute(
            'UPDATE purchases SET status = ? WHERE id = ?',
            ('cancelled', purchase_id)
        )
        conn.commit()
        
        # Получаем информацию о пользователе
        cursor.execute('SELECT user_id FROM purchases WHERE id = ?', (purchase_id,))
        result = cursor.fetchone()
        
        if result:
            user_id = result[0]
            try:
                await bot.send_message(
                    user_id,
                    f"<b>❌ ЗАКАЗ ОТМЕНЕН</b>\n\n"
                    f"<b>🛒 Заказ #{purchase_id} был отменен администратором.</b>\n\n"
                    f"<b>ℹ️ Возможные причины:</b>\n"
                    f"• Оплата не поступила\n"
                    f"• Ошибка при оформлении\n"
                    f"• Технические проблемы\n\n"
                    f"<b>📞 Свяжитесь с администратором для уточнения деталей.</b>",
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.error(f"Не удалось уведомить пользователя {user_id}: {e}")
        
        # Обновляем сообщение админу
        await callback_query.message.edit_text(
            text=f"<b>❌ ЗАКАЗ ОТМЕНЕН</b>\n\n"
                 f"<b>📋 Заказ #{purchase_id}</b>\n"
                 f"<b>👑 Отменил: @{callback_query.from_user.username or 'админ'}</b>\n"
                 f"<b>⏰ {datetime.now().strftime('%H:%M %d.%m.%Y')}</b>",
            reply_markup=None,
            parse_mode="HTML"
        )
        
        await callback_query.answer("❌ Заказ отменен")
        
    except Exception as e:
        logger.error(f"Ошибка в admin_cancel_card_payment: {e}")
        await callback_query.answer("❌ Произошла ошибка", show_alert=True)

# ============================================================================
# ✅ АДМИН ПОДТВЕРЖДАЕТ ВЫДАЧУ STARS (ОБЩИЙ МЕТОД)
# ============================================================================

@router.callback_query(F.data.startswith('admin_complete_'), F.from_user.id.in_(ADMIN_IDS))
async def admin_complete_purchase(callback_query: CallbackQuery):
    """Админ подтверждает выдачу Stars (общий метод для всех способов оплаты)"""
    try:
        purchase_id = int(callback_query.data.split('_')[2])
        admin_id = callback_query.from_user.id
        
        # Получаем информацию о покупке
        cursor.execute('''
            SELECT p.user_id, p.stars_count, p.amount_rub, u.username, u.full_name, p.payment_method 
            FROM purchases p
            JOIN users u ON p.user_id = u.user_id
            WHERE p.id = ? AND p.status = 'paid'
        ''', (purchase_id,))
        
        purchase = cursor.fetchone()
        
        if not purchase:
            await callback_query.answer("Покупка не найдена или уже обработана", show_alert=True)
            return
        
        user_id, stars, amount, username, full_name, payment_method = purchase
        
        # Обновляем статус
        cursor.execute(
            'UPDATE purchases SET status = ?, admin_id = ?, completed_at = CURRENT_TIMESTAMP WHERE id = ?',
            ('completed', admin_id, purchase_id)
        )
        conn.commit()
        
        # Уведомляем покупателя
        payment_methods_text = {
            'yookassa': 'через ЮKassa',
            'card_transfer': 'переводом на карту'
        }
        
        payment_text = payment_methods_text.get(payment_method, '')
        
        try:
            await bot.send_message(
                user_id,
                f"<b>🎉 ПОКУПКА ЗАВЕРШЕНА!</b>\n\n"
                f"<b>✅ Администратор выдал вам {stars} Telegram Stars.</b>\n"
                f"<b>🛒 Номер покупки: #{purchase_id}</b>\n"
                f"<b>⭐️ Количество: {stars} Stars</b>\n"
                f"<b>💰 Сумма: {format_price(amount)} руб.</b>\n"
                f"<b>💳 Оплата: {payment_text}</b>\n\n"
                f"<b>Спасибо за покупку! 🚀</b>",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Не удалось уведомить пользователя {user_id}: {e}")
        
        # Обновляем сообщение админу
        await callback_query.message.edit_text(
            text=f"<b>✅ ВЫДАЧА ПОДТВЕРЖДЕНА</b>\n\n"
                 f"<b>📋 Заказ #{purchase_id}</b>\n"
                 f"<b>👤 {full_name} (@{username})</b>\n"
                 f"<b>⭐️ {stars} Stars выданы</b>\n"
                 f"<b>💰 {format_price(amount)} руб.</b>\n"
                 f"<b>👑 Выдал: @{callback_query.from_user.username or 'админ'}</b>\n"
                 f"<b>⏰ {datetime.now().strftime('%H:%M %d.%m.%Y')}</b>",
            reply_markup=None,
            parse_mode="HTML"
        )
        
        await callback_query.answer("✅ Выдача подтверждена")
        
    except Exception as e:
        logger.error(f"Ошибка в admin_complete_purchase: {e}")
        await callback_query.answer("❌ Произошла ошибка", show_alert=True)

# ============================================================================
# 📋 ПОКАЗАТЬ МОИ ПОКУПКИ
# ============================================================================

@router.message(F.text == "📋 Мои заказы")
async def show_user_purchases(message: Message):
    try:
        user_id = message.from_user.id
        
        cursor.execute('''
            SELECT id, stars_count, amount_rub, status, created_at, completed_at, payment_method 
            FROM purchases 
            WHERE user_id = ? 
            ORDER BY created_at DESC 
            LIMIT 10
        ''', (user_id,))
        
        purchases = cursor.fetchall()
        
        if not purchases:
            await message.answer("<b>📭 У вас еще нет покупок.</b>", parse_mode="HTML")
            return
        
        response = "<b>📋 История ваших покупок:</b>\n\n"
        
        status_icons = {
            'waiting_payment': '⏳ Ожидает оплаты',
            'paid': '✅ Оплачено (ждет выдачи)',
            'completed': '🎉 Завершено',
            'cancelled': '❌ Отменено',
            'creating_payment': '⚡ Создание платежа'
        }
        
        payment_methods = {
            'yookassa': '💳 ЮKassa',
            'card_transfer': '🤝 Перевод на карту'
        }
        
        for purchase in purchases:
            pid, stars, amount, status, created, completed, payment_method = purchase
            
            status_text = status_icons.get(status, status)
            payment_text = payment_methods.get(payment_method, payment_method)
            
            # Безопасное преобразование даты
            if isinstance(created, str):
                try:
                    created_str = datetime.strptime(created, '%Y-%m-%d %H:%M:%S').strftime('%d.%m.%Y %H:%M')
                except:
                    created_str = created
            else:
                created_str = str(created)
            
            response += f"<b>🆔 #{pid}</b>\n"
            response += f"<b>⭐️ {stars} Stars</b>\n"
            response += f"<b>💰 {format_price(amount)} руб.</b>\n"
            response += f"<b>💳 {payment_text}</b>\n"
            response += f"<b>📊 {status_text}</b>\n"
            response += f"<b>📅 {created_str}</b>\n"
            
            if completed and status == 'completed':
                if isinstance(completed, str):
                    try:
                        completed_str = datetime.strptime(completed, '%Y-%m-%d %H:%M:%S').strftime('%d.%m.%Y %H:%M')
                    except:
                        completed_str = completed
                else:
                    completed_str = str(completed)
                response += f"<b>✅ Выдано: {completed_str}</b>\n"
            
            response += "─" * 25 + "\n"
        
        await message.answer(response, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Ошибка в show_user_purchases: {e}")
        await message.answer("❌ Произошла ошибка при загрузке покупок.")

# ============================================================================
# 👑 АДМИН-ПАНЕЛЬ
# ============================================================================

@router.message(F.text == "👑 Админ-панель", F.from_user.id.in_(ADMIN_IDS))
async def admin_panel(message: Message):
    try:
        keyboard = types.ReplyKeyboardMarkup(
            keyboard=[
                [types.KeyboardButton(text="📊 Статистика"), types.KeyboardButton(text="🔄 Ожидают выдачи")],
                [types.KeyboardButton(text="📈 Все заказы"), types.KeyboardButton(text="🔙 Главное меню")]
            ],
            resize_keyboard=True
        )
        
        await message.answer("<b>👑 Панель администратора</b>", reply_markup=keyboard, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Ошибка в admin_panel: {e}")
        await message.answer("❌ Произошла ошибка.")

@router.message(F.text == "📊 Статистика", F.from_user.id.in_(ADMIN_IDS))
async def admin_stats(message: Message):
    try:
        # Общая статистика
        cursor.execute("SELECT COUNT(*) FROM users")
        result = cursor.fetchone()
        total_users = result[0] if result else 0
        
        cursor.execute("SELECT COUNT(*) FROM purchases WHERE status = 'completed'")
        result = cursor.fetchone()
        completed_purchases = result[0] if result else 0
        
        cursor.execute("SELECT COUNT(*) FROM purchases WHERE status = 'paid'")
        result = cursor.fetchone()
        waiting_purchases = result[0] if result else 0
        
        cursor.execute("SELECT SUM(amount_rub) FROM purchases WHERE status = 'completed'")
        result = cursor.fetchone()
        total_revenue = result[0] if result and result[0] else 0
        
        cursor.execute("SELECT SUM(stars_count) FROM purchases WHERE status = 'completed'")
        result = cursor.fetchone()
        total_stars = result[0] if result and result[0] else 0
        
        # Статистика по методам оплаты
        cursor.execute("SELECT payment_method, COUNT(*), SUM(amount_rub) FROM purchases WHERE status = 'completed' GROUP BY payment_method")
        payment_stats = cursor.fetchall()
        
        stats_text = (
            f"<b>📊 СТАТИСТИКА МАГАЗИНА</b>\n\n"
            f"<b>👥 Пользователей:</b> {total_users}\n"
            f"<b>✅ Выполнено покупок:</b> {completed_purchases}\n"
            f"<b>🔄 Ожидают выдачи:</b> {waiting_purchases}\n"
            f"<b>💰 Общая выручка:</b> {format_price(total_revenue)} руб.\n"
            f"<b>⭐️ Всего Stars продано:</b> {total_stars}\n\n"
        )
        
        if payment_stats:
            stats_text += f"<b>💳 Статистика по способам оплаты:</b>\n"
            for method, count, amount in payment_stats:
                method_text = {
                    'yookassa': 'ЮKassa',
                    'card_transfer': 'Перевод на карту'
                }.get(method, method)
                stats_text += f"• {method_text}: {count} покупок, {format_price(amount or 0)} руб.\n"
        
        await message.answer(stats_text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Ошибка в admin_stats: {e}")
        await message.answer("❌ Произошла ошибка при загрузке статистики.")

# ============================================================================
# 👑 АДМИН-ПАНЕЛЬ - ОБРАБОТЧИКИ КНОПОК
# ============================================================================

@router.message(F.text == "🔄 Ожидают выдачи", F.from_user.id.in_(ADMIN_IDS))
async def show_pending_orders(message: Message):
    """Показать заказы, ожидающие выдачи Stars"""
    try:
        # Получаем заказы со статусом 'paid' (оплачено, но не выдано)
        cursor.execute('''
            SELECT p.id, p.user_id, u.username, u.full_name, 
                   p.stars_count, p.amount_rub, p.payment_method,
                   p.created_at
            FROM purchases p
            JOIN users u ON p.user_id = u.user_id
            WHERE p.status = 'paid'
            ORDER BY p.created_at DESC
        ''')
        
        pending_orders = cursor.fetchall()
        
        if not pending_orders:
            await message.answer("<b>✅ Нет заказов, ожидающих выдачи Stars.</b>", parse_mode="HTML")
            return
        
        response = "<b>🔄 ЗАКАЗЫ, ОЖИДАЮЩИЕ ВЫДАЧИ STARS</b>\n\n"
        
        payment_methods = {
            'yookassa': '💳 ЮKassa',
            'card_transfer': '🤝 Перевод на карту'
        }
        
        for order in pending_orders:
            order_id, user_id, username, full_name, stars, amount, payment_method, created = order
            
            # Форматируем дату
            if isinstance(created, str):
                try:
                    created_str = datetime.strptime(created, '%Y-%m-%d %H:%M:%S').strftime('%d.%m.%Y %H:%M')
                except:
                    created_str = created
            else:
                created_str = str(created)
            
            payment_text = payment_methods.get(payment_method, 'Неизвестно')
            username_display = f"@{username}" if username else "Нет username"
            
            response += (
                f"<b>🆔 Заказ #{order_id}</b>\n"
                f"<b>👤 Покупатель:</b> {full_name}\n"
                f"<b>🔗 Юзернейм:</b> {username_display}\n"
                f"<b>🆔 ID:</b> {user_id}\n"
                f"<b>⭐️ Количество:</b> {stars} Stars\n"
                f"<b>💰 Сумма:</b> {format_price(amount)} руб.\n"
                f"<b>💳 Способ оплаты:</b> {payment_text}\n"
                f"<b>📅 Дата заказа:</b> {created_str}\n"
                f"<b>🎯 Подтвердить выдачу:</b> /complete_{order_id}\n"
                f"{'─' * 30}\n\n"
            )
        
        response += f"<b>📊 Всего ожидает выдачи:</b> {len(pending_orders)} заказов"
        
        await message.answer(response, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Ошибка в show_pending_orders: {e}")
        await message.answer("❌ Произошла ошибка при загрузке заказов.")

@router.message(F.text == "📈 Все заказы", F.from_user.id.in_(ADMIN_IDS))
async def show_all_orders(message: Message):
    """Показать все заказы (последние 20)"""
    try:
        # Получаем последние 20 заказов
        cursor.execute('''
            SELECT p.id, p.user_id, u.username, u.full_name, 
                   p.stars_count, p.amount_rub, p.payment_method,
                   p.status, p.created_at, p.completed_at
            FROM purchases p
            JOIN users u ON p.user_id = u.user_id
            ORDER BY p.created_at DESC
            LIMIT 20
        ''')
        
        all_orders = cursor.fetchall()
        
        if not all_orders:
            await message.answer("<b>📭 В базе данных нет заказов.</b>", parse_mode="HTML")
            return
        
        response = "<b>📈 ПОСЛЕДНИЕ 20 ЗАКАЗОВ</b>\n\n"
        
        status_icons = {
            'waiting_payment': '⏳ Ожидает оплаты',
            'paid': '✅ Оплачено (ждет выдачи)',
            'completed': '🎉 Завершено',
            'cancelled': '❌ Отменено',
            'creating_payment': '⚡ Создание платежа'
        }
        
        payment_methods = {
            'yookassa': '💳',
            'card_transfer': '🤝'
        }
        
        payment_methods_full = {
            'yookassa': 'ЮKassa',
            'card_transfer': 'Перевод на карту'
        }
        
        for order in all_orders:
            order_id, user_id, username, full_name, stars, amount, payment_method, status, created, completed = order
            
            # Форматируем даты
            if isinstance(created, str):
                try:
                    created_str = datetime.strptime(created, '%Y-%m-%d %H:%M:%S').strftime('%d.%m %H:%M')
                except:
                    created_str = created
            else:
                created_str = str(created)
            
            status_text = status_icons.get(status, status)
            payment_icon = payment_methods.get(payment_method, '💳')
            payment_full = payment_methods_full.get(payment_method, 'Неизвестно')
            
            # Определяем эмодзи статуса
            if status == 'completed':
                status_emoji = "✅"
            elif status == 'paid':
                status_emoji = "⏳"
            elif status == 'cancelled':
                status_emoji = "❌"
            elif status == 'waiting_payment':
                status_emoji = "💳"
            else:
                status_emoji = "⚡"
            
            username_display = f"@{username}" if username else "нет username"
            
            response += (
                f"{status_emoji} <b>Заказ #{order_id}</b>\n"
                f"{payment_icon} <b>Способ:</b> {payment_full}\n"
                f"<b>👤:</b> {username_display}\n"
                f"<b>⭐️:</b> {stars} Stars\n"
                f"<b>💰:</b> {format_price(amount)} руб.\n"
                f"<b>📊:</b> {status_text}\n"
                f"<b>📅:</b> {created_str}\n"
            )
            
            # Если заказ завершен, показываем дату завершения
            if status == 'completed' and completed:
                if isinstance(completed, str):
                    try:
                        completed_str = datetime.strptime(completed, '%Y-%m-%d %H:%M:%S').strftime('%d.%m %H:%M')
                    except:
                        completed_str = completed
                else:
                    completed_str = str(completed)
                response += f"<b>✅ Выдано:</b> {completed_str}\n"
            
            response += f"{'─' * 20}\n"
        
        # Статистика по статусам
        cursor.execute('''
            SELECT status, COUNT(*) as count, SUM(amount_rub) as total 
            FROM purchases 
            GROUP BY status
        ''')
        
        status_stats = cursor.fetchall()
        
        if status_stats:
            response += "\n<b>📊 СТАТИСТИКА ПО СТАТУСАМ:</b>\n"
            total_amount = 0
            total_count = 0
            
            for status, count, amount in status_stats:
                status_name = {
                    'waiting_payment': 'Ожидают оплаты',
                    'paid': 'Оплачено (ждут выдачи)',
                    'completed': 'Завершено',
                    'cancelled': 'Отменено',
                    'creating_payment': 'Создание платежа'
                }.get(status, status)
                
                amount_display = format_price(amount or 0)
                response += f"• {status_name}: {count} зак. ({amount_display} руб.)\n"
                
                if status == 'completed':
                    total_amount += (amount or 0)
                total_count += count
            
            response += f"\n<b>📈 ИТОГО:</b> {total_count} заказов\n"
            response += f"<b>💰 Выручка:</b> {format_price(total_amount)} руб."
        
        await message.answer(response, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Ошибка в show_all_orders: {e}")
        await message.answer("❌ Произошла ошибка при загрузке всех заказов.")

# ============================================================================
# 🎯 КОМАНДА ДЛЯ ПОДТВЕРЖДЕНИЯ ВЫДАЧИ ЧЕРЕЗ СООБЩЕНИЕ
# ============================================================================

@router.message(F.text.regexp(r'^/complete_\d+$'), F.from_user.id.in_(ADMIN_IDS))
async def complete_order_via_command(message: Message):
    """Подтверждение выдачи Stars через текстовую команду /complete_{order_id}"""
    try:
        # Извлекаем ID заказа из команды
        command_text = message.text
        order_id = int(command_text.split('_')[1])
        
        # Получаем информацию о заказе
        cursor.execute('''
            SELECT p.user_id, p.stars_count, p.amount_rub, u.username, u.full_name, p.payment_method, p.status
            FROM purchases p
            JOIN users u ON p.user_id = u.user_id
            WHERE p.id = ?
        ''', (order_id,))
        
        order = cursor.fetchone()
        
        if not order:
            await message.answer(f"<b>❌ Заказ #{order_id} не найден.</b>", parse_mode="HTML")
            return
        
        user_id, stars, amount, username, full_name, payment_method, status = order
        
        if status == 'completed':
            await message.answer(f"<b>⚠️ Заказ #{order_id} уже завершен.</b>", parse_mode="HTML")
            return
        
        if status != 'paid':
            await message.answer(f"<b>❌ Заказ #{order_id} не готов к выдаче (статус: {status}).</b>", parse_mode="HTML")
            return
        
        # Обновляем статус заказа
        cursor.execute(
            'UPDATE purchases SET status = ?, admin_id = ?, completed_at = CURRENT_TIMESTAMP WHERE id = ?',
            ('completed', message.from_user.id, order_id)
        )
        conn.commit()
        
        # Уведомляем покупателя
        payment_methods_text = {
            'yookassa': 'через ЮKassa',
            'card_transfer': 'переводом на карту'
        }
        
        payment_text = payment_methods_text.get(payment_method, '')
        
        try:
            await bot.send_message(
                user_id,
                f"<b>🎉 ПОКУПКА ЗАВЕРШЕНА!</b>\n\n"
                f"<b>✅ Администратор выдал вам {stars} Telegram Stars.</b>\n"
                f"<b>🛒 Номер заказа: #{order_id}</b>\n"
                f"<b>⭐️ Количество: {stars} Stars</b>\n"
                f"<b>💰 Сумма: {format_price(amount)} руб.</b>\n"
                f"<b>💳 Оплата: {payment_text}</b>\n\n"
                f"<b>Спасибо за покупку! 🚀</b>",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Не удалось уведомить пользователя {user_id}: {e}")
        
        # Уведомляем админа об успешном завершении
        await message.answer(
            f"<b>✅ ВЫДАЧА ПОДТВЕРЖДЕНА</b>\n\n"
            f"<b>📋 Заказ #{order_id}</b>\n"
            f"<b>👤 {full_name} (@{username})</b>\n"
            f"<b>⭐️ {stars} Stars выданы</b>\n"
            f"<b>💰 {format_price(amount)} руб.</b>\n"
            f"<b>👑 Выдал: @{message.from_user.username or 'админ'}</b>\n"
            f"<b>⏰ {datetime.now().strftime('%H:%M %d.%m.%Y')}</b>",
            parse_mode="HTML"
        )
        
    except ValueError:
        await message.answer("<b>❌ Неверный формат команды. Используйте: /complete_123</b>", parse_mode="HTML")
    except Exception as e:
        logger.error(f"Ошибка в complete_order_via_command: {e}")
        await message.answer("<b>❌ Произошла ошибка при обработке команды.</b>", parse_mode="HTML")

@router.message(F.text == "🔙 Главное меню", F.from_user.id.in_(ADMIN_IDS))
async def back_to_main_from_admin(message: Message):
    """Возврат из админ-панели в главное меню"""
    try:
        # Главное меню с кнопкой админ-панели
        keyboard = types.ReplyKeyboardMarkup(
            keyboard=[
                [types.KeyboardButton(text="⭐️ Купить Telegram Stars")],
                [types.KeyboardButton(text="📋 Мои заказы")],
                [types.KeyboardButton(text="💳 Способы оплаты")],
                [types.KeyboardButton(text="👑 Админ-панель")]
            ],
            resize_keyboard=True
        )
        
        await message.answer(
            "<b>🏠 Вы вернулись в главное меню</b>\n\n"
            "Выберите действие:",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Ошибка в back_to_main_from_admin: {e}")
        await message.answer("❌ Произошла ошибка при возврате в меню.")

# ============================================================================
# 🚀 ЗАПУСК БОТА
# ============================================================================

async def main():
    print("🤖 Бот для продажи Telegram Stars запущен!")
    print(f"👑 Администраторы: {ADMIN_IDS}")
    print(f"💳 Доступные способы оплаты: ЮKassa, Перевод на карту")
    
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
    finally:
        # Закрываем соединения при завершении
        await bot.session.close()
        conn.close()

if __name__ == '__main__':
    asyncio.run(main())
