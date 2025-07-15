from fastapi import APIRouter, Depends, status, HTTPException, Response, Query
from fastapi.responses import StreamingResponse
from database.connection import SessionDep
from database.models import (
    Todo,
    TodoCreate,
    TodoRead,
    TodoUpdate,
    TodoListResponse,
    User,
)
from sqlmodel import select, func
from enum import Enum
from typing import Annotated, List, Optional
from datetime import datetime, timezone, timedelta
from routers.auth.oauth2 import get_current_user
from zoneinfo import ZoneInfo
from io import BytesIO
import pandas as pd

router = APIRouter(prefix="/todos", tags=["todos"])


class StatusEnum(str, Enum):
    backlog = "backlog"
    progress = "progress"
    done = "done"


class CategoryEnum(str, Enum):
    personal = "personal"
    work = "work"
    development = "development"


@router.get("/", response_model=TodoListResponse)
def get_todos(
    current_user: Annotated[User, Depends(get_current_user)],
    session: SessionDep,
    period: str | None = None,
    category: Annotated[Optional[List[CategoryEnum]], Query()] = None,
    status: Annotated[Optional[List[StatusEnum]], Query()] = None,
    limit: int = Query(5, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    base_query = select(Todo).where(Todo.user_id == current_user.id)

    print("LIMIT", limit)

    if category:
        base_query = base_query.where(Todo.category.in_(category))

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

    # Teljes elemszám lekérdezése (szűrés után, paginálás nélkül)
    count_query = select(func.count()).select_from(base_query.subquery())
    total = session.exec(count_query).one()

    paginated_query = (
        base_query.order_by(Todo.deadline.asc()).offset(offset).limit(limit)
    )

    todos = session.exec(paginated_query).all()

    return {"items": todos, "total": total}


@router.get("/report/daily")
def get_todays_todos(
    current_user: Annotated[User, Depends(get_current_user)], session: SessionDep
):
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)

    done_stmt = select(Todo).where(
        Todo.user_id == current_user.id,
        Todo.status == "done",
        Todo.completed_at >= today_start,
        Todo.completed_at < today_end,
    )
    done_todos = session.exec(done_stmt).all()

    due_stmt = select(Todo).where(
        Todo.user_id == current_user.id,
        Todo.status != "done",
        Todo.deadline >= today_start,
        Todo.deadline < today_end,
    )
    due_todos = session.exec(due_stmt).all()

    return {
        "done_today": done_todos,
        "due_today": due_todos,
    }


@router.get("/report/weekly")
def get_todays_todos(
    current_user: Annotated[User, Depends(get_current_user)], session: SessionDep
):
    now = datetime.now(timezone.utc)

    # Hét kezdete (hétfő 00:00)
    week_start = now - timedelta(days=now.weekday())
    week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)

    # Hét vége (vasárnap 23:59:59)
    week_end = week_start + timedelta(days=7)

    done_stmt = select(Todo).where(
        Todo.user_id == current_user.id,
        Todo.status == "done",
        Todo.completed_at >= week_start,
        Todo.completed_at < week_end,
    )
    done_todos = session.exec(done_stmt).all()

    due_stmt = select(Todo).where(
        Todo.user_id == current_user.id,
        Todo.status != "done",
        Todo.deadline >= week_start,
        Todo.deadline < week_end,
    )
    due_todos = session.exec(due_stmt).all()

    return {
        "done_weekly": done_todos,
        "due_weekly": due_todos,
    }


@router.get("/report/daily/export")
def get_todays_todos(
    current_user: Annotated[User, Depends(get_current_user)], session: SessionDep
):
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)

    done_stmt = select(Todo).where(
        Todo.user_id == current_user.id,
        Todo.status == "done",
        Todo.completed_at >= today_start,
        Todo.completed_at < today_end,
    )
    done_todos = session.exec(done_stmt).all()

    due_stmt = select(Todo).where(
        Todo.user_id == current_user.id,
        Todo.status != "done",
        Todo.deadline >= today_start,
        Todo.deadline < today_end,
    )
    due_todos = session.exec(due_stmt).all()

    # service
    def todos_to_df(todos):
        if not todos:

            return pd.DataFrame(
                {
                    "Title": [""],
                    "Description": [""],
                    "Category": [""],
                    "Deadline": [""],
                    "Completed At": [""],
                    "Status": [""],
                }
            )
        return pd.DataFrame(
            [
                {
                    "Title": todo.title,
                    "Description": todo.description,
                    "Category": str(todo.category).split(".")[-1],
                    "Deadline": todo.deadline,
                    "Completed At": todo.completed_at,
                    "Status": str(todo.status).split(".")[-1],
                }
                for todo in todos
            ]
        )

    df_done = todos_to_df(done_todos)
    df_due = todos_to_df(due_todos)

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_done.to_excel(writer, sheet_name="Completed Today", index=False)
        df_due.to_excel(writer, sheet_name="Due Today", index=False)

    output.seek(0)

    filename = f"daily_report_{now.date()}.xlsx"

    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        },
    )


@router.get("/report/weekly/export")
def get_todays_todos(
    current_user: Annotated[User, Depends(get_current_user)], session: SessionDep
):
    now = datetime.now(timezone.utc)

    # Hét kezdete (hétfő 00:00)
    week_start = now - timedelta(days=now.weekday())
    week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)

    # Hét vége (vasárnap 23:59:59)
    week_end = week_start + timedelta(days=7)

    done_stmt = select(Todo).where(
        Todo.user_id == current_user.id,
        Todo.status == "done",
        Todo.completed_at >= week_start,
        Todo.completed_at < week_end,
    )
    done_todos = session.exec(done_stmt).all()

    due_stmt = select(Todo).where(
        Todo.user_id == current_user.id,
        Todo.status != "done",
        Todo.deadline >= week_start,
        Todo.deadline < week_end,
    )
    due_todos = session.exec(due_stmt).all()

    # service
    def todos_to_df(todos):
        if not todos:

            return pd.DataFrame(
                {
                    "Title": [""],
                    "Description": [""],
                    "Category": [""],
                    "Deadline": [""],
                    "Completed At": [""],
                    "Status": [""],
                }
            )
        df = pd.DataFrame(
            [
                {
                    "Title": todo.title,
                    "Description": todo.description,
                    "Category": str(todo.category).split(".")[-1],
                    "Deadline": todo.deadline,
                    "Completed At": todo.completed_at,
                    "Status": str(todo.status).split(".")[-1],
                }
                for todo in todos
            ]
        )
        return df.sort_values(["Category"])

    df_done = todos_to_df(done_todos)
    df_due = todos_to_df(due_todos)

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_done.to_excel(writer, sheet_name="Completed This Week", index=False)
        df_due.to_excel(writer, sheet_name="Due This Week", index=False)

    output.seek(0)

    filename = f"weekly_report_{now.date()}.xlsx"

    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        },
    )


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
