import argparse
import json
from pathlib import Path
from backend.app.config import ROOT, Settings
from backend.app.embeddings import Embedder
from backend.app.retrieval import SearchEngine, load_collection


def evaluate(engine):
    cases = json.loads((ROOT / 'data' / 'evaluation.json').read_text(encoding='utf-8'))
    rows = []
    for case in cases:
        response = engine.search(case['query'])
        ids = [row['notice_id'] for row in response['results']]
        expected = set(case['expected_notice_ids'])
        chunks = {p['chunk_id'] for row in response['results'] for p in row['passages']}
        chunks.update(p['chunk_id'] for c in response['conflicts'] for p in (c['earlier'],c['newer']))
        revision_ok = not case.get('revision') or any(c['kind'] == 'explicit_revision' and {c['earlier']['notice_id'],c['newer']['notice_id']} == expected for c in response['conflicts'])
        rows.append({'query': case['query'], 'expected': sorted(expected), 'actual': ids,
            'hit_at_1': bool(expected.intersection(ids[:1])), 'hit_at_3': bool(expected.intersection(ids[:3])),
            'recall_at_5': len(expected.intersection(ids[:5])) / len(expected) if expected else None,
            'expected_chunks_found': set(case.get('expected_chunk_ids',[])).issubset(chunks),
            'unsupported_rejected': not response['found'] if not expected else None,
            'revision_ok': revision_ok,
            'passed': (bool(expected.intersection(ids[:3])) and set(case.get('expected_chunk_ids',[])).issubset(chunks) if expected else not response['found']) and revision_ok})
    supported = [r for r in rows if r['expected']]
    unsupported = [r for r in rows if not r['expected']]
    metrics = {'queries': len(rows), 'passed': sum(r['passed'] for r in rows),
        'hit_at_1': sum(r['hit_at_1'] for r in supported) / len(supported),
        'hit_at_3': sum(r['hit_at_3'] for r in supported) / len(supported),
        'recall_at_5': sum(r['recall_at_5'] for r in supported) / len(supported),
        'unsupported_rejection_rate': sum(r['unsupported_rejected'] for r in unsupported) / len(unsupported),
        'revision_checks_passed': all(r['revision_ok'] for r in rows)}
    return {'metrics': metrics, 'cases': rows}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='docs/evaluation-results.json')
    args = parser.parse_args()
    settings = Settings()
    engine = SearchEngine(settings, Embedder(settings), load_collection(settings.notices_path))
    report = evaluate(engine)
    Path(args.output).write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report['metrics'], indent=2))
    for row in report['cases']:
        if not row['passed']:
            print('FAIL:', row['query'], row['actual'], 'chunks:', row['expected_chunks_found'])
    raise SystemExit(0 if report['metrics']['passed'] == report['metrics']['queries'] else 1)
