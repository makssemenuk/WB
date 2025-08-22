from app.database.models import async_session, User, Product
from sqlalchemy import select, update
from typing import List, Optional


async def set_user(tg_id):
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == tg_id))

        if not user:
            session.add(User(tg_id=tg_id))
            await session.commit()
            return False
        return True if user.name else False


async def get_user(tg_id):
    async with async_session() as session:
        return await session.scalar(select(User).where(User.tg_id == tg_id))


async def update_user(tg_id, name, phone_number):
    async with async_session() as session:
        await session.execute(update(User).where(User.tg_id == tg_id).values(name=name,
                                                                             phone_number=phone_number))
        await session.commit()


# Функции для работы с товарами
async def add_product(user_id: int, name: str, url: str, current_price: float, price_threshold: float = 50.0) -> Product:
    async with async_session() as session:
        product = Product(
            user_id=user_id,
            name=name,
            url=url,
            current_price=current_price,
            price_threshold=price_threshold
        )
        session.add(product)
        await session.commit()
        await session.refresh(product)
        return product


async def get_user_products(user_id: int) -> List[Product]:
    async with async_session() as session:
        result = await session.execute(
            select(Product).where(Product.user_id == user_id, Product.is_active == True)
        )
        return result.scalars().all()


async def get_product(product_id: int) -> Optional[Product]:
    async with async_session() as session:
        return await session.scalar(select(Product).where(Product.id == product_id))


async def update_product_price(product_id: int, new_price: float) -> Optional[Product]:
    async with async_session() as session:
        product = await session.scalar(select(Product).where(Product.id == product_id))
        if product:
            product.previous_price = product.current_price
            product.current_price = new_price
            await session.commit()
            await session.refresh(product)
        return product


async def delete_product(product_id: int, user_id: int) -> bool:
    async with async_session() as session:
        product = await session.scalar(
            select(Product).where(Product.id == product_id, Product.user_id == user_id)
        )
        if product:
            product.is_active = False
            await session.commit()
            return True
        return False


async def get_products_for_price_check() -> List[Product]:
    """Получает все активные товары для проверки цен"""
    async with async_session() as session:
        result = await session.execute(
            select(Product).where(Product.is_active == True)
        )
        return result.scalars().all()