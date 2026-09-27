import json
import sqlite3
import pytest
from backend.app.config import ROOT, Settings
from backend.app.models import Collection, Notice
from backend.app.retrieval import SearchEngine, chunks, load_collection

CASES = json.loads((ROOT / 'data' / 'evaluation.json').read_text(encoding='utf-8'))


@pytest.mark.parametrize('case', CASES, ids=[case['query'] for case in CASES])
def test_evaluation(engine, case):
    result = engine.search(case['query'])
    if not case['expected_notice_ids']:
        assert not result['found']
        assert result['results'] == []
        assert result['message'] == 'No matching information found.'
        return
    ids = [r['notice_id'] for r in result['results']]
    assert set(ids[:3]) & set(case['expected_notice_ids'])
    evidence = [p for r in result['results'] for p in r['passages']]
    evidence += [p for c in result['conflicts'] for p in (c['earlier'],c['newer'])]
    assert set(case.get('expected_chunk_ids',[])) <= {p['chunk_id'] for p in evidence}
    for passage in evidence:
        source = engine.notices[passage['notice_id']].content
        assert source[passage['start']:passage['end']] == passage['passage']
        for start,end in passage['highlights']:
            assert 0 <= start < end <= len(passage['passage'])
    if case.get('revision'):
        assert any(c['kind'] == 'explicit_revision' and c['earlier']['notice_id'] == 'notice_01' and c['newer']['notice_id'] == 'notice_10' for c in result['conflicts'])


def test_index_cache_is_idempotent(engine, monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError('Cached document embeddings must not be regenerated')
    monkeypatch.setattr(engine.embedder, 'encode', fail)
    again = SearchEngine(engine.settings, engine.embedder, list(engine.notices.values()))
    assert again.index.ntotal == engine.index.ntotal
    with sqlite3.connect(engine.settings.index_dir / 'embeddings.sqlite3') as db:
        assert db.execute('SELECT count(*) FROM vectors').fetchone()[0] == 1


def test_source_offsets_preserved():
    notice = Notice(id='test',title='Test',publication_date='2026-01-01',content='First paragraph.\n\n  Second paragraph with spacing.\nContinued line.\n\nThird.')
    found = chunks(notice)
    assert len(found) == 3
    assert all(notice.content[c['start']:c['end']] == c['passage'] for c in found)


def test_collection_constraints(engine):
    notices = list(engine.notices.values())
    with pytest.raises(ValueError):
        Collection(notices=notices[:9])
    with pytest.raises(ValueError):
        Collection(notices=[notices[0]] * 10)
    invalid = notices[-1].model_copy(update={'revises':['absent']})
    with pytest.raises(ValueError):
        Collection(notices=[*notices[:9],invalid])


def test_no_newer_authority_without_revision(embedder, tmp_path):
    settings = Settings(index_dir=tmp_path)
    notices = load_collection(settings.notices_path)
    notices[-1] = notices[-1].model_copy(update={'content':'AI workshop registration closes on 20 September 2026.', 'revises':[]})
    result = SearchEngine(settings,embedder,notices).search('When is the workshop registration deadline?')
    assert any(c['kind'] == 'possible_conflict' for c in result['conflicts'])
    assert not any(c['kind'] == 'explicit_revision' for c in result['conflicts'])


def test_unrelated_deadlines_not_linked(engine):
    result = engine.search('When is the scholarship application deadline?')
    assert not result['conflicts']
    assert result['results'][0]['notice_id'] == 'notice_03'


def test_explicit_source_reference_without_optional_links(embedder,tmp_path):
    settings = Settings(index_dir=tmp_path)
    notices = [n.model_copy(update={'topic':'','revises':[]}) for n in load_collection(settings.notices_path)]
    result = SearchEngine(settings,embedder,notices).search('When is the registration deadline?')
    assert any(c['kind'] == 'explicit_revision' and c['earlier']['notice_id'] == 'notice_01' and c['newer']['notice_id'] == 'notice_10' for c in result['conflicts'])


def test_empty_collection(embedder, tmp_path):
    result = SearchEngine(Settings(index_dir=tmp_path),embedder,[]).search('Workshop?')
    assert not result['found']
    assert result['message'] == 'No notices are currently available.'
