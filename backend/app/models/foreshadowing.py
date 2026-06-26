from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, JSON, func

from app.core.database import Base


class Foreshadowing(Base):
    __tablename__ = "foreshadowings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    novel_id = Column(Integer, ForeignKey("novels.id"), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    planted_chapter_id = Column(Integer, ForeignKey("chapters.id"), nullable=False)
    description = Column(Text, nullable=False)
    hidden_truth = Column(Text, nullable=False, default="")
    status = Column(String(20), nullable=False, default="planted")  # planted | developing | resolved
    expected_reveal_chapter_id = Column(Integer, ForeignKey("chapters.id"), nullable=True)
    related_characters = Column(JSON, nullable=False, default=list)
    risk_warning = Column(Text, nullable=False, default="")
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
