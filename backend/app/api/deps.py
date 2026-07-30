"""Shared FastAPI dependencies."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import Unauthorized
from app.core.security import decode_token
from app.db.models import LearnerProfile, User
from app.db.session import get_session

DbSession = Annotated[AsyncSession, Depends(get_session)]


async def current_user(
    db: DbSession,
    authorization: Annotated[str | None, Header()] = None,
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise Unauthorized("Missing learner token.")

    user_id = decode_token(authorization.split(" ", 1)[1].strip())
    user = (
        await db.execute(select(User).where(User.id == user_id).options(selectinload(User.profile)))
    ).scalar_one_or_none()

    if user is None:
        raise Unauthorized("Learner not found.")
    if user.profile is None:
        # Self-heal rather than 500: a learner without a profile has no memory,
        # and losing memory is the one failure this product cannot ship.
        user.profile = LearnerProfile(user_id=user.id)
        db.add(user.profile)
        await db.flush()
    return user


CurrentUser = Annotated[User, Depends(current_user)]

__all__ = ["CurrentUser", "DbSession", "current_user"]
