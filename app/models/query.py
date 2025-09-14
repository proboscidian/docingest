from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

class DocumentMetadata(BaseModel):
    """Document metadata model"""
    doc_id: str = Field(..., description="Document identifier")
    title: str = Field(..., description="Document title")
    mime_type: str = Field(..., description="MIME type")
    sha256: str = Field(..., description="SHA256 hash")
    modified_at: datetime = Field(..., description="Last modified time")
    drive_path: str = Field(..., description="Google Drive path")
    page_count: int = Field(default=0, description="Number of pages")
    chunk_count: int = Field(default=0, description="Number of chunks")

class ChunkData(BaseModel):
    """Chunk data model for vector storage"""
    tenant: str = Field(..., description="Tenant identifier")
    doc_id: str = Field(..., description="Document identifier")
    title: str = Field(..., description="Document title")
    drive_path: str = Field(..., description="Google Drive path")
    mime_type: str = Field(..., description="MIME type")
    page: int = Field(..., description="Page number")
    chunk_idx: int = Field(..., description="Chunk index within page")
    sha256: str = Field(..., description="SHA256 hash")
    text: str = Field(..., description="Chunk text content")
    embedding: Optional[List[float]] = Field(None, description="Vector embedding")

class DriveFile(BaseModel):
    """Google Drive file model"""
    id: str = Field(..., description="Google Drive file ID")
    name: str = Field(..., description="File name")
    mime_type: str = Field(..., description="MIME type")
    modified_time: datetime = Field(..., description="Last modified time")
    size: int = Field(..., description="File size in bytes")
    parents: List[str] = Field(default=[], description="Parent folder IDs")
    web_view_link: Optional[str] = Field(None, description="Web view link")
    sha256: Optional[str] = Field(None, description="SHA256 hash")

class ParsedPage(BaseModel):
    """Parsed page model"""
    page_number: int = Field(..., description="Page number")
    text: str = Field(..., description="Extracted text")
    has_text: bool = Field(..., description="Whether page has extractable text")
    needs_ocr: bool = Field(default=False, description="Whether OCR was needed")
    confidence: Optional[float] = Field(None, description="OCR confidence score")

class ParsedDocument(BaseModel):
    """Parsed document model"""
    doc_id: str = Field(..., description="Document identifier")
    title: str = Field(..., description="Document title")
    mime_type: str = Field(..., description="MIME type")
    pages: List[ParsedPage] = Field(..., description="List of parsed pages")
    total_pages: int = Field(..., description="Total number of pages")
    processing_time: float = Field(..., description="Processing time in seconds")
