import asyncio
from contextlib import asynccontextmanager
import hmac
import json
import logging
import os
from pathlib import Path
import tempfile
import threading
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from .config import Settings
from .embeddings import Embedder
from .models import Collection, SearchRequest
from .retrieval import SearchEngine, load_collection

logger = logging.getLogger(__name__)


def create_app(settings=None, embedder_factory=Embedder):
    settings = settings or Settings()
    write_lock = threading.Lock()
    embed_lock = threading.Lock()
    collection_path = settings.index_dir / 'collection.json'

    @asynccontextmanager
    async def lifespan(app):
        try:
            embedder = await asyncio.to_thread(embedder_factory, settings)
            notices = load_collection(collection_path if collection_path.exists() else settings.notices_path)
            app.state.engine = await asyncio.to_thread(SearchEngine, settings, embedder, notices)
            app.state.ready = True
        except Exception:
            logger.exception('Initialization failed. Check model access, dataset, and cache permissions.')
            raise RuntimeError('Search initialization failed. Check server configuration and model availability.') from None
        yield
        app.state.ready = False

    app = FastAPI(title='Find That Notice API', version='1.0.0', lifespan=lifespan)
    app.state.ready = False
    if settings.cors_origins:
        app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins,
            allow_methods=['GET','POST'], allow_headers=['Content-Type','Authorization'])

    @app.middleware('http')
    async def security(request: Request, call_next):
        # Check actual bytes as well as Content-Length (which may be omitted).
        if request.method == 'POST':
            limit = 300_000 if request.url.path == '/api/index' else 4096
            body = bytearray()
            async for part in request.stream():
                body.extend(part)
                if len(body) > limit:
                    return JSONResponse({'message': 'Request is too large.'}, status_code=413)
            request._body = bytes(body)
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'same-origin'
        response.headers['X-Frame-Options'] = 'DENY'
        if not request.url.path.startswith(('/docs','/redoc')):
            response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        return response

    @app.exception_handler(RequestValidationError)
    async def invalid(request, exc):
        return JSONResponse({'message': 'Please enter a question of 1 to 500 characters.' if request.url.path == '/api/search' else 'Invalid notice collection. Provide exactly ten valid notices with unique IDs and valid revision links.'}, status_code=422)

    @app.exception_handler(Exception)
    async def unavailable(request, exc):
        logger.error('Request failed', exc_info=exc)
        return JSONResponse({'message': 'Search service is temporarily unavailable. Please try again.'}, status_code=503)

    @app.get('/api/health')
    def health():
        return JSONResponse({'status': 'ready' if app.state.ready else 'starting',
            'notice_count': len(app.state.engine.notices) if app.state.ready else 0,
            'embedding_provider': settings.embedding_provider}, status_code=200 if app.state.ready else 503)

    @app.post('/api/search')
    def search(payload: SearchRequest):
        try:
            with embed_lock:
                return app.state.engine.search(payload.query)
        except Exception:
            logger.exception('Search failed')
            raise HTTPException(503, 'Search service is temporarily unavailable. Please try again.') from None

    @app.get('/api/notices')
    def notices():
        return {'notices': [n.model_dump(mode='json') for n in app.state.engine.notices.values()]}

    @app.get('/api/notices/{notice_id}')
    def notice(notice_id: str):
        result = app.state.engine.notices.get(notice_id)
        if result is None:
            raise HTTPException(404, 'Notice not found.')
        return result

    def admin(authorization: str = Header(default='')):
        if not settings.admin_token:
            raise HTTPException(503, 'Collection management is disabled.')
        if not hmac.compare_digest(authorization, 'Bearer ' + settings.admin_token):
            raise HTTPException(401, 'Admin authorization required.')

    @app.post('/api/index', dependencies=[Depends(admin)])
    def index(payload: Collection):
        # Build first, publish atomically. Failed ingestion leaves the old service intact.
        if not write_lock.acquire(blocking=False):
            raise HTTPException(409, 'Another index update is in progress.')
        temp_path = None
        try:
            with embed_lock:
                candidate = SearchEngine(settings, app.state.engine.embedder, payload.notices)
                with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=settings.index_dir, delete=False) as handle:
                    json.dump([n.model_dump(mode='json') for n in payload.notices], handle, ensure_ascii=False)
                    temp_path = handle.name
                os.replace(temp_path, collection_path)
                app.state.engine = candidate
            return {'status': 'indexed', 'notice_count': len(candidate.notices), 'chunk_count': len(candidate.chunks)}
        finally:
            if temp_path and Path(temp_path).exists():
                Path(temp_path).unlink()
            write_lock.release()

    if settings.frontend_dist.is_dir():
        assets = settings.frontend_dist / 'assets'
        if assets.is_dir():
            app.mount('/assets', StaticFiles(directory=assets), name='assets')

        @app.get('/', include_in_schema=False)
        def frontend():
            return FileResponse(settings.frontend_dist / 'index.html')
    return app


app = create_app()
