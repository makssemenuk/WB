import asyncio
from typing import List
from aiogram import Bot
from app.database.request import get_products_for_price_check, update_product_price, get_user
from app.service.price_parser import check_wildberries_price


class PriceTracker:
    def __init__(self, bot: Bot):
        self.bot = bot
        self.is_running = False

    async def start_tracking(self):
        """Запускает отслеживание цен"""
        self.is_running = True
        while self.is_running:
            try:
                await self.check_all_prices()
                # Проверяем цены каждые 30 минут
                await asyncio.sleep(1800)  # 30 минут
            except Exception as e:
                print(f"Ошибка в отслеживании цен: {e}")
                await asyncio.sleep(300)  # 5 минут при ошибке

    async def stop_tracking(self):
        """Останавливает отслеживание цен"""
        self.is_running = False

    async def check_all_prices(self):
        """Проверяет цены всех товаров"""
        products = await get_products_for_price_check()
        
        for product in products:
            try:
                await self.check_single_product(product)
                # Небольшая задержка между запросами
                await asyncio.sleep(2)
            except Exception as e:
                print(f"Ошибка при проверке товара {product.id}: {e}")

    async def check_single_product(self, product):
        """Проверяет цену одного товара"""
        try:
            # Проверяем, что это Wildberries URL
            if 'wildberries.ru' not in product.url and 'wb.ru' not in product.url:
                return

            new_price = await check_wildberries_price(product.url)
            
            if new_price is None:
                return

            # Если цена изменилась
            if abs(new_price - product.current_price) > 0.01:  # Учитываем небольшие различия
                old_price = product.current_price
                
                # Обновляем цену в базе
                updated_product = await update_product_price(product.id, new_price)
                
                if updated_product:
                    # Проверяем, нужно ли отправить уведомление
                    price_difference = abs(new_price - old_price)
                    
                    if price_difference >= product.price_threshold:
                        await self.send_price_notification(updated_product, old_price, new_price)

        except Exception as e:
            print(f"Ошибка при проверке товара {product.id}: {e}")

    async def send_price_notification(self, product, old_price, new_price):
        """Отправляет уведомление об изменении цены"""
        try:
            user = await get_user(product.user_id)
            if not user:
                return

            price_difference = new_price - old_price
            change_type = "выросла" if price_difference > 0 else "упала"
            
            message = f"🔔 Изменение цены!\n\n"
            message += f"📦 Товар: {product.name}\n"
            message += f"💰 Старая цена: {old_price:.2f} ₽\n"
            message += f"💰 Новая цена: {new_price:.2f} ₽\n"
            message += f"📈 Изменение: {price_difference:+.2f} ₽ ({change_type})\n\n"
            message += f"🔗 Ссылка: {product.url}"

            await self.bot.send_message(user.tg_id, message)
            
        except Exception as e:
            print(f"Ошибка при отправке уведомления: {e}")

    async def check_price_now(self, product_id: int) -> bool:
        """Проверяет цену конкретного товара прямо сейчас"""
        try:
            product = await get_products_for_price_check()
            product = next((p for p in product if p.id == product_id), None)
            
            if not product:
                return False
                
            await self.check_single_product(product)
            return True
            
        except Exception as e:
            print(f"Ошибка при немедленной проверке цены: {e}")
            return False
