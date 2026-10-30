from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class RawDataLog(Base):
    """Registro crudo de ingesta (esquema `raw_data_logs` de SPEC §6).

    Espejo del JSONL que escribe `app/services/storage/raw_store.py`, con el
    `error` adicional que el archivo también persiste.
    """

    __tablename__ = "raw_data_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[str] = mapped_column(String(64), index=True)
    raw_payload: Mapped[Any] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(16), default="ok")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
