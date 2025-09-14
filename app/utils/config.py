from pydantic_settings import BaseSettings
from typing import List
import os

class Settings(BaseSettings):
    """Application settings"""
    
    # Qdrant Configuration
    qdrant_url: str = "https://your-cluster.qdrant.tech"
    qdrant_api_key: str = "your-qdrant-api-key"
    
    # Google OAuth Configuration (Centralized)
    google_client_id: str = "your-google-client-id"
    google_client_secret: str = "your-google-client-secret"
    google_redirect_uri: str = "https://docingest.industrialwebworks.net/oauth/callback"
    
    # Unstructured API Configuration
    unstructured_api_key: str = "your-unstructured-api-key"
    
    # FastEmbed Configuration
    embedding_model: str = "BAAI/bge-small-en-v1.5"  # FastEmbed default
    embedding_dimension: int = 384
    
    # Security Configuration
    api_secret_key: str = "your-shared-secret-with-proxy"
    jwt_secret_key: str = "your-jwt-secret-key"
    allowed_origins: List[str] = [
        "https://api.industrialwebworks.net",
        "https://switchprompt.industrialwebworks.net"
    ]
    
    # Logging Configuration
    log_level: str = "INFO"
    log_file_path: str = "./logs/docingest.log"
    
    # Redis Configuration
    redis_url: str = "redis://localhost:6379/0"
    
    # Application Configuration
    app_name: str = "Document Ingest Service"
    app_version: str = "1.0.0"
    debug: bool = False
    
    # Processing Configuration
    chunk_size: int = 1000
    chunk_overlap: int = 200
    max_file_size: int = 50 * 1024 * 1024  # 50MB
    supported_mime_types: List[str] = [
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/plain",
        "text/csv"
    ]
    
    class Config:
        env_file = ".env"
        case_sensitive = False

def get_settings() -> Settings:
    """Get application settings"""
    return Settings()
