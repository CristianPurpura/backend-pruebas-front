from pydantic import BaseModel


class DatasetUploadResponse(BaseModel):
    filename: str
    status: str
    rows_count: int
    columns_detected: list[str]
    message: str