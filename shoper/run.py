import os
import asyncio
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from app.handlers.user import router
from app.database.models import init_models
from app.service.price_tracker import PriceTracker

async def shutdown():
    print("Shutdown...")

async def startup():
    print("Startup...")

async def main():
    
    await init_models()
    
    load_dotenv()
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    
    print("BOT_TOKEN:", BOT_TOKEN)
    
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    # Подключаем router
    dp.include_router(router)

    dp.startup.register(startup)
    dp.shutdown.register(shutdown)

    # Создаем и запускаем отслеживание цен
    price_tracker = PriceTracker(bot)
    
    # Запускаем отслеживание цен в фоновом режиме
    tracking_task = asyncio.create_task(price_tracker.start_tracking())
    
    try:
        await dp.start_polling(bot)
    finally:
        # Останавливаем отслеживание при завершении
        await price_tracker.stop_tracking()
        tracking_task.cancel()
        try:
            await tracking_task
        except asyncio.CancelledError:
            pass

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass

