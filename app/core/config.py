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
