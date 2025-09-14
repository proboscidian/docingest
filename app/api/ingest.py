"""
Ingest API Router - Updated for centralized OAuth connections
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import Dict, Any
import asyncio
from datetime import datetime
from app.models.ingest import (
    IngestRequest, IngestResponse, JobProgress, 
    CollectionInitRequest, CollectionInitResponse
)
from app.services.google_drive_service import GoogleDriveService
from app.services.parser_service_optimized import ParserService
from app.services.embedding_service_optimized import EmbeddingService
from app.services.qdrant_service import QdrantService
from app.services.job_service import JobService
from app.services.token_storage import TokenStorage
from app.utils.logging_optimized import get_logger, log_error, log_ingest_progress
from app.utils.security import generate_job_id, validate_tenant_name

router = APIRouter()
logger = get_logger(__name__)

# Global job storage (in production, use Redis or database)
active_jobs: Dict[str, JobProgress] = {}

@router.post("/", response_model=IngestResponse)
async def start_ingest(request: IngestRequest, background_tasks: BackgroundTasks):
    """Start document ingestion job using OAuth connection"""
    try:
        # Normalize and validate tenant name (accept hyphens or underscores)
        normalized_tenant = request.tenant.replace('-', '_')
        if not validate_tenant_name(normalized_tenant):
            raise HTTPException(status_code=400, detail="Invalid tenant name")
        
        # Use normalized tenant for all operations
        request.tenant = normalized_tenant
        
        # Validate connection exists and is active
        token_storage = TokenStorage()
        connection = token_storage.get_connection(request.connection_id)
        
        if not connection:
            raise HTTPException(status_code=400, detail="Invalid or inactive connection ID")
        
        # Allow match against either raw or normalized tenant
        if connection['tenant'] not in (request.tenant, normalized_tenant):
            raise HTTPException(status_code=400, detail="Connection does not belong to this tenant")
        
        # Generate job ID
        job_id = generate_job_id()
        
        # Initialize job progress
        job_progress = JobProgress(
            job_id=job_id,
            status="queued",
            started_at=datetime.utcnow(),
            processed_docs=0,
            processed_pages=0,
            total_docs=0,
            total_pages=0,
            errors=[]
        )

        # Attach tenant for admin visibility
        try:
            job_progress.tenant = normalized_tenant  # type: ignore[attr-defined]
        except Exception:
            pass
        
        # Store job
        active_jobs[job_id] = job_progress
        
        # Start background task
        background_tasks.add_task(process_ingest_job, job_id, request)
        
        logger.info(f"Started ingest job {job_id} for tenant {normalized_tenant} using connection {request.connection_id}")
        
        return IngestResponse(
            success=True,
            job_id=job_id,
            message="Ingest job started successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        log_error(e, f"Error starting ingest job for tenant {request.tenant}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/job/{job_id}")
async def get_job_status(job_id: str):
    """Get job status and progress"""
    try:
        if job_id not in active_jobs:
            raise HTTPException(status_code=404, detail="Job not found")
        
        return active_jobs[job_id]
        
    except HTTPException:
        raise
    except Exception as e:
        log_error(e, f"Error getting job status for {job_id}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/collection/init", response_model=CollectionInitResponse)
async def init_collection(request: CollectionInitRequest):
    """Initialize Qdrant collection for tenant"""
    try:
        # Validate tenant name
        if not validate_tenant_name(request.tenant):
            raise HTTPException(status_code=400, detail="Invalid tenant name")
        
        # Create collection
        qdrant_service = QdrantService()
        success = qdrant_service.create_collection(request.tenant)
        
        if success:
            collection_name = f"sp_{request.tenant}"
            return CollectionInitResponse(
                success=True,
                collection_name=collection_name,
                message=f"Collection {collection_name} initialized successfully"
            )
        else:
            raise HTTPException(status_code=500, detail="Failed to create collection")
            
    except HTTPException:
        raise
    except Exception as e:
        log_error(e, f"Error initializing collection for tenant {request.tenant}")
        raise HTTPException(status_code=500, detail=str(e))

async def process_ingest_job(job_id: str, request: IngestRequest):
    """Process ingest job in background using OAuth connection"""
    try:
        # Update job status
        active_jobs[job_id].status = "running"
        
        # Initialize services
        drive_service = GoogleDriveService()
        parser_service = ParserService()
        embedding_service = EmbeddingService()
        qdrant_service = QdrantService()
        token_storage = TokenStorage()
        
        # Get connection details
        connection = token_storage.get_connection(request.connection_id)
        if not connection:
            raise Exception("Connection not found or inactive")
        
        # Ensure collection exists
        if not qdrant_service.create_collection(request.tenant):
            raise Exception("Failed to create Qdrant collection")
        
        # List files from Google Drive using connection
        all_files = []
        for folder_id in request.drive.folder_ids:
            files = await drive_service.list_drive_files(request.connection_id, folder_id)
            all_files.extend(files)
        
        active_jobs[job_id].total_docs = len(all_files)
        
        logger.info(f"Processing {len(all_files)} files for tenant {request.tenant}")
        
        # Process files concurrently (batch processing)
        import asyncio
        from concurrent.futures import ThreadPoolExecutor
        
        async def process_single_file(file):
            """Process a single file"""
            try:
                # Check if file needs processing
                if request.reingest == "incremental":
                    # TODO: Check against existing SHA256 in database
                    pass
                
                # Download file
                content, filename = await drive_service.download_file(request.connection_id, file['id'])
                
                # Parse document (synchronous call)
                parsed_doc = parser_service.parse_document(content, file['mime_type'], filename)
                
                # Generate chunks
                chunks = parser_service.chunk_document(parsed_doc)
                logger.info(f"Generated {len(chunks)} chunks for {filename}")
                
                # Debug chunk content
                for i, chunk in enumerate(chunks):
                    logger.info(f"Chunk {i+1}: text_length={len(chunk.get('text', ''))}")
                    if chunk.get('text'):
                        logger.info(f"Chunk {i+1} sample: {chunk['text'][:100]}...")
                
                if not chunks:
                    logger.warning(f"No chunks generated for {filename} - skipping Qdrant upsert")
                    return {
                        'success': True,
                        'filename': filename,
                        'pages': parsed_doc.total_pages,
                        'chunks': 0
                    }
                
                # Generate embeddings
                texts = [chunk["text"] for chunk in chunks]
                embeddings = await embedding_service.generate_embeddings(texts)
                
                # Add embeddings to chunks
                for i, chunk in enumerate(chunks):
                    chunk["embedding"] = embeddings[i]
                    chunk["tenant"] = request.tenant
                    chunk["drive_path"] = file.get('web_view_link', f"/{filename}")
                    chunk["sha256"] = drive_service.get_file_sha256(content)
                    chunk["doc_id"] = file['id']
                    chunk["title"] = filename
                    chunk["mime_type"] = file['mime_type']
                    chunk["page"] = chunk.get("page", 1)
                    chunk["chunk_idx"] = i
                
                # Upsert to Qdrant
                logger.info(f"Attempting to upsert {len(chunks)} chunks for tenant {request.tenant}")
                try:
                    result = qdrant_service.upsert_chunks(request.tenant, chunks)
                    if not result:
                        logger.error(f"Qdrant upsert returned False for {len(chunks)} chunks")
                        raise Exception("Failed to upsert chunks to Qdrant")
                    logger.info(f"Successfully upserted {len(chunks)} chunks")
                except Exception as e:
                    logger.error(f"Qdrant upsert exception: {e}")
                    raise Exception(f"Failed to upsert chunks to Qdrant: {e}")
                
                return {
                    'success': True,
                    'filename': filename,
                    'pages': parsed_doc.total_pages,
                    'chunks': len(chunks)
                }
                
            except Exception as e:
                error_msg = f"Error processing file {file.get('name', 'unknown')}: {str(e)}"
                logger.error(error_msg)
                return {
                    'success': False,
                    'filename': file.get('name', 'unknown'),
                    'error': error_msg
                }
        
        # Process files in batches of 5 concurrently
        batch_size = 5
        for i in range(0, len(all_files), batch_size):
            batch = all_files[i:i + batch_size]
            logger.info(f"Processing batch {i//batch_size + 1}: {len(batch)} files")
            
            # Process batch concurrently
            results = await asyncio.gather(*[process_single_file(file) for file in batch])
            
            # Update progress for successful files
            for result in results:
                if result['success']:
                    active_jobs[job_id].processed_docs += 1
                    active_jobs[job_id].processed_pages += result['pages']
                    
                    log_ingest_progress(
                        job_id, request.tenant,
                        active_jobs[job_id].processed_docs,
                        active_jobs[job_id].total_docs,
                        active_jobs[job_id].processed_pages,
                        active_jobs[job_id].total_pages
                    )
                else:
                    active_jobs[job_id].errors.append(result['error'])
        
        # Mark job as completed
        active_jobs[job_id].status = "completed"
        active_jobs[job_id].completed_at = datetime.utcnow()
        
        logger.info(f"Completed ingest job {job_id} for tenant {request.tenant}")
        
    except Exception as e:
        # Mark job as failed
        active_jobs[job_id].status = "failed"
        active_jobs[job_id].completed_at = datetime.utcnow()
        active_jobs[job_id].errors.append(str(e))
        log_error(e, f"Failed to process ingest job {job_id}")
        logger.error(f"Failed ingest job {job_id}: {str(e)}")
