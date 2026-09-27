from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / '.env', extra='ignore')
    embedding_provider: str = 'fastembed'
    embedding_model: str = 'BAAI/bge-small-en-v1.5'
    embedding_api_url: str = ''
    api_key: str = ''
    model_cache: Path = ROOT / '.cache' / 'models'
    index_dir: Path = ROOT / '.cache' / 'index'
    notices_path: Path = ROOT / 'data' / 'notices.json'
    frontend_dist: Path = ROOT / 'frontend' / 'dist'
    similarity_threshold: float = Field(default=0.63, ge=0, le=1)
    top_k: int = Field(default=5, ge=1, le=10)
    admin_token: str = ''
    cors_origins: list[str] = []
    query_cache_size: int = Field(default=256, ge=0, le=4096)
