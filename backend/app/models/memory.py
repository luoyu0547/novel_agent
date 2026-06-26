import datetime

from sqlalchemy import ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class CharacterProfile(Base):
    """角色资料模型。behavior_rules 以 JSON 列表存储，记录角色的行为准则。"""
    __tablename__ = "character_profiles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    novel_id: Mapped[int] = mapped_column(ForeignKey("novels.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    story_role: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    identity: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    personality: Mapped[str] = mapped_column(Text, nullable=False, default="")
    motivation: Mapped[str] = mapped_column(Text, nullable=False, default="")
    speech_style: Mapped[str] = mapped_column(Text, nullable=False, default="")
    behavior_rules: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    current_state: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.now)
    updated_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.now, onupdate=datetime.datetime.now)

    novel = relationship("Novel", back_populates="characters")


class WorldSetting(Base):
    """世界观设定模型。category 可选值见 memory.py 中的 WorldSettingCategory 字面量。"""
    __tablename__ = "world_settings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    novel_id: Mapped[int] = mapped_column(ForeignKey("novels.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.now)
    updated_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.now, onupdate=datetime.datetime.now)

    novel = relationship("Novel", back_populates="world_settings")
