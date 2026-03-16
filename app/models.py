from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from app.database import Base
from sqlalchemy.orm import Mapped, mapped_column


class Object(Base):
    __tablename__ = "objects"

    hash: Mapped[str] = mapped_column(String, primary_key=True)
    size: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())


class Bucket(Base):
    __tablename__ = "buckets"

    name: Mapped[str] = mapped_column(String, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())


class Key(Base):
    __tablename__ = "keys"

    bucket: Mapped[str] = mapped_column(
        String, ForeignKey("buckets.name", ondelete="CASCADE"), primary_key=True
    )
    key: Mapped[str] = mapped_column(String, primary_key=True)
    hash: Mapped[str] = mapped_column(
        String, ForeignKey("objects.hash", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
