import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

WorldSettingCategory = Literal["geography", "faction", "rule", "history", "culture", "other"]


class CharacterCreate(BaseModel):
    name: str
    story_role: str = ""
    identity: str = ""
    personality: str = ""
    motivation: str = ""
    speech_style: str = ""
    behavior_rules: list[str] = Field(default_factory=list)
    current_state: str = ""

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("角色名不能为空")
        if len(v) > 100:
            raise ValueError("角色名长度不能超过 100 个字符")
        return v


class CharacterUpdate(BaseModel):
    name: Optional[str] = None
    story_role: Optional[str] = None
    identity: Optional[str] = None
    personality: Optional[str] = None
    motivation: Optional[str] = None
    speech_style: Optional[str] = None
    behavior_rules: Optional[list[str]] = None
    current_state: Optional[str] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.strip():
            raise ValueError("角色名不能为空")
        if v is not None and len(v) > 100:
            raise ValueError("角色名长度不能超过 100 个字符")
        return v


class CharacterOut(BaseModel):
    id: int
    novel_id: int
    name: str
    story_role: str
    identity: str
    personality: str
    motivation: str
    speech_style: str
    behavior_rules: list[str]
    current_state: str
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = {"from_attributes": True}


class WorldSettingCreate(BaseModel):
    title: str
    category: WorldSettingCategory = "other"
    content: str = ""

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("设定标题不能为空")
        if len(v) > 200:
            raise ValueError("设定标题长度不能超过 200 个字符")
        return v


class WorldSettingUpdate(BaseModel):
    title: Optional[str] = None
    category: Optional[WorldSettingCategory] = None
    content: Optional[str] = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.strip():
            raise ValueError("设定标题不能为空")
        if v is not None and len(v) > 200:
            raise ValueError("设定标题长度不能超过 200 个字符")
        return v


class WorldSettingOut(BaseModel):
    id: int
    novel_id: int
    title: str
    category: str
    content: str
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = {"from_attributes": True}
