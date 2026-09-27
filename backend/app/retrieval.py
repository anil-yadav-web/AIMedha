"""Deterministic hybrid retrieval. Every returned passage is a source substring."""
import hashlib
import json
import re
import sqlite3
from pathlib import Path
import faiss
import numpy as np
from rank_bm25 import BM25Okapi
from .models import Collection

STOP = set('a an the is are was were what which who where when how do does did can could should would i we my me to for of on in at and or with it this that please tell about need needed required must bring carry submit get have will be you students student'.split())
REVISION = re.compile(r'\b(revis(?:ed|es|ion)|updat(?:ed|es)|exten(?:ded|sion)|postponed|rescheduled|supersedes|replaces|correction|modification)\b', re.I)
FACETS = {
    'deadline': r'\b(deadline|closes?|closing|last date|due|extended)\b',
    'venue': r'\b(venue|hall|room|auditorium|report|location)\b',
    'schedule': r'\b(schedule|scheduled|rescheduled|postponed|held|conducted)\b',
    'materials': r'\b(bring|carry|required|documents|laptop|identity)\b',
}
GENERIC_TOPIC = set('registration orientation membership allotment evening event meet instructions tools deadline update extended'.split())


def supports_requested_detail(query, passage):
    """Guard against a topic match being mistaken for the requested fact."""
    if re.search(r'\b(how much|cost|price|fee|fees|charges?)\b', query, re.I):
        if not re.search(r'(?:\b(?:Rs\.?|INR|rupees)\s*[\d,]+|₹\s*[\d,]+|\b(?:free|no fee|no charge)\b)', passage, re.I):
            return False
    if re.search(r'\b(password|wi[ -]?fi|internet)\b', query, re.I):
        if not re.search(r'\b(password|wi[ -]?fi|internet)\b', passage, re.I):
            return False
    return True


def tokens(text):
    return [t for t in re.findall(r'[a-z0-9]+', text.lower()) if t not in STOP]


def chunks(notice):
    result = []
    # Preserve exact text and offsets; split long paragraphs at sentence boundaries.
    for paragraph in re.finditer(r'\S[^\n]*(?:\n(?!\s*\n)[^\n]+)*', notice.content):
        start, end = paragraph.span()
        boundaries = [start]
        for match in re.finditer(r'(?<=[.!?])\s+', notice.content[start:end]):
            if start + match.end() - boundaries[-1] > 500:
                boundaries.append(start + match.end())
        boundaries.append(end)
        for left, right in zip(boundaries, boundaries[1:]):
            text = notice.content[left:right].rstrip()
            if text:
                result.append({'notice_id': notice.id, 'title': notice.title,
                    'publication_date': notice.publication_date.isoformat(), 'category': notice.category,
                    'source_filename': notice.source_filename, 'chunk_id': f'{notice.id}:{len(result)}',
                    'passage': text, 'start': left, 'end': left + len(text)})
    return result


class SearchEngine:
    def __init__(self, settings, embedder, notices):
        self.settings, self.embedder = settings, embedder
        self.notices = {n.id: n for n in notices}
        self.chunks = [c for n in notices for c in chunks(n)]
        self.index = None
        if not self.chunks:
            return
        documents = [c['title'] + '\n' + c['passage'] for c in self.chunks]
        fingerprint = hashlib.sha256(json.dumps([settings.embedding_provider, settings.embedding_model,
            settings.embedding_api_url, 'chunks-v1', documents], ensure_ascii=False).encode()).hexdigest()
        settings.index_dir.mkdir(parents=True, exist_ok=True)
        # SQLite commits atomically; a content-addressed snapshot survives restarts.
        with sqlite3.connect(settings.index_dir / 'embeddings.sqlite3') as db:
            db.execute('CREATE TABLE IF NOT EXISTS vectors (key TEXT PRIMARY KEY, rows INTEGER, dims INTEGER, value BLOB)')
            row = db.execute('SELECT rows,dims,value FROM vectors WHERE key=?', (fingerprint,)).fetchone()
            if row:
                vectors = np.frombuffer(row[2], dtype='float32').reshape(row[0], row[1]).copy()
            else:
                vectors = embedder.encode(documents)
                db.execute('INSERT OR REPLACE INTO vectors VALUES (?,?,?,?)',
                    (fingerprint, *vectors.shape, vectors.tobytes()))
        self.index = faiss.IndexFlatIP(vectors.shape[1])
        self.index.add(vectors)
        self.bm25 = BM25Okapi([tokens(t) for t in documents])
        self.vocabulary = set(tokens(' '.join(documents)))

    def evidence(self, index, score, query_tokens):
        chunk = self.chunks[index]
        spans = [list(m.span()) for m in re.finditer(r'\b\w+\b', chunk['passage']) if m.group().lower() in query_tokens]
        if query_tokens & {'bring', 'carry'}:
            material = re.search(r'\b(?:bring|carry)\s+(.+?)(?:[.!?]|$)', chunk['passage'], re.I)
            if material:
                spans = [list(material.span(1))]
        return {**chunk, 'score': round(float(score), 4), 'highlights': spans}

    def search(self, query):
        response = {'query': query, 'found': False, 'results': [], 'conflicts': [],
            'message': 'No matching information found.'}
        if self.index is None:
            response['message'] = 'No notices are currently available.'
            return response
        query_tokens = set(tokens(query)) | (set(re.findall(r'\w+', query.lower())) & {'bring', 'carry'})
        distances, indices = self.index.search(self.embedder.query(query), len(self.chunks))
        semantic = np.zeros(len(self.chunks))
        semantic[indices[0]] = distances[0]
        raw_bm25 = np.maximum(self.bm25.get_scores(tokens(query)), 0)
        lexical = raw_bm25 / (raw_bm25 + 3)
        scores = 0.85 * semantic + 0.15 * lexical
        topic_words = {nid: set(tokens(n.topic)) - GENERIC_TOPIC for nid,n in self.notices.items()}
        mentioned_topics = {nid for nid, words in topic_words.items() if words & query_tokens}
        accepted = [int(i) for i in np.argsort(-scores)
            if semantic[i] >= self.settings.similarity_threshold
            and scores[i] >= max(self.settings.similarity_threshold, scores.max() - 0.13)
            and (not mentioned_topics or self.chunks[i]['notice_id'] in mentioned_topics)
            and supports_requested_detail(query, self.chunks[i]['passage'])]
        grouped = {}
        for i in accepted:
            chunk = self.chunks[i]
            grouped.setdefault(chunk['notice_id'], []).append(self.evidence(i, scores[i], query_tokens))
        chosen = list(grouped)[:self.settings.top_k]
        conflicts = []
        seen = set()
        for nid in list(chosen):
            current = self.notices[nid]
            for other in self.notices.values():
                older, newer = sorted([current, other], key=lambda n: (n.publication_date, n.id))
                pair = (older.id, newer.id)
                if older.id == newer.id or pair in seen or older.publication_date == newer.publication_date:
                    continue
                reference = re.search(r'\b' + re.escape(older.id) + r'\b', newer.content, re.I)
                named_reference = older.title.casefold() in newer.content.casefold()
                explicit = older.id in newer.revises or bool((reference or named_reference) and REVISION.search(newer.content))
                same_topic = bool(older.topic and older.topic == newer.topic)
                if not (explicit or same_topic):
                    continue
                candidates = []
                for facet, pattern in FACETS.items():
                    if not re.search(pattern, query, re.I) and not (facet == 'deadline' and re.search(r'when.*regist', query, re.I)):
                        continue
                    left = [i for i,c in enumerate(self.chunks) if c['notice_id'] == older.id and re.search(pattern,c['passage'],re.I)]
                    right = [i for i,c in enumerate(self.chunks) if c['notice_id'] == newer.id and re.search(pattern,c['passage'],re.I)]
                    if left and right:
                        li, ri = max(left,key=lambda i:scores[i]), max(right,key=lambda i:scores[i])
                        if self.chunks[li]['passage'] != self.chunks[ri]['passage']:
                            candidates.append((li,ri))
                if not candidates:
                    continue
                li, ri = max(candidates, key=lambda p:scores[p[0]]+scores[p[1]])
                revision = bool(REVISION.search(self.chunks[ri]['passage']))
                # Explicit metadata is preferred. Same-topic language is only a possible revision.
                kind = 'explicit_revision' if explicit and revision else ('possible_revision' if revision else 'possible_conflict')
                conflicts.append({'kind': kind,
                    'message': 'The later notice explicitly revises the earlier instruction. Both passages are shown for verification.' if kind == 'explicit_revision' else 'These notices may contain different instructions. Verify both sources; a newer date alone does not establish authority.',
                    'earlier': self.evidence(li, scores[li], query_tokens),
                    'newer': self.evidence(ri, scores[ri], query_tokens)})
                seen.add(pair)
                for i in (li,ri):
                    cid = self.chunks[i]['notice_id']
                    if cid not in chosen:
                        chosen.append(cid)
                        grouped[cid] = [self.evidence(i,scores[i],query_tokens)]
        results = []
        for nid in chosen:
            passages = grouped[nid][:3]
            results.append({**passages[0], 'passages': passages})
        response.update(found=bool(results), results=results, conflicts=conflicts)
        if results:
            response.pop('message')
        return response


def load_collection(path: Path):
    return Collection(notices=json.loads(path.read_text(encoding='utf-8'))).notices
