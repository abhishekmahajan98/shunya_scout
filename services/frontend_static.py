import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parent.parent / "frontend" / "dist"
RESERVED_PATHS = {"docs", "openapi.json", "redoc"}


def frontend_dist_exists() -> bool:
    return STATIC_DIR.is_dir() and (STATIC_DIR / "index.html").is_file()


def mount_frontend(app: FastAPI) -> None:
    if not frontend_dist_exists():
        logger.info(
            "Frontend build not found at %s — run `npm run build` in frontend/",
            STATIC_DIR,
        )
        return

    assets_dir = STATIC_DIR / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="frontend-assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str) -> FileResponse:
        root = full_path.split("/", 1)[0] if full_path else ""
        if root in RESERVED_PATHS:
            raise HTTPException(status_code=404, detail="Not found")

        if full_path:
            candidate = (STATIC_DIR / full_path).resolve()
            if not str(candidate).startswith(str(STATIC_DIR.resolve())):
                raise HTTPException(status_code=404, detail="Not found")
            if candidate.is_file():
                return FileResponse(candidate)

        return FileResponse(STATIC_DIR / "index.html")
