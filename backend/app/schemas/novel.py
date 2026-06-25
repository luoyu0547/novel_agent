import datetime
from typing import List, Optional

from pydantic import BaseModel, field_validator


class NovelCreate(BaseModel):
    title: str
    description: Optional[str] = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        if len(v) > 200:
            raise ValueError("标题长度不能超过 200 个字符")
        return v


class NovelUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        if v is not None and len(v) > 200:
            raise ValueError("标题长度不能超过 200 个字符")
        return v


class ChapterCreate(BaseModel):
    title: str
    content: str = ""

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        if len(v) > 200:
            raise ValueError("标题长度不能超过 200 个字符")
        return v


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
