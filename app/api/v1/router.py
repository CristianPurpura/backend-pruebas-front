from fastapi import APIRouter

from app.api.v1.endpoints import datasets, employability, health, occupations

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(occupations.router, prefix="/occupations")
api_router.include_router(datasets.router, prefix="/datasets", tags=["Datasets"])
api_router.include_router(employability.router, prefix="/employability", tags=["Employability"])
