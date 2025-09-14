from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
from typing import List, Dict, Optional
import uuid
from app.utils.config import get_settings
from app.utils.logging_optimized import get_logger, log_error
from app.utils.security import get_collection_name

logger = get_logger(__name__)

class QdrantService:
    """Qdrant vector database service"""
    
    def __init__(self):
        self.settings = get_settings()
        self.client = None
        self._connect()
    
    def _connect(self):
        """Connect to Qdrant"""
        try:
            self.client = QdrantClient(
                url=self.settings.qdrant_url,
                api_key=self.settings.qdrant_api_key
            )
            logger.info("Connected to Qdrant successfully")
        except Exception as e:
            log_error(e, "Failed to connect to Qdrant")
            raise Exception(f"Failed to connect to Qdrant: {e}")
    
    def create_collection(self, tenant: str) -> bool:
        """Create tenant-specific collection"""
        try:
            collection_name = get_collection_name(tenant)
            
            # Check if collection already exists
            collections = self.client.get_collections()
            existing_collections = [col.name for col in collections.collections]
            
            if collection_name in existing_collections:
                logger.info(f"Collection {collection_name} already exists")
                return True
            
            # Create collection
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(
                    size=self.settings.embedding_dimension,
                    distance=Distance.COSINE
                )
            )
            
            logger.info(f"Created collection {collection_name} for tenant {tenant}")
            return True
            
        except Exception as e:
            log_error(e, f"Error creating collection for tenant {tenant}")
            return False
    
    def upsert_chunks(self, tenant: str, chunks: List[Dict]) -> bool:
        """Upsert document chunks to vector database"""
        try:
            collection_name = get_collection_name(tenant)
            
            # Prepare points for upsertion
            points = []
            for chunk in chunks:
                # Generate unique point ID based on content
                point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{chunk['doc_id']}_{chunk['page']}_{chunk['chunk_idx']}_{chunk['sha256']}"))
                
                point = PointStruct(
                    id=point_id,
                    vector=chunk['embedding'],
                    payload={
                        "tenant": chunk['tenant'],
                        "doc_id": chunk['doc_id'],
                        "title": chunk['title'],
                        "drive_path": chunk['drive_path'],
                        "mime_type": chunk['mime_type'],
                        "page": chunk['page'],
                        "chunk_idx": chunk['chunk_idx'],
                        "sha256": chunk['sha256'],
                        "text": chunk['text']
                    }
                )
                points.append(point)
            
            # Upsert points
            self.client.upsert(
                collection_name=collection_name,
                points=points
            )
            
            logger.info(f"Upserted {len(points)} chunks for tenant {tenant}")
            return True
            
        except Exception as e:
            log_error(e, f"Error upserting chunks for tenant {tenant}")
            return False
    
    def search_similar(self, tenant: str, query_vector: List[float], top_k: int = 10, score_threshold: float = 0.0) -> List[Dict]:
        """Search for similar chunks"""
        try:
            collection_name = get_collection_name(tenant)
            
            # Perform search
            search_results = self.client.search(
                collection_name=collection_name,
                query_vector=query_vector,
                limit=top_k,
                score_threshold=score_threshold,
                with_payload=True
            )
            
            # Format results
            hits = []
            for result in search_results:
                hit = {
                    "text": result.payload.get("text", ""),
                    "doc_id": result.payload.get("doc_id", ""),
                    "title": result.payload.get("title", ""),
                    "page": result.payload.get("page", 0),
                    "score": result.score,
                    "drive_path": result.payload.get("drive_path", ""),
                    "chunk_idx": result.payload.get("chunk_idx", 0)
                }
                hits.append(hit)
            
            logger.info(f"Found {len(hits)} similar chunks for tenant {tenant}")
            return hits
            
        except Exception as e:
            log_error(e, f"Error searching similar chunks for tenant {tenant}")
            return []
    
    def delete_document(self, tenant: str, doc_id: str) -> bool:
        """Delete all chunks for a specific document"""
        try:
            collection_name = get_collection_name(tenant)
            
            # Delete points with matching doc_id
            self.client.delete(
                collection_name=collection_name,
                points_selector=Filter(
                    must=[
                        FieldCondition(
                            key="doc_id",
                            match=MatchValue(value=doc_id)
                        )
                    ]
                )
            )
            
            logger.info(f"Deleted chunks for document {doc_id} in tenant {tenant}")
            return True
            
        except Exception as e:
            log_error(e, f"Error deleting document {doc_id} for tenant {tenant}")
            return False
    
    def get_collection_info(self, tenant: str) -> Optional[Dict]:
        """Get collection information"""
        try:
            collection_name = get_collection_name(tenant)
            
            collection_info = self.client.get_collection(collection_name)
            
            return {
                "name": collection_name,
                "points_count": collection_info.points_count,
                "vectors_count": collection_info.vectors_count,
                "status": collection_info.status
            }
            
        except Exception as e:
            log_error(e, f"Error getting collection info for tenant {tenant}")
            return None
    
    def is_connected(self) -> bool:
        """Check if connected to Qdrant"""
        try:
            self.client.get_collections()
            return True
        except Exception:
            return False
