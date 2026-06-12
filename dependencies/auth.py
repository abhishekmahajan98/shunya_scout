from typing import Annotated

from fastapi import Depends, Header, HTTPException

from services.auth import AuthError, get_user


async def require_user(
    authorization: Annotated[str | None, Header()] = None,
) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        return get_user(token)
    except AuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
