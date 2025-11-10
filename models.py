from typing import Optional
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


# Base class for all Sqlalchemy models
class Base(DeclarativeBase):
    pass


class URL(Base):
    __tablename__ = "urls"

    id: Mapped[int] = mapped_column(primary_key=True)
    original_url: Mapped[str] = mapped_column(index=True)
    short_code: Mapped[Optional[str]] = mapped_column(unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(default=True, index=True)
