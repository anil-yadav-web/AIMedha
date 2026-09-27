import pytest
from fastapi.testclient import TestClient
from backend.app.config import Settings
from backend.app.main import create_app
from backend.app.retrieval import load_collection


@pytest.fixture
def client(embedder, tmp_path):
    settings = Settings(index_dir=tmp_path, admin_token='test-secret-only')
    with TestClient(create_app(settings, lambda s: embedder), raise_server_exceptions=False) as client:
        yield client


def test_health_notices_and_source(client):
    assert client.get('/api/health').json()['notice_count'] == 10
    assert len(client.get('/api/notices').json()['notices']) == 10
    assert 'laptop' in client.get('/api/notices/notice_01').json()['content']
    assert client.get('/api/notices/missing').status_code == 404
    assert client.get('/api/health').headers['X-Content-Type-Options'] == 'nosniff'


@pytest.mark.parametrize('payload',[{}, {'query':''}, {'query':'  '}, {'query':'x'*501}, {'query':123}])
def test_input_validation(client,payload):
    response = client.post('/api/search',json=payload)
    assert response.status_code == 422
    assert 'traceback' not in response.text.lower()


def test_malformed_and_oversized(client):
    assert client.post('/api/search',content='{').status_code == 422
    assert client.post('/api/search',content='x'*5000).status_code == 413


def test_normalized_query(client):
    response = client.post('/api/search',json={'query':'  What should I bring\n to the workshop?  '})
    assert response.status_code == 200
    assert response.json()['query'] == 'What should I bring to the workshop?'
    assert response.json()['results'][0]['notice_id'] == 'notice_01'


def test_admin_auth_and_ingestion(client):
    payload = {'notices':client.get('/api/notices').json()['notices']}
    assert client.post('/api/index',json=payload).status_code == 401
    assert client.post('/api/index',json=payload,headers={'Authorization':'Bearer wrong'}).status_code == 401
    response = client.post('/api/index',json=payload,headers={'Authorization':'Bearer test-secret-only'})
    assert response.status_code == 200
    assert response.json()['notice_count'] == 10
    assert client.get('/api/health').json()['notice_count'] == 10


def test_failed_index_preserves_old_collection(client,monkeypatch):
    payload = {'notices':client.get('/api/notices').json()['notices']}
    payload['notices'][0]['title'] = 'Changed title to invalidate cache'
    def fail(*args,**kwargs):
        raise RuntimeError('sensitive internal error')
    monkeypatch.setattr(client.app.state.engine.embedder, 'encode', fail)
    response = client.post('/api/index',json=payload,headers={'Authorization':'Bearer test-secret-only'})
    assert response.status_code == 503
    assert 'sensitive' not in response.text
    assert client.get('/api/notices/notice_01').json()['title'] != payload['notices'][0]['title']


def test_embedding_failure_is_friendly(client,monkeypatch):
    def fail(query):
        raise RuntimeError('secret internal service details')
    monkeypatch.setattr(client.app.state.engine.embedder,'query',fail)
    response = client.post('/api/search',json={'query':'a novel query'})
    assert response.status_code == 503
    assert 'temporarily unavailable' in response.text
    assert 'secret internal' not in response.text


def test_collection_survives_restart(embedder,tmp_path):
    settings = Settings(index_dir=tmp_path,admin_token='test-token')
    with TestClient(create_app(settings,lambda s:embedder)) as client:
        notices = client.get('/api/notices').json()['notices']
        notices[0]['title'] = 'Updated Workshop Title'
        assert client.post('/api/index',json={'notices':notices},headers={'Authorization':'Bearer test-token'}).status_code == 200
    with TestClient(create_app(settings,lambda s:embedder)) as client:
        assert client.get('/api/notices/notice_01').json()['title'] == 'Updated Workshop Title'
        assert client.get('/api/health').json()['notice_count'] == 10


def test_admin_disabled_by_default(embedder,tmp_path):
    settings = Settings(index_dir=tmp_path,admin_token='')
    with TestClient(create_app(settings,lambda s:embedder)) as client:
        notices = client.get('/api/notices').json()['notices']
        assert client.post('/api/index',json={'notices':notices}).status_code == 503
