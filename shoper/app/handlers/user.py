import os
import re
from aiogram import Router, types, F, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from app.handlers import keyb as kb
import app.database.request as rq
from app.service.price_parser import get_wildberries_price
from app.service.price_tracker import PriceTracker


router = Router()


class Form1(StatesGroup):
    name = State()
    phone = State()


class ProductForm(StatesGroup):
    waiting_for_url = State()
    waiting_for_threshold = State()


@router.message(Command("start"))
async def start_handler(message: types.Message, state: FSMContext, bot: Bot):
    await state.clear()

    tg_id = message.from_user.id

    is_user = await rq.set_user(tg_id)
    if not is_user:
        await message.answer("Привет! Давайте зарегистрируемся. Введите ваше имя:")
        await state.set_state(Form1.name)
    else:
        await message.answer("/help - для помощи или Нажмите кнопку:", reply_markup=kb.order_bot)


@router.message(Form1.name)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Введите номер телефона:")
    await state.set_state(Form1.phone)


PHONE_PATTERN = re.compile(r"^\+?\d{10,15}$")  # Например: +380XXXXXXXXX или 380XXXXXXXXX

@router.message(Form1.phone)
async def process_phone(message: types.Message, state: FSMContext):
    phone = message.text.strip()
    
    if not PHONE_PATTERN.match(phone):
        await message.answer("❗ Номер введён неверно. Пожалуйста, введите в формате +380XXXXXXXX.")
        return
    
    await state.update_data(phone=phone)
    tg_id = message.from_user.id
    user_data = await state.get_data()
    name = user_data['name']
    phone_number = user_data['phone']
    
    await rq.update_user(tg_id, name, phone_number)
    await message.answer("✅ Вы успешно зарегистрированы!", reply_markup=kb.order_bot)
    await state.clear()


# Обработчики кнопок клавиатуры
@router.message(F.text == "📦 Добавить товар")
async def add_product_button(message: types.Message, state: FSMContext):
    await add_product_start(message, state)


@router.message(F.text == "📋 Мои товары")
async def list_products_button(message: types.Message):
    await list_products(message)


@router.message(F.text == "🔍 Проверить цены")
async def check_prices_button(message: types.Message):
    await message.answer(
        "🔍 Для проверки цены конкретного товара используйте команду:\n"
        "/check <номер товара>\n\n"
        "Сначала посмотрите список товаров командой /list"
    )


@router.message(F.text == "❌ Удалить товар")
async def delete_product_button(message: types.Message):
    await message.answer(
        "❌ Для удаления товара используйте команду:\n"
        "/delete <номер товара>\n\n"
        "Сначала посмотрите список товаров командой /list"
    )


@router.message(F.text == "ℹ️ Помощь")
async def help_button(message: types.Message):
    await help_command(message)


# Команды для работы с товарами
@router.message(Command("add"))
async def add_product_start(message: types.Message, state: FSMContext):
    """Начинает процесс добавления товара"""
    await state.clear()
    await message.answer(
        "📦 Добавление товара для отслеживания\n\n"
        "Отправьте ссылку на товар с Wildberries:"
    )
    await state.set_state(ProductForm.waiting_for_url)


@router.message(ProductForm.waiting_for_url)
async def process_product_url(message: types.Message, state: FSMContext):
    """Обрабатывает URL товара"""
    url = message.text.strip()
    
    # Проверяем, что это Wildberries URL
    if 'wildberries.ru' not in url and 'wb.ru' not in url:
        await message.answer("❌ Пожалуйста, отправьте ссылку на товар с Wildberries (wildberries.ru или wb.ru)")
        return
    
    await message.answer("🔍 Получаю информацию о товаре...")
    
    try:
        # Получаем информацию о товаре
        product_info = await get_wildberries_price(url)
        
        if not product_info:
            await message.answer("❌ Не удалось получить информацию о товаре. Проверьте ссылку.")
            await state.clear()
            return
        
        name, price = product_info
        
        # Сохраняем данные в состоянии
        await state.update_data(url=url, name=name, price=price)
        
        await message.answer(
            f"📦 Товар: {name}\n"
            f"💰 Текущая цена: {price:.2f} ₽\n\n"
            f"Введите порог для уведомлений (в рублях):\n"
            f"Например: 50 (уведомление при изменении цены на 50+ рублей)"
        )
        await state.set_state(ProductForm.waiting_for_threshold)
        
    except Exception as e:
        await message.answer(f"❌ Ошибка при получении информации о товаре: {e}")
        await state.clear()


@router.message(ProductForm.waiting_for_threshold)
async def process_threshold(message: types.Message, state: FSMContext):
    """Обрабатывает порог для уведомлений"""
    try:
        threshold = float(message.text.strip())
        if threshold <= 0:
            await message.answer("❌ Порог должен быть больше 0. Попробуйте снова:")
            return
    except ValueError:
        await message.answer("❌ Введите число. Попробуйте снова:")
        return
    
    user_data = await state.get_data()
    url = user_data['url']
    name = user_data['name']
    price = user_data['price']
    
    # Получаем пользователя
    user = await rq.get_user(message.from_user.id)
    if not user:
        await message.answer("❌ Пользователь не найден. Зарегистрируйтесь снова.")
        await state.clear()
        return
    
    try:
        # Добавляем товар в базу
        product = await rq.add_product(user.id, name, url, price, threshold)
        
        await message.answer(
            f"✅ Товар успешно добавлен!\n\n"
            f"📦 {name}\n"
            f"💰 Текущая цена: {price:.2f} ₽\n"
            f"🔔 Порог уведомлений: {threshold} ₽\n\n"
            f"Бот будет отслеживать изменения цены и уведомит вас при изменении на {threshold}+ рублей."
        )
        
    except Exception as e:
        await message.answer(f"❌ Ошибка при добавлении товара: {e}")
    
    await state.clear()


@router.message(Command("list"))
async def list_products(message: types.Message):
    """Показывает список отслеживаемых товаров"""
    user = await rq.get_user(message.from_user.id)
    if not user:
        await message.answer("❌ Пользователь не найден. Зарегистрируйтесь снова.")
        return
    
    products = await rq.get_user_products(user.id)
    
    if not products:
        await message.answer("📭 У вас нет отслеживаемых товаров.\n\nИспользуйте /add для добавления товара.")
        return
    
    message_text = "📦 Ваши отслеживаемые товары:\n\n"
    
    for i, product in enumerate(products, 1):
        message_text += f"{i}. {product.name}\n"
        message_text += f"   💰 Цена: {product.current_price:.2f} ₽\n"
        message_text += f"   🔔 Порог: {product.price_threshold} ₽\n"
        message_text += f"   📅 Добавлен: {product.created_at.strftime('%d.%m.%Y')}\n\n"
    
    message_text += "Используйте /check <номер> для проверки цены или /delete <номер> для удаления."
    
    await message.answer(message_text)


@router.message(Command("check"))
async def check_price_command(message: types.Message):
    """Проверяет цену конкретного товара"""
    try:
        # Извлекаем номер товара из команды
        args = message.text.split()
        if len(args) != 2:
            await message.answer("❌ Используйте: /check <номер товара>")
            return
        
        product_num = int(args[1])
        if product_num <= 0:
            await message.answer("❌ Номер товара должен быть положительным числом.")
            return
        
        user = await rq.get_user(message.from_user.id)
        if not user:
            await message.answer("❌ Пользователь не найден.")
            return
        
        products = await rq.get_user_products(user.id)
        
        if product_num > len(products):
            await message.answer(f"❌ Товар с номером {product_num} не найден.")
            return
        
        product = products[product_num - 1]
        
        await message.answer("🔍 Проверяю цену...")
        
        # Проверяем цену
        new_price = await get_wildberries_price(product.url)
        
        if new_price is None:
            await message.answer("❌ Не удалось получить текущую цену товара.")
            return
        
        name, current_price = new_price
        
        # Обновляем цену в базе
        await rq.update_product_price(product.id, current_price)
        
        price_change = current_price - product.current_price
        
        if abs(price_change) > 0.01:
            change_text = f"📈 Изменение: {price_change:+.2f} ₽"
            if price_change > 0:
                change_text += " (цена выросла)"
            else:
                change_text += " (цена упала)"
        else:
            change_text = "📊 Цена не изменилась"
        
        await message.answer(
            f"📦 {name}\n"
            f"💰 Текущая цена: {current_price:.2f} ₽\n"
            f"💰 Предыдущая цена: {product.current_price:.2f} ₽\n"
            f"{change_text}"
        )
        
    except ValueError:
        await message.answer("❌ Номер товара должен быть числом.")
    except Exception as e:
        await message.answer(f"❌ Ошибка при проверке цены: {e}")


@router.message(Command("delete"))
async def delete_product_command(message: types.Message):
    """Удаляет товар из отслеживания"""
    try:
        args = message.text.split()
        if len(args) != 2:
            await message.answer("❌ Используйте: /delete <номер товара>")
            return
        
        product_num = int(args[1])
        if product_num <= 0:
            await message.answer("❌ Номер товара должен быть положительным числом.")
            return
        
        user = await rq.get_user(message.from_user.id)
        if not user:
            await message.answer("❌ Пользователь не найден.")
            return
        
        products = await rq.get_user_products(user.id)
        
        if product_num > len(products):
            await message.answer(f"❌ Товар с номером {product_num} не найден.")
            return
        
        product = products[product_num - 1]
        
        # Удаляем товар
        success = await rq.delete_product(product.id, user.id)
        
        if success:
            await message.answer(f"✅ Товар '{product.name}' удален из отслеживания.")
        else:
            await message.answer("❌ Ошибка при удалении товара.")
        
    except ValueError:
        await message.answer("❌ Номер товара должен быть числом.")
    except Exception as e:
        await message.answer(f"❌ Ошибка при удалении товара: {e}")


@router.message(Command("help"))
async def help_command(message: types.Message):
    """Показывает справку по командам"""
    help_text = """
🤖 Бот для отслеживания цен на Wildberries

📋 Доступные команды:

/add - Добавить товар для отслеживания
/list - Показать список отслеживаемых товаров
/check <номер> - Проверить цену товара
/delete <номер> - Удалить товар из отслеживания
/help - Показать эту справку

💡 Как использовать:
1. Используйте /add и отправьте ссылку на товар с Wildberries
2. Укажите порог для уведомлений (например, 50 рублей)
3. Бот будет отслеживать изменения цены и уведомит вас при изменении на указанную сумму

🔔 Уведомления:
Бот автоматически проверяет цены каждые 30 минут и отправляет уведомления при значительных изменениях.
"""
    await message.answer(help_text)



