from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from app.services.qdrant_service import QdrantService
from app.services.embedding_service_optimized import EmbeddingService
from app.utils.logging_optimized import get_logger
from app.utils.security import validate_tenant_name
from app.api.health import validate_api_key

logger = get_logger(__name__)

router = APIRouter()

class SearchRequest(BaseModel):
    """Request model for vector search"""
    tenant: str = Field(..., description="Tenant identifier")
    query: str = Field(..., description="Search query text")
    top_k: int = Field(default=5, ge=1, le=20, description="Number of results to return")
    score_threshold: float = Field(default=0.0, ge=0.0, le=1.0, description="Minimum relevance score")
    
    class Config:
        json_schema_extra = {
            "example": {
                "tenant": "exciting-heisenberg-docingest",
                "query": "carbide coating warranty",
                "top_k": 5,
                "score_threshold": 0.5
            }
        }

class SearchResult(BaseModel):
    """Individual search result"""
    text: str = Field(..., description="Document chunk text")
    metadata: Dict = Field(..., description="Document metadata")
    score: float = Field(..., description="Relevance score")
    
class SearchResponse(BaseModel):
    """Response model for search results"""
    results: List[SearchResult] = Field(..., description="Search results")
    total_results: int = Field(..., description="Total number of results found")
    query: str = Field(..., description="Original search query")
    tenant: str = Field(..., description="Tenant identifier")

# Create separate router for health check (no auth)
health_router = APIRouter()

@health_router.get("/health")
async def search_health():
    """Health check for search service (no auth required)"""
    try:
        # Test services
        embedding_service = EmbeddingService()
        qdrant_service = QdrantService()
        
        # Quick connectivity test
        test_embedding = await embedding_service.generate_query_embedding("test")
        
        return {
            "status": "healthy",
            "embedding_service": "operational",
            "qdrant_service": "operational",
            "embedding_dimension": len(test_embedding)
        }
    except Exception as e:
        logger.error(f"Search health check failed: {e}")
        raise HTTPException(status_code=500, detail=f"Search service unhealthy: {str(e)}")

@router.get("/documents", response_model=Dict)
async def list_documents(
    tenant: str,
    api_key: str = Depends(validate_api_key)
):
    """
    List all documents in the vector database for a tenant
    
    This endpoint returns all documents stored in the vector database,
    not just search results. Useful for getting complete document inventory.
    """
    try:
        # Normalize and validate tenant name
        normalized_tenant = tenant.replace('-', '_')
        if not validate_tenant_name(normalized_tenant):
            raise HTTPException(status_code=400, detail="Invalid tenant name")
        
        # Initialize services
        qdrant_service = QdrantService()
        
        logger.info(f"Listing documents for tenant {normalized_tenant}")
        
        # Get all points from Qdrant
        try:
            result = qdrant_service.client.scroll(
                collection_name=f"sp_{normalized_tenant}",
                limit=1000,  # Large limit to get all documents
                with_payload=True
            )
            
            documents = {}
            for point in result[0]:
                payload = point.payload
                title = payload.get('title', 'Unknown')
                if title not in documents:
                    documents[title] = {
                        'title': title,
                        'chunks': 0,
                        'pages': set(),
                        'doc_id': payload.get('doc_id', ''),
                        'source': payload.get('source', 'google_drive'),
                        'total_chunks': 0
                    }
                documents[title]['chunks'] += 1
                if 'page' in payload:
                    documents[title]['pages'].add(payload['page'])
            
            # Format response
            document_list = []
            for doc_name, info in documents.items():
                pages = sorted(list(info['pages'])) if info['pages'] else [1]
                document_list.append({
                    'title': info['title'],
                    'chunks': info['chunks'],
                    'pages': pages,
                    'total_pages': len(pages),
                    'doc_id': info['doc_id'],
                    'source': info['source']
                })
            
            # Sort by title
            document_list.sort(key=lambda x: x['title'])
            
            response = {
                'documents': document_list,
                'total_documents': len(document_list),
                'total_chunks': sum(doc['chunks'] for doc in document_list),
                'tenant': normalized_tenant
            }
            
            logger.info(f"Listed {len(document_list)} documents for tenant {normalized_tenant}")
            return response
            
        except Exception as e:
            logger.error(f"Error scrolling Qdrant collection: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to retrieve documents: {str(e)}")
        
    except Exception as e:
        logger.error(f"Document listing error for tenant {tenant}: {e}")
        raise HTTPException(status_code=500, detail=f"Document listing failed: {str(e)}")

@router.post("/", response_model=SearchResponse)
async def search_documents(
    request: SearchRequest,
    api_key: str = Depends(validate_api_key)
):
    """
    Search documents in the vector database
    
    This endpoint allows plugins to search through ingested documents
    using semantic similarity search.
    """
    try:
        # Normalize and validate tenant name
        normalized_tenant = request.tenant.replace('-', '_')
        if not validate_tenant_name(normalized_tenant):
            raise HTTPException(status_code=400, detail="Invalid tenant name")
        
        # Initialize services
        embedding_service = EmbeddingService()
        qdrant_service = QdrantService()
        
        logger.info(f"Search request for tenant {normalized_tenant}: '{request.query}'")
        
        # Generate query embedding
        query_embedding = await embedding_service.generate_query_embedding(request.query)
        logger.info(f"Generated query embedding: {len(query_embedding)} dimensions")
        
        # Search in Qdrant
        search_results = qdrant_service.search_similar(
            tenant=normalized_tenant,
            query_vector=query_embedding,
            top_k=request.top_k,
            score_threshold=request.score_threshold
        )
        
        logger.info(f"Found {len(search_results)} results for query: '{request.query}'")
        
        # Format results
        formatted_results = []
        for result in search_results:
            formatted_results.append(SearchResult(
                text=result["text"],
                metadata={
                    "title": result["title"],
                    "page": result.get("page", 1),
                    "doc_id": result.get("doc_id", ""),
                    "chunk_idx": result.get("chunk_idx", 0),
                    "source": result.get("source", "google_drive")
                },
                score=result["score"]
            ))
        
        response = SearchResponse(
            results=formatted_results,
            total_results=len(formatted_results),
            query=request.query,
            tenant=normalized_tenant
        )
        
        logger.info(f"Search completed: {len(formatted_results)} results returned")
        return response
        
    except Exception as e:
        logger.error(f"Search error for tenant {request.tenant}: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")
