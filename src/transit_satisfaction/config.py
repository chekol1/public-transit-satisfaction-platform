"""Centralized, environment-driven configuration.

Replaces hardcoded credentials/paths that lived directly in scripts in the
original project (e.g. a MongoDB connection string with a plaintext
password committed to source control). Nothing secret should ever have a
default value here that looks like a real credential.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", protected_namespaces=("settings_",)
    )

    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db_name: str = "transit_satisfaction"
    model_artifact_path: str = "artifacts/model.pkl"
    log_level: str = "INFO"


settings = Settings()
