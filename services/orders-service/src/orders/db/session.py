from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from orders.config import settings

engine: AsyncEngine = create_async_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)
