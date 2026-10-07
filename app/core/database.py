from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _ensure_engine() -> async_sessionmaker[AsyncSession] | None:
    global _engine, _session_factory
    settings = get_settings()
    if not settings.database_url:
        return None
    if _session_factory is None:
        _engine = create_async_engine(settings.database_url, pool_pre_ping=True)
        _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    return _session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    factory = _ensure_engine()
    if factory is None:
        raise RuntimeError("DATABASE_URL no configurada: revisar .env / variables de entorno.")
    async with factory() as session:
        yield session


async def async_check_db() -> str:
    """Estado de la conexion a base de datos para el healthcheck."""
    factory = _ensure_engine()
    if factory is None:
        return "not_configured"
    try:
        async with factory() as session:
            await session.execute(text("SELECT 1"))
        return "ok"
    except Exception:
        return "error"


def reset_engine() -> None:
    """Util para tests: olvida el engine cacheado."""
    global _engine, _session_factory
    _engine = None
    _session_factory = None


__all__: list[str] = ["get_db", "async_check_db", "reset_engine"]
