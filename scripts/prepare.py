"""Download the local model at build time, before serving traffic."""
from backend.app.config import Settings
from backend.app.embeddings import Embedder

if __name__ == '__main__':
    settings = Settings()
    embedder = Embedder(settings)
    print('Embedding model ready:', settings.embedding_model, embedder.encode(['Model readiness check']).shape)
