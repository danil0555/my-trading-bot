import asyncio
import os
import ccxt.async_support as ccxt
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Загружаем переменные окружения (токен)
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

# --- НАСТРОЙКИ ---
SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT']
SPREAD_THRESHOLD = 0.15  # Минимальный чистый спред для сигнала (в %)
SCAN_INTERVAL = 30       # Как часто проверять цены (в секундах)

# Комиссии Binance (тейкер). 0.001 = 0.1%, 0.0005 = 0.05%
SPOT_TAKER_FEE = 0.001
FUTURES_TAKER_FEE = 0.0005
# -----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"👋 Привет! Я бот для арбитража спот-фьючерс.\n\n"
        f"📊 Сканирую монеты: {', '.join(SYMBOLS)}\n"
        f"🎯 Порог чистого спреда: {SPREAD_THRESHOLD}%\n"
        f"💸 Комиссии учтены: спот {SPOT_TAKER_FEE*100}% + фьюч {FUTURES_TAKER_FEE*100}%\n\n"
        f"Отправьте /subscribe, чтобы начать поиск сигналов."
    )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    jobs = context.job_queue.get_jobs_by_name(str(chat_id))
    if jobs:
        await update.message.reply_text("✅ Сканер активен и ищет связки. Ждите сигналов!")
    else:
        await update.message.reply_text("❌ Сканер выключен. Отправьте /subscribe для запуска.")

async def check_arbitrage_opportunity(context: ContextTypes.DEFAULT_TYPE):
    print(f"--- Начинаю проверку {len(SYMBOLS)} монет ---")
    
    # Создаем подключения к биржам
    spot_exchange = ccxt.binance()
    futures_exchange = ccxt.binance({'options': {'defaultType': 'future'}})

    try:
        for symbol in SYMBOLS:
            futures_symbol = f"{symbol}:USDT"
            
            try:
                # Получаем стаканы (order book)
                spot_book = await spot_exchange.fetch_order_book(symbol, limit=5)
                futures_book = await futures_exchange.fetch_order_book(futures_symbol, limit=5)
                
                # Получаем ставку фандинга
                funding_info = await futures_exchange.fetch_funding_rate(futures_symbol)

                if not spot_book['asks'] or not futures_book['bids']:
                    continue

                # Лучшая цена купить на споте и лучшая цена продать на фьючерсе
                spot_ask = spot_book['asks'][0][0]
                futures_bid = futures_book['bids'][0][0]

                # Считаем спред
                raw_spread_pct = ((futures_bid - spot_ask) / spot_ask) * 100
                
                # Считаем общие комиссии на вход/выход (в %)
                total_fees_pct = (SPOT_TAKER_FEE + FUTURES_TAKER_FEE) * 100
                
                # Чистый спред
                net_spread_pct = raw_spread_pct - total_fees_pct

                print(f"{symbol}: Спред {raw_spread_pct:.2f}%, Чистый: {net_spread_pct:.2f}%")

                # Если чистый спред больше порога, отправляем сигнал
                if net_spread_pct >= SPREAD_THRESHOLD:
                    funding_rate_pct = (funding_info.get('fundingRate', 0) or 0) * 100
                    
                    message = (
                        f"🚀 **АРБИТРАЖНЫЙ СИГНАЛ: {symbol}**\n\n"
                        f"📈 Купить на СПОТЕ по: `{spot_ask:.4f}`\n"
                        f"📉 Продать на ФЬЮЧЕРСЕ по: `{futures_bid:.4f}`\n\n"
                        f"📊 Сырой спред: `{raw_spread_pct:.3f}%`\n"
                        f"💸 Комиссии: `-{total_fees_pct:.3f}%`\n"
                        f"✅ **Чистый спред:** `{net_spread_pct:.3f}%`\n\n"
                        f"💰 Фандинг: `{funding_rate_pct:.4f}%`"
                    )
                    await context.bot.send_message(
                        chat_id=context.job.chat_id, 
                        text=message, 
                        parse_mode='Markdown'
                    )
            except Exception as e:
                print(f"Ошибка при обработке {symbol}: {e}")
    finally:
        # Обязательно закрываем соединения
        await spot_exchange.close()
        await futures_exchange.close()
        print("--- Проверка завершена ---")

async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    
    # Удаляем старую задачу, если она была
    current_jobs = context.job_queue.get_jobs_by_name(str(chat_id))
    for job in current_jobs:
        job.schedule_removal()
        
    # Запускаем новую задачу
    context.job_queue.run_repeating(
        check_arbitrage_opportunity,
        interval=SCAN_INTERVAL,
        first=5,
        chat_id=chat_id,
        name=str(chat_id)
    )
    await update.message.reply_text(f"✅ Подписка оформлена! Сканирую каждые {SCAN_INTERVAL} секунд.")

def main():
    print("Инициализация бота...")
    # Убеждаемся, что токен загружен
    if not TOKEN:
        print("ОШИБКА: Токен не найден! Проверьте файл .env")
        return

    app = Application.builder().token(TOKEN).build()
    
    # Добавляем команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("subscribe", subscribe))
    app.add_handler(CommandHandler("status", status))
    
    print("Бот успешно запущен и работает!")
    app.run_polling()

if __name__ == '__main__':
    main()
