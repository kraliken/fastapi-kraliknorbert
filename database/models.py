from sqlmodel import Field, SQLModel, Relationship
from enum import Enum
from typing import Optional, List
from datetime import datetime, timezone


class Role(str, Enum):
    admin = "admin"
    member = "member"


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True, min_length=6, max_length=50)
    email: Optional[str] = Field(
        default=None, index=True, unique=True, max_length=255, nullable=True
    )
    role: Role = Field(default=Role.member)
    hashed_password: str = Field(max_length=255)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class UserCreate(SQLModel):
    username: str
    password: str


class UserRead(SQLModel):
    id: int
    username: str
    email: Optional[str] = None
    role: Role
    created_at: datetime


class Token(SQLModel):
    access_token: str
    token_type: str


class TokenWithUser(Token):
    user: UserRead


class TokenData(SQLModel):
    username: str | None = None
