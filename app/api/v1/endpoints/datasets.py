from fastapi import APIRouter, File, HTTPException, UploadFile

from app.schemas.dataset import DatasetUploadResponse
from app.services.parsers.dataset_parser import DatasetValidationError, parse_dataset

router = APIRouter()


@router.post("/upload", response_model=DatasetUploadResponse)
def upload_dataset(file: UploadFile = File(...)) -> DatasetUploadResponse:
    try:
        return parse_dataset(file)
    except DatasetValidationError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc