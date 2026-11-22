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

SPOT_TAKER_FEE = 0.001
FUTURES_TAKER_FEE = 0.0005

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"Привет! Я бот для арбитража спот-фьючерс.\n"
        f"Сканирую {len(SYMBOLS)} монет.\n"
        f"Порог чистого спреда: {SPREAD_THRESHOLD}%"
    )

async def check_arbitrage_opportunity(context: ContextTypes.DEFAULT_TYPE):
    spot_exchange = ccxt.binance()
    futures_exchange = ccxt.binance({'options': {'defaultType': 'future'}})

    try:
        for symbol in SYMBOLS:
            futures_symbol = f"{symbol}:USDT"
            try:
                spot_book = await spot_exchange.fetch_order_book(symbol, limit=5)
                futures_book = await futures_exchange.fetch_order_book(futures_symbol, limit=5)
                funding_info = await futures_exchange.fetch_funding_rate(futures_symbol)

                if not spot_book['asks'] or not futures_book['bids']:
                    continue

                spot_ask = spot_book['asks'][0][0]
                futures_bid = futures_book['bids'][0][0]

                raw_spread_pct = ((futures_bid - spot_ask) / spot_ask) * 100
                total_fees_pct = (SPOT_TAKER_FEE + FUTURES_TAKER_FEE) * 100
                net_spread_pct = raw_spread_pct - total_fees_pct

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
        await spot_exchange.close()
        await futures_exchange.close()

async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    current_jobs = context.job_queue.get_jobs_by_name(str(chat_id))
    for job in current_jobs:
        job.schedule_removal()
        
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
