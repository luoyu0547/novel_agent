import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, field_validator

ChapterStatus = Literal["draft", "reviewed", "locked"]


class NovelCreate(BaseModel):
    title: str
    description: Optional[str] = None
    genre: Optional[str] = None
    style_guide: Optional[str] = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        if len(v) > 200:
            raise ValueError("标题长度不能超过 200 个字符")
        return v

    @field_validator("genre")
    @classmethod
    def validate_genre(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v) > 100:
            raise ValueError("类型长度不能超过 100 个字符")
        return v


class NovelUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    genre: Optional[str] = None
    style_guide: Optional[str] = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v) > 200:
            raise ValueError("标题长度不能超过 200 个字符")
        return v

    @field_validator("genre")
    @classmethod
    def validate_genre(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v) > 100:
            raise ValueError("类型长度不能超过 100 个字符")
        return v


class ChapterCreate(BaseModel):
    title: str
    content: str = ""
    summary: str = ""
    status: ChapterStatus = "draft"

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        if len(v) > 200:
            raise ValueError("标题长度不能超过 200 个字符")
        return v


class ChapterUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    summary: Optional[str] = None
    status: Optional[ChapterStatus] = None


class ChapterOut(BaseModel):
    id: int
    novel_id: int
    title: str
    content: str
    summary: str
    status: str
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = {"from_attributes": True}


class NovelOut(BaseModel):
    id: int
    title: str
    description: Optional[str]
    genre: Optional[str]
    style_guide: Optional[str]
    created_at: datetime.datetime
    updated_at: datetime.datetime
    chapters: Optional[List[ChapterOut]] = None

    model_config = {"from_attributes": True}


class NovelListItem(BaseModel):
    id: int
    title: str
    description: Optional[str]
    genre: Optional[str]
    style_guide: Optional[str]
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = {"from_attributes": True}
