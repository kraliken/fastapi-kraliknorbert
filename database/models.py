from sqlmodel import Field, SQLModel, Relationship
from enum import Enum
from typing import Optional, List
from datetime import datetime, timezone
from pydantic import EmailStr


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

    todos: List["Todo"] = Relationship(back_populates="user")


class UserCreate(SQLModel):
    username: str
    password: str


class UserUpdate(SQLModel):
    email: str


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


class Category(str, Enum):
    work = "work"
    personal = "personal"
    development = "development"


class Status(str, Enum):
    backlog = "backlog"
    progress = "progress"
    done = "done"


class Todo(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = Field(index=True, min_length=3, max_length=255)
    description: Optional[str] = None
    category: Category = Field(default=Category.personal)
    status: Status = Field(default=Status.backlog)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    modified_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    deadline: datetime
    priority: Optional[int] = Field(default=1, ge=1, le=5)
    archived: bool = Field(default=False)

    user_id: int = Field(foreign_key="users.id")
    user: Optional[User] = Relationship(back_populates="todos")


class TodoRead(SQLModel):
    id: int
    title: str
    description: Optional[str] = None
    category: Category
    status: Status
    created_at: datetime
    modified_at: datetime
    completed_at: Optional[datetime] = None
    deadline: datetime


class TodoCreate(SQLModel):
    title: str
    description: Optional[str] = None
    category: Optional[Category] = Category.personal
    status: Optional[Status] = Status.backlog
    deadline: datetime
    priority: Optional[int] = 1
