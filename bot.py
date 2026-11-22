import asyncio
import ccxt.async_support as ccxt
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Вставьте сюда ваш токен от BotFather
TOKEN = "9105978736:AAGW4pZ70Ie6L9VRzVVRNZDlOiIxoAMWzl0"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Я бот для арбитража. Начинаю сканировать спот и фьючерсы...")

async def check_spread(context: ContextTypes.DEFAULT_TYPE):
    """Фоновая задача для проверки спреда"""
    exchange = ccxt.binance()
    try:
        while True:
            try:
                ticker_spot = await exchange.fetch_ticker('BTC/USDT')
                ticker_future = await exchange.fetch_ticker('BTC/USDT:USDT')
                
                spot_price = ticker_spot['last']
                future_price = ticker_future['last']
                spread = ((future_price - spot_price) / spot_price) * 100
                
                print(f"Спот: {spot_price}, Фьючерс: {future_price}, Спред: {spread:.3f}%")
            except Exception as e:
                print(f"Ошибка при получении данных: {e}")
            await asyncio.sleep(10) # Проверяем каждые 10 секунд
    finally:
        await exchange.close()

async def post_init(application: Application):
    """Запускаем фоновую задачу после инициализации бота"""
    application.create_task(check_spread(application))

def main():
    print("Инициализация бота...")
    app = Application.builder().token(TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start))
    
    print("Бот запущен и начинает работу!")
    # run_polling сам создаст и запустит event loop
    app.run_polling()

if __name__ == '__main__':
    main()
