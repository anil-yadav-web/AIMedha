"""Exercise a running local or HTTPS deployment; no administrative writes."""
import argparse
import httpx

def check(base):
    with httpx.Client(base_url=base.rstrip('/'),timeout=60,follow_redirects=True) as client:
        home = client.get('/')
        assert home.status_code == 200 and 'Find That Notice' in home.text
        health = client.get('/api/health')
        assert health.status_code == 200 and health.json()['notice_count'] == 10
        assert len(client.get('/api/notices').json()['notices']) == 10
        found = client.post('/api/search',json={'query':'What should I bring to the workshop?'}).json()
        assert found['found'] and found['results'][0]['notice_id'] == 'notice_01'
        passage = found['results'][0]['passage']
        assert 'laptop' in passage
        source = client.get('/api/notices/notice_01').json()
        assert passage in source['content']
        revision = client.post('/api/search',json={'query':'When is the registration deadline?'}).json()
        assert any(c['kind'] == 'explicit_revision' for c in revision['conflicts'])
        unsupported = client.post('/api/search',json={'query':"What is today's weather?"}).json()
        assert not unsupported['found'] and unsupported['message'] == 'No matching information found.'
        assert client.post('/api/search',json={'query':' '}).status_code == 422
        assert client.get('/api/notices/unknown').status_code == 404
        assert client.get('/openapi.json').status_code == 200
        print('PASS: homepage, health, ten notices, semantic search, source viewer API, revision pair, unsupported query, validation, 404, OpenAPI.')
        print('Verified server:', str(home.url))

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('url',nargs='?',default='http://127.0.0.1:8000')
    check(parser.parse_args().url)
