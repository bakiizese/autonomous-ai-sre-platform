from typing import Optional

from fastapi import Header

from app.db.session import get_db  # noqa: F401  (re-exported for router imports)


def get_session_id(x_session_id: Optional[str] = Header(default=None)) -> Optional[str]:
    """No accounts this round — this is just an opaque, optional client-supplied
    id recorded on Repo.created_by_session_id, not an auth mechanism."""
    return x_session_id
