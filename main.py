from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    CallbackQueryHandler,
    PreCheckoutQueryHandler
)
import requests
import json
import sqlite3
from datetime import datetime

DEEPINFRA_API_KEY = ""  
DEEPINFRA_API_URL = "https://api.deepinfra.com/v1/openai/chat/completions"
MODEL_NAME = "meta-llama/Meta-Llama-3-70B-Instruct"

TOKEN = ""
PAYMENT_PROVIDER_TOKEN = ""

DAILY_LIMIT = 50  
POINTS_PER_REQUEST = 1  

ADMINS = []  

POINTS_PRICES = {
    100: 10000,  
    250: 20000,
    500: 35000,
    1000: 60000
}

def init_db():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        points_used INTEGER DEFAULT 0,
        last_reset_date TEXT,
        total_points INTEGER DEFAULT 0,
        is_admin BOOLEAN DEFAULT FALSE
    )
    ''')
    
    cursor.execute('''
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    amount INTEGER,
    points INTEGER,
    date TEXT,
    status TEXT,
    FOREIGN KEY(user_id) REFERENCES users(user_id)
)
''')
    
    conn.commit()
    conn.close()


def check_reset_points(user_id):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    
    today = datetime.now().strftime('%Y-%m-%d')
    
    cursor.execute('SELECT last_reset_date, points_used, total_points FROM users WHERE user_id = ?', (user_id,))
    user_data = cursor.fetchone()
    
    if user_data:
        last_reset_date, points_used, total_points = user_data
        if last_reset_date != today:
            cursor.execute('''
            UPDATE users 
            SET points_used = 0, last_reset_date = ?
            WHERE user_id = ?
            ''', (today, user_id))
            conn.commit()
            points_used = 0
    else:
        points_used = 0
        total_points = 0
    
    conn.close()
    return points_used, total_points

def add_user(user):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    
    today = datetime.now().strftime('%Y-%m-%d')
    is_admin = 1 if user.id in ADMINS else 0
    
    cursor.execute('''
    INSERT OR IGNORE INTO users (user_id, username, first_name, last_name, last_reset_date, is_admin)
    VALUES (?, ?, ?, ?, ?, ?)
    ''', (user.id, user.username, user.first_name, user.last_name, today, is_admin))
    
    conn.commit()
    conn.close()

def update_points(user_id, points):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    
    cursor.execute('''
    UPDATE users 
    SET points_used = points_used + ?
    WHERE user_id = ?
    ''', (points, user_id))
    
    conn.commit()
    conn.close()

def add_points_to_user(user_id, points):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    
    cursor.execute('''
    UPDATE users 
    SET total_points = total_points + ?
    WHERE user_id = ?
    ''', (points, user_id))
    
    conn.commit()
    conn.close()

def get_users_list():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT user_id, username, first_name, last_name, total_points FROM users')
    users = cursor.fetchall()
    
    conn.close()
    return users

def is_admin(user_id):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT is_admin FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    
    conn.close()
    return result[0] if result else False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    add_user(user)
    
    keyboard = [
        [InlineKeyboardButton("💰 Купить очки", callback_data='buy_points')],
        [InlineKeyboardButton("📊 Мой баланс", callback_data='my_balance')]
    ]
    
    if user.id in ADMINS:
        keyboard.append([InlineKeyboardButton("👑 Админ-панель", callback_data='admin_panel')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.message:
        await update.message.reply_text(
            f"Привет, {user.first_name}!\n"
            "Я бот с ИИ. Ты можешь общаться со мной, используя свои очки.\n"
            "Очки можно купить или получать ежедневный бонус.",
            reply_markup=reply_markup
        )
    elif update.callback_query:
        await update.callback_query.edit_message_text(
            f"Привет, {user.first_name}!\n"
            "Я бот с ИИ. Ты можешь общаться со мной, используя свои очки.\n"
            "Очки можно купить или получать ежедневный бонус.",
            reply_markup=reply_markup
        )
    else:
        await context.bot.send_message(
            chat_id=user.id,
            text=f"Привет, {user.first_name}!\n"
                 "Я бот с ИИ. Ты можешь общаться со мной, используя свои очки.\n"
                 "Очки можно купить или получать ежедневный бонус.",
            reply_markup=reply_markup
        )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id in ADMINS:
        await update.message.reply_text(
            "Доступные команды:\n"
            "/start - Начать общение\n"
            "/help - Помощь\n"
            "/points - Проверить оставшиеся очки\n"
            "/admin - Панель администратора"
        )
    else:
        await update.message.reply_text(
            "Доступные команды:\n"
            "/start - Начать общение\n"
            "/help - Помощь\n"
            "/points - Проверить оставшиеся очки"
        )

async def points_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    points_used, total_points = check_reset_points(user.id)
    remaining = DAILY_LIMIT - points_used
    
    await update.message.reply_text(
        f"Дневной лимит: {remaining}/{DAILY_LIMIT}\n"
        f"Общий баланс: {total_points} очков\n"
        f"Лимит сбрасывается в полночь."
    )

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        if update.message:
            await update.message.reply_text("У вас нет прав администратора.")
        elif update.callback_query:
            await update.callback_query.answer("У вас нет прав администратора.", show_alert=True)
        return
    
    keyboard = [
        [InlineKeyboardButton("Список пользователей", callback_data='users_list')],
        [InlineKeyboardButton("Пополнить очки", callback_data='add_points')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = "Админ-панель:"
    
    if update.message:
        await update.message.reply_text(text, reply_markup=reply_markup)
    elif update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
    else:
        await context.bot.send_message(
            chat_id=user.id,
            text=text,
            reply_markup=reply_markup
        )


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == 'buy_points':
        await shop_menu(update, context)
    elif query.data.startswith('buy_'):
        await initiate_payment(update, context)
    elif query.data == 'my_balance':
        points_used, total_points = check_reset_points(query.from_user.id)
        remaining = DAILY_LIMIT - points_used
        await query.edit_message_text(
            f"📊 Ваш баланс:\n"
            f"Дневные очки: {remaining}/{DAILY_LIMIT}\n"
            f"Общие очки: {total_points}\n\n"
            "Вы можете купить больше очков в магазине.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💰 Купить очки", callback_data='buy_points')],
                [InlineKeyboardButton("🔙 Назад", callback_data='back_to_main')]
            ])
        )
    elif query.data == 'back_to_main':
        await start(update, context)  
    elif query.data == 'admin_panel':
        await admin_panel(update, context)
    if is_admin(query.from_user.id):
        if query.data == 'users_list':
            users = get_users_list()
            message = "Список пользователей:\n\n"
            for user in users:
                user_id, username, first_name, last_name, total_points = user
                message += (
                    f"ID: {user_id}\n"
                    f"Имя: {first_name} {last_name}\n"
                    f"Username: @{username if username else 'нет'}\n"
                    f"Баланс: {total_points} очков\n\n"
                )
            await query.edit_message_text(text=message)
        
        elif query.data == 'add_points':
            context.user_data['admin_action'] = 'add_points'
            await query.edit_message_text(
                "Введите ID пользователя и количество очков через пробел:\n"
                "Например: 123456789 100"
            )

async def handle_admin_actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("У вас нет прав администратора.")
        return
    
    if 'admin_action' in context.user_data and context.user_data['admin_action'] == 'add_points':
        try:
            user_id, points = map(int, update.message.text.split())
            add_points_to_user(user_id, points)
            await update.message.reply_text(
                f"Пользователю {user_id} успешно добавлено {points} очков."
            )
            del context.user_data['admin_action']
        except ValueError:
            await update.message.reply_text(
                "Неверный формат. Введите ID пользователя и количество очков через пробел:\n"
                "Например: 123456789 100"
            )

async def shop_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton(f"100 очков - {POINTS_PRICES[100]/100} RUB", callback_data='buy_100')],
        [InlineKeyboardButton(f"250 очков - {POINTS_PRICES[250]/100} RUB", callback_data='buy_250')],
        [InlineKeyboardButton(f"500 очков - {POINTS_PRICES[500]/100} RUB", callback_data='buy_500')],
        [InlineKeyboardButton(f"1000 очков - {POINTS_PRICES[1000]/100} RUB", callback_data='buy_1000')],
        [InlineKeyboardButton("🔙 Назад", callback_data='back_to_main')]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "🎁 Магазин очков:\n"
        "Выберите количество очков для покупки:",
        reply_markup=reply_markup
    )

async def initiate_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    points = int(query.data.split('_')[1])
    price = POINTS_PRICES[points]
    

    context.user_data['current_transaction'] = {
        'points': points,
        'price': price
    }
    
    title = f"Покупка {points} очков"
    description = f"Пополнение баланса на {points} очков"
    payload = f"{user.id}_{points}_{datetime.now().timestamp()}"
    currency = "RUB"
    
    prices = [LabeledPrice(title, price)]
    
    await context.bot.send_invoice(
        chat_id=user.id,
        title=title,
        description=description,
        payload=payload,
        provider_token=PAYMENT_PROVIDER_TOKEN,
        currency=currency,
        prices=prices,
        start_parameter="buy-points"
    )

async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.pre_checkout_query
    await query.answer(ok=True)

async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    payment = update.message.successful_payment
    transaction = context.user_data.get('current_transaction', {})
    
    points = transaction.get('points', 0)
    price = transaction.get('price', 0)
    
    if points > 0:
        add_points_to_user(user.id, points)
        
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute('''
        INSERT INTO transactions (user_id, amount, points, date, status)
        VALUES (?, ?, ?, ?, ?)
        ''', (user.id, price, points, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'completed'))
        conn.commit()
        conn.close()
        
        await update.message.reply_text(
            f"✅ Оплата прошла успешно!\n"
            f"Ваш баланс пополнен на {points} очков.\n"
            f"Текущий баланс: {get_user_info(user.id)[1] + points} очков."
        )
    else:
        await update.message.reply_text("Произошла ошибка при обработке платежа.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.effective_user
        if 'admin_action' in context.user_data:
            await handle_admin_actions(update, context)
            return
            
        user_message = update.message.text
        
        points_used, total_points = check_reset_points(user.id)
        remaining_points = DAILY_LIMIT - points_used
        
        if remaining_points < POINTS_PER_REQUEST and total_points < POINTS_PER_REQUEST:
            await update.message.reply_text(
                f"Извини, ты израсходовал все свои очки.\n"
                "Попробуй завтра снова или используй /points чтобы проверить баланс."
            )
            return
        
        headers = {
            "Authorization": f"Bearer {DEEPINFRA_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": MODEL_NAME,
            "messages": [{"role": "user", "content": user_message}],
            "max_tokens": 1000
        }
        
        response = requests.post(DEEPINFRA_API_URL, headers=headers, data=json.dumps(payload))
        response_data = response.json()
        
        if response.status_code == 200:
            ai_response = response_data['choices'][0]['message']['content']
            
            if remaining_points >= POINTS_PER_REQUEST:
                update_points(user.id, POINTS_PER_REQUEST)
                remaining = DAILY_LIMIT - (points_used + POINTS_PER_REQUEST)
                points_type = "дневных"
            else:
                add_points_to_user(user.id, -POINTS_PER_REQUEST)
                remaining = total_points - POINTS_PER_REQUEST
                points_type = "общих"
            
            await update.message.reply_text(
                f"{ai_response}\n\n"
                f"Использовано {POINTS_PER_REQUEST} {points_type} очков.\n"
                f"Осталось: {remaining}"
            )
        else:
            await update.message.reply_text(f"Ошибка API: {response_data.get('message', 'Неизвестная ошибка')}")
        
    except Exception as e:
        await update.message.reply_text(f"Произошла ошибка: {str(e)}")

if __name__ == "__main__":
    init_db()
    
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("points", points_command))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Бот запущен...")
    app.run_polling()