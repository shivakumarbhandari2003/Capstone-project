import os
import math
from typing import Optional
from backend.app.core.config import settings
from backend.app.core.logging_config import logger

import threading

# Enforce offline cache usage to avoid network timeouts when loading local models
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

class LocalEmbeddingService:
    """Generates 384-dimensional dense vectors using local BAAI/bge-small-en-v1.5."""
    _cached_models: dict = {}
    _cache_lock = threading.Lock()

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or settings.EMBEDDING_MODEL_NAME
        self.dimension = settings.EMBEDDING_DIMENSION
        self.batch_size = settings.EMBEDDING_BATCH_SIZE
        self.device = "cpu"
        self._model = None
        self._load_model()

    def _load_model(self):
        with self._cache_lock:
            if self.model_name in self._cached_models:
                self._model, self.device = self._cached_models[self.model_name]
                return

            try:
                from sentence_transformers import SentenceTransformer
                import torch
                if torch.cuda.is_available():
                    self.device = "cuda"
                logger.info(f"Loading local embedding model '{self.model_name}' on device '{self.device}'...")
                self._model = SentenceTransformer(self.model_name, device=self.device)
                self._cached_models[self.model_name] = (self._model, self.device)
                logger.info(f"Successfully loaded embedding model '{self.model_name}'")
            except Exception as e:
                logger.error(f"Failed to load SentenceTransformer model {self.model_name}: {e}")
                raise RuntimeError(f"Could not initialize local embedding model {self.model_name}: {e}")

    def generate_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Generate normalized dense embeddings in batches."""
        if not texts:
            return []
            
        if self._model is None:
            raise RuntimeError("Embedding model is not loaded.")

        logger.info(f"Generating embeddings for {len(texts)} chunks (batch size {self.batch_size})...")
        
        # sentence-transformers encode with batching and normalization
        raw_embeddings = self._model.encode(
            texts,
            batch_size=self.batch_size,
            show_progress_bar=False,
            normalize_embeddings=True
        )

        embeddings_list: list[list[float]] = []
        for i, vec in enumerate(raw_embeddings):
            vec_list = [float(x) for x in vec]
            
            # Validation: finite numbers and correct dimension
            if len(vec_list) != self.dimension:
                raise ValueError(
                    f"Embedding dimension mismatch at index {i}: expected {self.dimension}, got {len(vec_list)}"
                )
                
            for val in vec_list:
                if math.isnan(val) or math.isinf(val):
                    raise ValueError(f"Invalid non-finite value in embedding vector at index {i}: {val}")

            # Verify non-zero vector
            if all(v == 0.0 for v in vec_list):
                raise ValueError(f"Zero vector generated for text index {i}")

            embeddings_list.append(vec_list)

        logger.info(f"Successfully generated {len(embeddings_list)} valid embeddings.")
        return embeddings_list
