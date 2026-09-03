import uuid
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


_EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    full_name: str
    email: str
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class UserCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=100)
    email: str = Field(max_length=255, pattern=_EMAIL_PATTERN)
    password: str = Field(min_length=8, max_length=100)
    role: Literal["AGENT", "MANAGER", "ADMIN"]


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=100)
    role: Literal["AGENT", "MANAGER", "ADMIN"] | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=8, max_length=100)


class PaginatedUsers(BaseModel):
    items: list[UserOut]
    total: int
    page: int
    page_size: int
    total_pages: int


class TeamMemberItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    user_id: uuid.UUID
    full_name: str
    email: str
    user_role: str
    team_role: Literal["MEMBER", "MANAGER"]
    is_active: bool
    joined_at: datetime


class TeamOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    description: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    member_count: int = 0


class TeamDetailOut(TeamOut):
    members: list[TeamMemberItem] = []


class TeamCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    description: str | None = Field(default=None, max_length=500)


class TeamUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    is_active: bool | None = None


class MemberAdd(BaseModel):
    user_id: uuid.UUID
    team_role: Literal["MEMBER", "MANAGER"] = "MEMBER"
