from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, JSON, func

from app.core.database import Base


class PendingMemory(Base):
    __tablename__ = "pending_memories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    novel_id = Column(Integer, ForeignKey("novels.id"), nullable=False, index=True)
    chapter_id = Column(Integer, ForeignKey("chapters.id"), nullable=False)
    memory_type = Column(String(50), nullable=False)  # character_change | plot_fact | world_setting | foreshadowing
    content = Column(JSON, nullable=False)
    status = Column(String(20), nullable=False, default="pending")  # pending | confirmed | rejected
    created_at = Column(DateTime, nullable=False, default=func.now())
