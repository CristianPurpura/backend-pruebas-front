from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "dev"
    database_url: str = ""
    cors_origins: str = "*"

    datos_ar_base_url: str = "https://apis.datos.gob.ar"
    datos_ar_series_ids: str = "148.3_INIVELNAL_DICI_M_26"
    banco_mundial_base_url: str = "https://api.worldbank.org/v2"
    simel_base_url: str = "https://sdmx.ine.gob.cl/rest"
    raw_dir: str = "data/raw"
    processed_dir: str = "data/processed"
    quarantine_dir: str = "data/quarantine"
    reference_dir: str = "data/reference"

    # API del equipo de Data (repo `DataAnalyst`): módulo de Data Science con
    # brechas de talento, habilidades emergentes y comparativa educativo-laboral.
    data_api_url: str = "http://127.0.0.1:8001"
    data_api_timeout: float = 5.0
    data_cache_ttl: int = 300

    # Refresca los snapshots de IDELR/ICOL al terminar una carga manual. Si no
    # hay DATABASE_URL configurada, la carga sigue funcionando sin snapshot.
    auto_snapshot_after_upload: bool = True

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def datos_ar_series_ids_list(self) -> list[str]:
        return [serie.strip() for serie in self.datos_ar_series_ids.split(",") if serie.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
