import asyncpg
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool
from backend.core.config import get_settings
from backend.db.models import Base

settings = get_settings()

engine = create_async_engine(settings.database_url, echo=False, poolclass=NullPool)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def ensure_db_exists():
    db_url = settings.database_url
    if not db_url:
        return
    
    try:
        # Extract base url and db name
        base_url, db_name = db_url.rsplit('/', 1)
        # Handle query params if any
        if '?' in db_name:
            db_name = db_name.split('?')[0]
            
        postgres_url = f"{base_url}/postgres"
        postgres_url = postgres_url.replace("postgresql+asyncpg://", "postgresql://")
        
        conn = await asyncpg.connect(postgres_url)
        try:
            exists = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", db_name)
            if not exists:
                await conn.execute(f'CREATE DATABASE "{db_name}"')
                print(f"Database '{db_name}' created successfully.")
        finally:
            await conn.close()
    except Exception as e:
        print(f"Note: Database auto-creation check skipped: {e}")


async def init_db():
    await ensure_db_exists()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
