from pydantic import BaseModel


class Country(BaseModel):
    code: str
    name: str


class Sector(BaseModel):
    id: str
    name: str


class Occupation(BaseModel):
    id: str
    name: str
    isco_code: str


class Indicators(BaseModel):
    demand_level: str
    annual_growth: float


class Traceability(BaseModel):
    source: str
    source_url: str
    last_updated: str
    retrieved_at: str
    data_type: str


class OccupationResponse(BaseModel):
    country: Country
    sector: Sector
    occupation: Occupation
    indicators: Indicators
    skills: list[str]
    traceability: Traceability