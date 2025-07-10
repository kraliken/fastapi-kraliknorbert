from fastapi import APIRouter, Depends, HTTPException
from typing import Annotated
from database.models import User, UserRead, UserUpdate
from routers.auth.oauth2 import get_current_user
from database.connection import SessionDep
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

router = APIRouter(prefix="/users", tags=["users"])


@router.patch("/update", response_model=UserRead)
def update_user(
    user_update: UserUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: SessionDep,
):
    update_data = user_update.model_dump(exclude_unset=True)

    new_email = update_data["email"]

    if new_email == current_user.email:
        raise HTTPException(
            status_code=400, detail="Email is already set to this value."
        )

    db_user = session.get(User, current_user.id)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    for field, value in update_data.items():
        if hasattr(db_user, field):
            setattr(db_user, field, value)

    try:
        session.commit()
        session.refresh(db_user)
    except IntegrityError as e:
        session.rollback()
        if "email" in str(e).lower():
            raise HTTPException(status_code=409, detail="Email already in use.")
        raise HTTPException(status_code=409, detail="Data integrity error occurred.")
    except SQLAlchemyError as e:
        session.rollback()
        raise HTTPException(
            status_code=500,
            detail="An error occurred while updating your account. Please try again.",
        )

    return db_user
