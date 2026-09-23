from fastapi import APIRouter, HTTPException

from app.schemas.occupation import OccupationResponse

router = APIRouter()


@router.get("/{occupation_id}", response_model=OccupationResponse)
def get_occupation(occupation_id: str) -> OccupationResponse:
    if occupation_id != "OCUP_01":
        raise HTTPException(status_code=404, detail="Ocupación no encontrada")

    return OccupationResponse(
        country={"code": "ARG", "name": "Argentina"},
        sector={"id": "TEC", "name": "Tecnología"},
        occupation={
            "id": "OCUP_01",
            "name": "Desarrollador de Software y Aplicaciones",
            "isco_code": "2512",
        },
        indicators={"demand_level": "Muy Alta", "annual_growth": 18.5},
        skills=["Python", "FastAPI", "React", "SQL", "Git"],
        traceability={
            "source": "INDEC-EPH",
            "source_url": "https://www.indec.gob.ar",
            "last_updated": "2025-Q3",
            "retrieved_at": "2026-09-18",
            "data_type": "observed",
        },
    )