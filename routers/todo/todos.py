from fastapi import APIRouter, Depends, status, HTTPException, Response, Query
from database.connection import SessionDep
from database.models import Todo, TodoCreate, TodoRead, TodoUpdate, User
from sqlmodel import select, func
from enum import Enum
from typing import Annotated, List, Optional
from datetime import datetime, timezone, timedelta
from routers.auth.oauth2 import get_current_user
from zoneinfo import ZoneInfo

router = APIRouter(prefix="/todos", tags=["todos"])


class StatusEnum(str, Enum):
    backlog = "backlog"
    progress = "progress"
    done = "done"


class CategoryEnum(str, Enum):
    personal = "personal"
    work = "work"
    development = "development"


@router.get("/", response_model=List[TodoRead])
def get_todos(
    current_user: Annotated[User, Depends(get_current_user)],
    session: SessionDep,
    # category: str | None = None,
    period: str | None = None,
    category: Annotated[Optional[List[CategoryEnum]], Query()] = None,
    status: Annotated[Optional[List[StatusEnum]], Query()] = None,
):
    base_query = select(Todo).where(Todo.user_id == current_user.id)

    if category:
        base_query = base_query.where(Todo.category.in_(category))

    # if category:
    #     base_query = base_query.where(Todo.category == category)

    HU_TZ = ZoneInfo("Europe/Budapest")
    now_local = datetime.now(HU_TZ)
    today = now_local.date()

    if period == "today":
        start_of_day = datetime.combine(today, datetime.min.time(), tzinfo=HU_TZ)
        end_of_day = start_of_day + timedelta(days=1)

        base_query = base_query.where(
            Todo.deadline >= start_of_day, Todo.deadline < end_of_day
        )
    if period == "upcoming":
        start_of_week = today - timedelta(days=today.weekday())
        end_of_week = start_of_week + timedelta(days=7)
        start_datetime = datetime.combine(start_of_week, datetime.min.time())
        end_datetime = datetime.combine(end_of_week, datetime.min.time())

        base_query = base_query.where(
            Todo.deadline >= start_datetime, Todo.deadline < end_datetime
        )

    if status:
        base_query = base_query.where(Todo.status.in_(status))

    todos = session.exec(base_query).all()

    return todos


@router.post("/create", status_code=status.HTTP_201_CREATED)
def create_todo(
    todo: TodoCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: SessionDep,
):
    todo_data = todo.model_dump()

    completed_at = None
    if todo_data.get("status") == "done":
        completed_at = datetime.now(timezone.utc)

    db_todo = Todo(**todo_data, user_id=current_user.id, completed_at=completed_at)

    session.add(db_todo)
    session.commit()
    session.refresh(db_todo)
    return db_todo


@router.delete("/{todo_id}")
def delete_todo(
    todo_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: SessionDep,
):
    todo = session.get(Todo, todo_id)
    if not todo or todo.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Todo not found")
    session.delete(todo)
    session.commit()
    return {"ok": True}


@router.patch("/{todo_id}")
def update_todo(
    todo_id: int,
    todo_update: TodoUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: SessionDep,
):
    db_todo = session.get(Todo, todo_id)

    if not db_todo or db_todo.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Todo not found")

    update_data = todo_update.model_dump(exclude_unset=True)

    new_status = update_data.get("status")
    if new_status is not None:
        if new_status == "done":
            db_todo.completed_at = datetime.now(timezone.utc)
        else:
            db_todo.completed_at = None

    for field, value in update_data.items():
        setattr(db_todo, field, value)

    db_todo.modified_at = datetime.now(timezone.utc)

    session.add(db_todo)
    session.commit()
    session.refresh(db_todo)
    return db_todo
