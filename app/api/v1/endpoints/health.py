from fastapi import APIRouter, Response, status

from app.core.database import async_check_db

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health(response: Response) -> dict[str, str]:
    db_status = await async_check_db()
    if db_status == "error":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "degraded", "db": db_status}
    return {"status": "ok", "db": db_status}
