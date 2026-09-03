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
