import asyncio
import os
import ccxt.async_support as ccxt
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT']
SPREAD_THRESHOLD = 0.15
SCAN_INTERVAL = 30

SPOT_TAKER_FEE = 0.001
FUTURES_TAKER_FEE = 0.0005

# Глобальные экземпляры бирж (создаются один раз)
spot_exchange = None
futures_exchange = None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"👋 Привет! Я бот для арбитража спот-фьючерс.\n\n"
        f"📊 Сканирую монеты: {', '.join(SYMBOLS)}\n"
        f"🎯 Порог чистого спреда: {SPREAD_THRESHOLD}%\n\n"
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
    print(f"--- Проверка {len(SYMBOLS)} монет ---", flush=True)
    
    # Используем глобальные экземпляры, не создаём новые
    global spot_exchange, futures_exchange
    
    for symbol in SYMBOLS:
        futures_symbol = f"{symbol}:USDT"
        
        try:
            # Добавляем таймауты, чтобы бот не зависал
            spot_book = await asyncio.wait_for(spot_exchange.fetch_order_book(symbol, limit=5), timeout=10)
            futures_book = await asyncio.wait_for(futures_exchange.fetch_order_book(futures_symbol, limit=5), timeout=10)
            funding_info = await asyncio.wait_for(futures_exchange.fetch_funding_rate(futures_symbol), timeout=10)

            if not spot_book['asks'] or not futures_book['bids']:
                continue

            spot_ask = spot_book['asks'][0][0]
            futures_bid = futures_book['bids'][0][0]

            raw_spread_pct = ((futures_bid - spot_ask) / spot_ask) * 100
            total_fees_pct = (SPOT_TAKER_FEE + FUTURES_TAKER_FEE) * 100
            net_spread_pct = raw_spread_pct - total_fees_pct

            print(f"{symbol}: Спред {raw_spread_pct:.2f}%, Чистый: {net_spread_pct:.2f}%", flush=True)

            if net_spread_pct >= SPREAD_THRESHOLD:
                funding_rate_pct = (funding_info.get('fundingRate', 0) or 0) * 100
                message = (
                    f"🚀 **АРБИТРАЖНЫЙ СИГНАЛ: {symbol}**\n\n"
                    f"📈 Купить на СПОТЕ: `{spot_ask:.4f}`\n"
                    f"📉 Продать на ФЬЮЧЕРСЕ: `{futures_bid:.4f}`\n\n"
                    f"📊 Сырой спред: `{raw_spread_pct:.3f}%`\n"
                    f"💸 Комиссии: `-{total_fees_pct:.3f}%`\n"
                    f"✅ **Чистый спред:** `{net_spread_pct:.3f}%`\n"
                    f"💰 Фандинг: `{funding_rate_pct:.4f}%`"
                )
                await context.bot.send_message(chat_id=context.job.chat_id, text=message, parse_mode='Markdown')
        except asyncio.TimeoutError:
            print(f"Таймаут при запросе {symbol}", flush=True)
        except Exception as e:
            print(f"Ошибка при обработке {symbol}: {e}", flush=True)
    
    print("--- Проверка завершена ---", flush=True)

async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    current_jobs = context.job_queue.get_jobs_by_name(str(chat_id))
    for job in current_jobs:
        job.schedule_removal()
        
    context.job_queue.run_repeating(
        check_arbitrage_opportunity,
        interval=SCAN_INTERVAL,
        first=5,
        chat_id=chat_id,
        name=str(chat_id)
    )
    await update.message.reply_text(f"✅ Подписка оформлена! Сканирую каждые {SCAN_INTERVAL} секунд.")

async def post_init(application: Application):
    """Создаём экземпляры бирж один раз при старте"""
    global spot_exchange, futures_exchange
    spot_exchange = ccxt.binance({'enableRateLimit': True, 'timeout': 15000})
    futures_exchange = ccxt.binance({'options': {'defaultType': 'future'}, 'enableRateLimit': True, 'timeout': 15000})
    print("Экземпляры бирж созданы.", flush=True)

async def post_stop(application: Application):
    """Закрываем соединения при остановке"""
    global spot_exchange, futures_exchange
    if spot_exchange:
        await spot_exchange.close()
    if futures_exchange:
        await futures_exchange.close()
    print("Соединения с биржами закрыты.", flush=True)

def main():
    print("Инициализация бота...", flush=True)
    if not TOKEN:
        print("ОШИБКА: Токен не найден! Проверьте файл .env", flush=True)
        return

    app = Application.builder().token(TOKEN).post_init(post_init).post_stop(post_stop).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("subscribe", subscribe))
    app.add_handler(CommandHandler("status", status))
    
    print("Бот успешно запущен и работает!", flush=True)
    app.run_polling()

if __name__ == '__main__':
    main()
