from fastapi import APIRouter, Depends, status, HTTPException, Response
from database.connection import SessionDep
from database.models import Todo, TodoCreate, TodoRead, User
from sqlmodel import select, func
from typing import Annotated, List
from datetime import datetime, timezone, timedelta
from routers.auth.oauth2 import get_current_user
from zoneinfo import ZoneInfo

router = APIRouter(prefix="/todos", tags=["todos"])


@router.get("/", response_model=List[TodoRead])
def get_todos(
    # current_user: Annotated[User, Depends(get_current_user)],
    session: SessionDep,
    category: str | None = None,
    period: str | None = None,
):
    # base_query = select(Todo).where(Todo.user_id == current_user.id)
    base_query = select(Todo)

    if category:
        base_query = base_query.where(Todo.category == category)

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
