import pytest
from backend.app.config import Settings
from backend.app.embeddings import Embedder
from backend.app.retrieval import SearchEngine, load_collection


@pytest.fixture(scope='session')
def embedder():
    return Embedder(Settings())


@pytest.fixture(scope='session')
def engine(embedder, tmp_path_factory):
    settings = Settings(index_dir=tmp_path_factory.mktemp('index'))
    return SearchEngine(settings, embedder, load_collection(settings.notices_path))
