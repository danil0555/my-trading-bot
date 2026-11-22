import asyncio
import ccxt.async_support as ccxt
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Сюда мы потом вставим ваш токен, но пока оставим так
TOKEN = "9105978736:AAGW4pZ70Ie6L9VRzVVRNZDlOiIxoAMWzl0"

# Функция, которая отвечает на команду /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Я бот для арбитража. Начинаю сканировать спот и фьючерсы...")

# Простая функция для проверки цен (для теста)
async def check_spread():
    exchange = ccxt.binance()
    while True:
        try:
            # Получаем цены на споте и фьючерсе
            ticker_spot = await exchange.fetch_ticker('BTC/USDT')
            ticker_future = await exchange.fetch_ticker('BTC/USDT:USDT')
            
            spot_price = ticker_spot['last']
            future_price = ticker_future['last']
            spread = ((future_price - spot_price) / spot_price) * 100
            
            print(f"Спот: {spot_price}, Фьючерс: {future_price}, Спред: {spread:.3f}%")
        except Exception as e:
            print(f"Ошибка: {e}")
        await asyncio.sleep(10) # Проверяем каждые 10 секунд

# Запуск бота
def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    
    # Запускаем сканер в фоне
    loop = asyncio.get_event_loop()
    loop.create_task(check_spread())
    
    print("Бот запущен!")
    app.run_polling()

if __name__ == '__main__':
    main()
