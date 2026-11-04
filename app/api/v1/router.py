from fastapi import APIRouter

from app.api.v1.endpoints import (
    catalog,
    datascience,
    datasets,
    employability,
    health,
    occupations,
    snapshots,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(catalog.router, tags=["Catalogs"])
api_router.include_router(occupations.router, prefix="/occupations")
api_router.include_router(datasets.router, prefix="/datasets", tags=["Datasets"])
api_router.include_router(employability.router, prefix="/employability", tags=["Employability"])
api_router.include_router(snapshots.router, prefix="/employability", tags=["Snapshots"])
api_router.include_router(datascience.router)
api_router.include_router(datascience.gaps_router)
