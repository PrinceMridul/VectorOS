"""Identity.

The MVP uses a signed, long-lived learner token rather than passwords: the unit
of value is the *longitudinal learner model*, and forcing account creation
before a learner has felt the product costs more than it protects. The token
carries a user id and is verified on every request; swapping in Supabase Auth
means replacing `issue_token` / `decode_token` only.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from jose import JWTError, jwt

from app.core.config import settings
from app.core.errors import Unauthorized

ALGORITHM = "HS256"
TOKEN_TTL = timedelta(days=180)


def issue_token(user_id: UUID) -> str:
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": str(user_id),
            "iat": int(now.timestamp()),
            "exp": int((now + TOKEN_TTL).timestamp()),
        },
        settings.secret_key,
        algorithm=ALGORITHM,
    )


def decode_token(token: str) -> UUID:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        return UUID(payload["sub"])
    except (JWTError, KeyError, ValueError) as exc:
        raise Unauthorized("Invalid or expired session token.") from exc
