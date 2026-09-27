"""Validate and index locally, or replace a running server's collection."""
import argparse
import os
import httpx
from backend.app.config import Settings
from backend.app.embeddings import Embedder
from backend.app.retrieval import SearchEngine, load_collection

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--file', type=str)
    parser.add_argument('--url', help='Running server base URL; requires ADMIN_TOKEN')
    args = parser.parse_args()
    settings = Settings()
    if args.file:
        from pathlib import Path
        settings.notices_path = Path(args.file)
    notices = load_collection(settings.notices_path)
    if args.url:
        if not settings.admin_token:
            parser.error('Set ADMIN_TOKEN before replacing the server collection')
        with httpx.Client(timeout=120) as client:
            response = client.post(args.url.rstrip('/') + '/api/index',
                headers={'Authorization': 'Bearer ' + settings.admin_token},
                json={'notices': [n.model_dump(mode='json') for n in notices]})
            response.raise_for_status()
            print(response.json())
    else:
        engine = SearchEngine(settings, Embedder(settings), notices)
        print(f'Validated and cached {len(engine.notices)} notices / {len(engine.chunks)} passages.')
        print('To activate a different file locally, set NOTICES_PATH before starting the server.')
