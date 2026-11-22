import asyncio
import os
import ccxt.async_support as ccxt
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

# --- Настройки сканера ---
SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT'] # Список монет для сканирования
SPREAD_THRESHOLD = 0.15  # Минимальный чистый спред в % (должен покрывать комиссии)
# --- Конец настроек ---

# Комиссии Binance (в долях, т.е. 0.001 = 0.1%)
SPOT_TAKER_FEE = 0.001     # 0.1%
FUTURES_TAKER_FEE = 0.0005 # 0.05%

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"Привет! Я бот для арбитража спот-фьючерс.\n"
        f"Сканирую {len(SYMBOLS)} монет.\n"
        f"Порог чистого спреда: {SPREAD_THRESHOLD}%\n"
        f"Учитываю комиссии: спот {SPOT_TAKER_FEE*100}%, фьючерсы {FUTURES_TAKER_FEE*100}%"
    )

async def check_arbitrage_opportunity(context: ContextTypes.DEFAULT_TYPE):
    """Основная функция сканирования, вызывается планировщиком."""
    # Создаем экземпляры бирж для спота и фьючерсов
    spot_exchange = ccxt.binance()
    futures_exchange = ccxt.binance({'options': {'defaultType': 'future'}})

    try:
        for symbol in SYMBOLS:
            # Для фьючерсов используем специальный формат символа
            futures_symbol = f"{symbol}:USDT"
            
            try:
                # 1. Получаем стаканы (order book) с обоих рынков
                spot_book = await spot_exchange.fetch_order_book(symbol, limit=5)
                futures_book = await futures_exchange.fetch_order_book(futures_symbol, limit=5)

                # 2. Получаем ставку финансирования
                funding_info = await futures_exchange.fetch_funding_rate(futures_symbol)

                # 3. Проверяем, что стаканы не пустые
                if not spot_book['asks'] or not futures_book['bids']:
                    continue

                # 4. Берем лучшие цены
                spot_ask = spot_book['asks'][0][0]     # Цена, по которой мы КУПИМ на споте
                futures_bid = futures_book['bids'][0][0] # Цена, по которой мы ПРОДАДИМ на фьючерсе

                # 5. Считаем "сырой" спред
                raw_spread_pct = ((futures_bid - spot_ask) / spot_ask) * 100

                # 6. Считаем общие комиссии на вход (покупка спот + продажа фьючерс)
                total_fees_pct = (SPOT_TAKER_FEE + FUTURES_TAKER_FEE) * 100

                # 7. Считаем ЧИСТЫЙ спред
                net_spread_pct = raw_spread_pct - total_fees_pct

                # 8. Если чистый спред превышает порог, отправляем сигнал
                if net_spread_pct >= SPREAD_THRESHOLD:
                    funding_rate_pct = funding_info['fundingRate'] * 100 if funding_info['fundingRate'] else 0
                    message = (
                        f"🚀 **АРБИТРАЖНЫЙ СИГНАЛ: {symbol}**\n\n"
                        f"📈 Купить на СПОТЕ по: `{spot_ask:.4f}`\n"
                        f"📉 Продать на ФЬЮЧЕРСЕ по: `{futures_bid:.4f}`\n\n"
                        f"📊 **Сырой спред:** `{raw_spread_pct:.3f}%`\n"
                        f"💸 **Комиссии:** `{total_fees_pct:.3f}%`\n"
                        f"✅ **Чистый спред:** `{net_spread_pct:.3f}%`\n\n"
                        f"💰 **Ставка фандинга:** `{funding_rate_pct:.4f}%`"
                    )
                    await context.bot.send_message(chat_id=context.job.chat_id, text=message, parse_mode='Markdown')

            except Exception as e:
                print(f"Ошибка при обработке {symbol}: {e}")

    finally:
        # Обязательно закрываем соединения
        await spot_exchange.close()
        await futures_exchange.close()

async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    # Удаляем старую задачу, если она была, чтобы избежать дублирования
    current_jobs = context.job_queue.get_jobs_by_name(str(chat_id))
    for job in current_jobs:
        job.schedule_removal()
        
    # Запускаем новую задачу каждые 30 секунд
    context.job_queue.run_repeating(
        check_arbitrage_opportunity,
        interval=30,
        first=5,
        chat_id=chat_id,
        name=str(chat_id)
    )
    await update.message.reply_text("✅ Вы подписались на сигналы! Бот будет присылать уведомления при появлении возможностей.")

def main():
    print("Инициализация бота...")
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("subscribe", subscribe))
    
    print("Бот запущен и начинает работу!")
    app.run_polling()

if __name__ == '__main__':
    main()
