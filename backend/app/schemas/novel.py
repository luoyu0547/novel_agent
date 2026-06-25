import datetime
from typing import List, Optional

from pydantic import BaseModel


class NovelCreate(BaseModel):
    title: str
    description: Optional[str] = None


class NovelUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None


class ChapterCreate(BaseModel):
    title: str
    content: str = ""


class ChapterUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None


class ChapterOut(BaseModel):
    id: int
    novel_id: int
    title: str
    content: str
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = {"from_attributes": True}


class NovelOut(BaseModel):
    id: int
    title: str
    description: Optional[str]
    created_at: datetime.datetime
    updated_at: datetime.datetime
    chapters: Optional[List[ChapterOut]] = None

    model_config = {"from_attributes": True}


class NovelListItem(BaseModel):
    id: int
    title: str
    description: Optional[str]
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = {"from_attributes": True}
