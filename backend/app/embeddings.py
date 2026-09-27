from functools import lru_cache
import httpx
import numpy as np


class Embedder:
    """Local ONNX inference by default; optional compatible remote embeddings API."""
    def __init__(self, settings):
        self.settings = settings
        if settings.embedding_provider == 'fastembed':
            from fastembed import TextEmbedding
            self.model = TextEmbedding(settings.embedding_model, cache_dir=str(settings.model_cache), threads=2)
        elif settings.embedding_provider == 'http':
            if not settings.embedding_api_url.startswith('https://') or not settings.api_key:
                raise ValueError('HTTP embeddings require an HTTPS URL and API_KEY')
        else:
            raise ValueError('EMBEDDING_PROVIDER must be fastembed or http')
        self.query = lru_cache(maxsize=settings.query_cache_size)(self._query)

    def encode(self, texts, query=False):
        if self.settings.embedding_provider == 'fastembed':
            method = self.model.query_embed if query else self.model.passage_embed
            vectors = np.asarray(list(method(texts)), dtype='float32')
        else:
            with httpx.Client(timeout=30) as client:
                response = client.post(self.settings.embedding_api_url,
                    headers={'Authorization': f'Bearer {self.settings.api_key}'},
                    json={'model': self.settings.embedding_model, 'input': texts})
                response.raise_for_status()
                rows = sorted(response.json()['data'], key=lambda row: row['index'])
                vectors = np.asarray([row['embedding'] for row in rows], dtype='float32')
        if vectors.ndim != 2 or len(vectors) != len(texts) or not np.isfinite(vectors).all():
            raise ValueError('Invalid embedding response')
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        if (norms == 0).any():
            raise ValueError('Empty embedding')
        return np.ascontiguousarray(vectors / norms)

    def _query(self, text):
        return self.encode([text], query=True)
