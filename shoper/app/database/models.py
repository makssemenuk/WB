import os
import datetime
from sqlalchemy import Column, DateTime
from sqlalchemy import BigInteger, String, ForeignKey, Boolean, Float, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncAttrs

from dotenv import load_dotenv

load_dotenv()

engine = create_async_engine(url="sqlite+aiosqlite:///db.sqlite3")

async_session = async_sessionmaker(engine)


class Base(AsyncAttrs, DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    tg_id = mapped_column(BigInteger)
    name: Mapped[str] = mapped_column(String(25), nullable=True)
    phone_number: Mapped[str] = mapped_column(String(25), nullable=True)


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(255))
    url: Mapped[str] = mapped_column(Text)
    current_price: Mapped[float] = mapped_column(Float)
    previous_price: Mapped[float] = mapped_column(Float, nullable=True)
    price_threshold: Mapped[float] = mapped_column(Float, default=50.0)  # Порог для уведомлений
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.now)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now)


async def init_models():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)