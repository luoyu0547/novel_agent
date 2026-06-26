from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, JSON, func

from app.core.database import Base


class PlotFact(Base):
    __tablename__ = "plot_facts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    novel_id = Column(Integer, ForeignKey("novels.id"), nullable=False, index=True)
    chapter_id = Column(Integer, ForeignKey("chapters.id"), nullable=False)
    fact_type = Column(String(50), nullable=False)  # event | relationship | location | item | knowledge
    content = Column(Text, nullable=False)
    related_characters = Column(JSON, nullable=False, default=list)
    importance = Column(String(20), nullable=False, default="minor")  # major | minor
    created_at = Column(DateTime, nullable=False, default=func.now())
