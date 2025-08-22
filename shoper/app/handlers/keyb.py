from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup, 
    KeyboardButton, 
    ReplyKeyboardMarkup
    )


# Основная клавиатура
order_bot = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📦 Добавить товар"), KeyboardButton(text="📋 Мои товары")],
        [KeyboardButton(text="🔍 Проверить цены"), KeyboardButton(text="❌ Удалить товар")],
        [KeyboardButton(text="ℹ️ Помощь")]
    ],
    resize_keyboard=True,
    input_field_placeholder="Выберите действие"
)


# Инлайн клавиатура для подтверждения
confirm_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да", callback_data="confirm_yes"),
            InlineKeyboardButton(text="❌ Нет", callback_data="confirm_no")
        ]
    ]
)

