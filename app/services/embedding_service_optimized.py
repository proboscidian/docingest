from fastembed import TextEmbedding
from typing import List
import asyncio
from app.utils.config import get_settings
from app.utils.logging_optimized import get_logger

logger = get_logger(__name__)

class EmbeddingService:
    """Optimized vector embedding service using FastEmbed"""
    
    def __init__(self):
        self.settings = get_settings()
        self.model = None
        self._load_model()
    
    def _load_model(self):
        """Load the FastEmbed model"""
        try:
            logger.info("Loading FastEmbed model (BAAI/bge-small-en-v1.5)")
            # FastEmbed uses BAAI/bge-small-en-v1.5 by default
            self.model = TextEmbedding()
            logger.info("FastEmbed model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load FastEmbed model: {e}")
            raise Exception(f"Failed to load embedding model: {e}")
    
    async def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of texts"""
        if not self.model:
            raise Exception("Embedding model not loaded")
        
        try:
            if not texts:
                return []
            
            # Generate embeddings using FastEmbed
            embeddings = list(self.model.embed(texts))
            
            logger.info(f"Generated {len(embeddings)} embeddings using FastEmbed")
            return embeddings
            
        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            raise Exception(f"Failed to generate embeddings: {e}")
    
    async def generate_query_embedding(self, query: str) -> List[float]:
        """Generate embedding for a single query"""
        try:
            if not self.model:
                raise Exception("Embedding model not loaded")
            
            embeddings = list(self.model.embed([query]))
            return embeddings[0]
            
        except Exception as e:
            logger.error(f"Error generating query embedding for: {query}")
            raise Exception(f"Failed to generate query embedding: {e}")
    
    def get_embedding_dimension(self) -> int:
        """Get the dimension of embeddings"""
        return 384  # BAAI/bge-small-en-v1.5 dimension
    
    def is_model_loaded(self) -> bool:
        """Check if the model is loaded"""
        return self.model is not None
