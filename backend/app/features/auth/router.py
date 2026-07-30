"""Identity endpoints.

A learner starts with a name and nothing else. Gating the first session behind
account creation costs more learners than it protects, and the thing worth
protecting — the longitudinal model — does not exist until they have used it.
The token is long-lived and carries the learner id; swapping in Supabase Auth
touches this file only.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.core.security import issue_token
from app.db.models import LearnerProfile, User
from app.pedagogy.calibration import CalibrationSummary, cognitive_debt

router = APIRouter(prefix="/auth", tags=["auth"])


class StartRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=80)
    email: str | None = None


class ProfileView(BaseModel):
    vocabulary_tier: int
    unaided_wins: int
    hinted_wins: int
    hints_consumed: int
    offload_attempts: int
    cognitive_debt: float
    cognitive_debt_label: str
    calibration_label: str
    calibration_error: float
    pedagogy_notes: list[str]
    session_summaries: list[dict]


class UserView(BaseModel):
    id: str
    display_name: str
    email: str | None
    profile: ProfileView


class SessionToken(BaseModel):
    token: str
    user: UserView


def to_profile_view(profile: LearnerProfile) -> ProfileView:
    debt = cognitive_debt(
        unaided_wins=profile.unaided_wins,
        hinted_wins=profile.hinted_wins,
        hints_consumed=profile.hints_consumed,
        offload_attempts=profile.offload_attempts,
    )
    mean_error = (
        profile.calibration_error_sum / profile.calibration_samples
        if profile.calibration_samples
        else 0.0
    )
    summary = CalibrationSummary(
        samples=profile.calibration_samples,
        mean_error=round(mean_error, 3),
        overconfidence=round(mean_error, 3),
        blind_spots=0,
    )
    notes = (profile.pedagogy_notes or {}).get("observations", [])
    return ProfileView(
        vocabulary_tier=profile.vocabulary_tier,
        unaided_wins=profile.unaided_wins,
        hinted_wins=profile.hinted_wins,
        hints_consumed=profile.hints_consumed,
        offload_attempts=profile.offload_attempts,
        cognitive_debt=debt.score,
        cognitive_debt_label=debt.label,
        calibration_label=summary.label,
        calibration_error=summary.mean_error,
        pedagogy_notes=notes[-6:],
        session_summaries=(profile.session_summaries or [])[-8:],
    )


def to_user_view(user: User) -> UserView:
    assert user.profile is not None
    return UserView(
        id=str(user.id),
        display_name=user.display_name,
        email=user.email,
        profile=to_profile_view(user.profile),
    )


@router.post("/start", response_model=SessionToken)
async def start(payload: StartRequest, db: DbSession) -> SessionToken:
    """Create or resume a learner."""
    user: User | None = None
    if payload.email:
        user = (
            await db.execute(select(User).where(User.email == payload.email))
        ).scalar_one_or_none()

    if user is None:
        user = User(display_name=payload.display_name, email=payload.email)
        db.add(user)
        await db.flush()
        user.profile = LearnerProfile(user_id=user.id)
        db.add(user.profile)
        await db.flush()

    return SessionToken(token=issue_token(user.id), user=to_user_view(user))


@router.get("/me", response_model=UserView)
async def me(user: CurrentUser) -> UserView:
    return to_user_view(user)
