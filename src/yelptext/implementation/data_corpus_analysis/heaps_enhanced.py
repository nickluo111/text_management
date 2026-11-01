"""Reproducible Heaps analysis using the project's formal reader/tokenizer."""
from __future__ import annotations
import csv
import hashlib
import inspect
import json
import math
import os
from pathlib import Path
import shutil
import sqlite3
import time

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from yelptext.interface.data_corpus_analysis import create_review_reader, create_tokenizer

PUNCTUATION = frozenset({'!', '?', '#'})


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(8 * 1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def tokenizer_identity(tokenizer):
    path = Path(inspect.getfile(type(tokenizer)))
    return {'fingerprint': tokenizer.fingerprint(), 'source_sha256': file_sha256(path)}


def write_json(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    temporary.replace(path)


def write_csv(path, rows):
    if not rows:
        raise ValueError('No rows to write')
    with Path(path).open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def fit_heaps(points):
    x = np.log([point['N'] for point in points])
    y = np.log([point['V'] for point in points])
    if len(points) < 2 or len(set(x)) < 2 or not np.all(np.isfinite(x + y)):
        raise ValueError('Heaps fit needs >=2 distinct positive-token checkpoints')
    beta, intercept = np.polyfit(x, y, 1)
    residual = y - (intercept + beta * x)
    ss_total = float(np.sum((y-y.mean())**2))
    return {'k': float(np.exp(intercept)), 'beta': float(beta),
            'r_squared_log_space': float(1-np.sum(residual**2)/ss_total) if ss_total else None,
            'checkpoints': len(points)}


def run_heaps(root, config):
    root = Path(root).resolve()
    options = config.get('analysis', {}).get('heaps', {})
    seed = int(options.get('seed', 2026))
    source = (root / config['data']['prepared_path']).resolve()
    vocabulary = (root / config['tokenizer']['vocabulary_path']).resolve()
    output = (root / options.get('enhanced_output_dir', 'artifacts/heaps_enhanced')).resolve()
    output.mkdir(parents=True, exist_ok=True)
    summary_path = output / 'heaps_summary.json'
    if summary_path.exists():
        raise FileExistsError(f'Completed result already exists: {summary_path}. Choose a new output directory.')
    if not source.is_file() or not vocabulary.is_file():
        raise FileNotFoundError('Prepare reviews and build the configured vocabulary first.')
    tokenizer = create_tokenizer()
    identity = tokenizer_identity(tokenizer)
    print('Hashing prepared input for provenance and reusable random-order staging...', flush=True)
    source_hash = file_sha256(source)
    source_stat = source.stat()
    vocabulary_hash = file_sha256(vocabulary)
    expected = {
        'input_sha256': source_hash, 'tokenizer': identity, 'seed': seed,
        'ordering': 'BLAKE2b-128 keyed by SHA256(seed), sorted by (priority, doc_id)',
    }
    with sqlite3.connect(vocabulary.as_uri() + '?mode=ro', uri=True) as connection:
        metadata = {key: json.loads(value) for key, value in connection.execute('SELECT key,value_json FROM metadata')}
        if metadata.get('status') != 'COMPLETED':
            raise ValueError('Vocabulary is not COMPLETED')
        if metadata.get('tokenizer_fingerprint') != identity['fingerprint']:
            raise ValueError('Vocabulary and current tokenizer fingerprints disagree; rebuild vocabulary.')
        if metadata.get('min_cf') != 1 or metadata.get('min_df') != 1 or metadata.get('skip_types') != []:
            raise ValueError('Use an unpruned, unfiltered vocabulary.')
        expected_tokens = expected_types = 0
        for term, cf in connection.execute('SELECT term,cf FROM terms WHERE term_id <> 0 AND cf > 0'):
            if term not in PUNCTUATION:
                expected_tokens += cf
                expected_types += 1
        expected_raw_tokens = int(metadata['total_tokens'])
        expected_documents = int(metadata['document_count'])
    stage_path = output / 'random_order.sqlite'
    stage = sqlite3.connect(stage_path)
    stage.execute('PRAGMA cache_size=-65536')
    stage.execute('PRAGMA temp_store=FILE')
    stage.execute('CREATE TABLE IF NOT EXISTS run (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
    previous = dict(stage.execute('SELECT key,value FROM run'))
    if previous.get('complete') == 'true':
        if json.loads(previous['identity']) != expected:
            stage.close()
            raise ValueError('Staging belongs to different data/seed/tokenizer. Choose a new output directory.')
        document_count = int(previous['documents'])
        print(f'Reusing complete randomized staging: {document_count:,} reviews', flush=True)
    else:
        if previous:
            stage.close()
            raise ValueError('Incomplete staging exists. Remove random_order.sqlite only, then retry.')
        # The staging stores one copy of text plus IDs/indexes. This check is a conservative estimate, not a guarantee.
        if shutil.disk_usage(output).free < source_stat.st_size * 3:
            stage.close()
            raise OSError('Allow at least 3x prepared JSONL size free for staging, indexes and temporary work.')
        stage.execute('INSERT INTO run VALUES (?,?)', ('identity', json.dumps(expected, sort_keys=True)))
        stage.execute('CREATE TABLE documents (priority BLOB NOT NULL, doc_id TEXT NOT NULL UNIQUE, text TEXT NOT NULL, PRIMARY KEY(priority,doc_id)) WITHOUT ROWID')
        stage.commit()
        key = hashlib.sha256(str(seed).encode()).digest()
        batch = []
        document_count = 0
        for review in create_review_reader(source).iter_reviews():
            doc_id = review['doc_id']
            priority = hashlib.blake2b(doc_id.encode('utf-8'), key=key, digest_size=16).digest()
            batch.append((priority, doc_id, review['text']))
            document_count += 1
            if len(batch) >= 2000:
                stage.executemany('INSERT INTO documents VALUES (?,?,?)', batch)
                stage.commit()
                batch.clear()
            if document_count % 100_000 == 0:
                print(f'[stage] {document_count:,} reviews', flush=True)
        if batch:
            stage.executemany('INSERT INTO documents VALUES (?,?,?)', batch)
        if not document_count:
            raise ValueError('No reviews')
        if source.stat().st_size != source_stat.st_size or source.stat().st_mtime_ns != source_stat.st_mtime_ns:
            raise RuntimeError('Prepared input changed during staging')
        stage.executemany('INSERT OR REPLACE INTO run VALUES (?,?)', [('complete','true'), ('documents',str(document_count))])
        stage.commit()
    if document_count != expected_documents:
        stage.close()
        raise ValueError(f'Vocabulary documents={expected_documents}; prepared documents={document_count}')
    if document_count < 100:
        stage.close()
        raise ValueError('Use at least 100 reviews for 1% checkpoint grids.')
    work_path = output / 'seen_work.sqlite'
    seen = sqlite3.connect(work_path)
    seen.execute('PRAGMA cache_size=-32768')
    seen.execute('DROP TABLE IF EXISTS seen')
    seen.execute('CREATE TABLE seen(term TEXT PRIMARY KEY) WITHOUT ROWID')
    pending = set()
    unique_count = 0

    def flush():
        nonlocal unique_count
        before = seen.total_changes
        seen.executemany('INSERT OR IGNORE INTO seen VALUES (?)', ((term,) for term in pending))
        unique_count += seen.total_changes-before
        pending.clear()
        seen.commit()

    targets = {math.ceil(document_count*p/100): p for p in range(1,101)}
    points = []
    token_count = raw_count = empty_reviews = 0
    started = time.perf_counter()
    try:
        for index, (text,) in enumerate(stage.execute('SELECT text FROM documents ORDER BY priority,doc_id'),1):
            raw_terms = tokenizer.tokenize(text)
            terms = [term for term in raw_terms if term not in PUNCTUATION]
            raw_count += len(raw_terms)
            token_count += len(terms)
            empty_reviews += not terms
            pending.update(terms)
            if len(pending) >= 100_000 or index in targets:
                flush()
            if index in targets:
                point = {'percent': targets[index], 'fraction': targets[index]/100, 'reviews': index, 'N': token_count, 'V': unique_count}
                points.append(point)
                write_csv(output / 'growth_points.csv', points)
                print(f"[growth {targets[index]:3d}%] reviews={index:,} N={token_count:,} V={unique_count:,}", flush=True)
        flush()
    finally:
        seen.close()
        stage.close()
    if (token_count,unique_count,raw_count) != (expected_tokens,expected_types,expected_raw_tokens):
        raise ValueError(f'Endpoint mismatch: actual N/V/rawN={(token_count,unique_count,raw_count)}; vocabulary={(expected_tokens,expected_types,expected_raw_tokens)}. Check inputs and rebuild vocabulary.')
    by_percent = {point['percent']:point for point in points}
    main_points = [by_percent[p] for p in (10,30,50,100)]
    main = fit_heaps(main_points)
    prediction_model = fit_heaps([by_percent[p] for p in (10,30,50)])
    predicted = prediction_model['k'] * token_count**prediction_model['beta']
    prediction = {'fit_percentages':[10,30,50], 'target_percent':100,
                  'target_N':token_count, 'actual_V':unique_count, 'predicted_V':float(predicted),
                  'signed_error':float(predicted-unique_count),
                  'absolute_percentage_error':float(abs(predicted-unique_count)/unique_count*100),
                  'model':prediction_model,
                  'limitation':'Nested same-corpus extrapolation given observed target N; not an independent test corpus.'}
    grids = {
        'main_4': [10,30,50,100], 'matched_range_10':list(range(10,101,10)),
        'matched_range_19':list(range(10,101,5)), 'matched_range_91':list(range(10,101)),
        'full_range_100':list(range(1,101)), 'late_range_71':list(range(30,101)),
    }
    reference_n = by_percent[50]['N']
    main_reference = main['k']*reference_n**main['beta']
    sensitivity = []
    for name, grid in grids.items():
        model = fit_heaps([by_percent[p] for p in grid])
        sensitivity.append({'model':name, 'start_percent':min(grid), 'end_percent':max(grid), **model,
                            'delta_k_percent':(model['k']/main['k']-1)*100,
                            'delta_beta':model['beta']-main['beta'],
                            'reference_N':reference_n,
                            'prediction_at_reference_N':model['k']*reference_n**model['beta'],
                            'reference_prediction_delta_percent':(model['k']*reference_n**model['beta']/main_reference-1)*100})
    write_csv(output / 'sensitivity_parameters.csv', sensitivity)
    write_csv(output / 'main_checkpoints.csv', main_points)
    write_json(output / 'prediction.json', prediction)
    plot_x = np.geomspace(points[0]['N'],token_count,300)
    fig, ax = plt.subplots(figsize=(8,5),layout='constrained')
    ax.loglog([p['N'] for p in points],[p['V'] for p in points],color='#2463A5',label='Observed (1% checkpoints)')
    ax.loglog([p['N'] for p in main_points],[p['V'] for p in main_points],'o',color='#2463A5',label='Main fit checkpoints')
    ax.loglog(plot_x,main['k']*plot_x**main['beta'],'--',color='#C37722',label=f"Main fit: V={main['k']:.3g} N^{main['beta']:.3f}")
    ax.set(xlabel='Cumulative tokens N (punctuation filtered)',ylabel='Observed vocabulary V',title=f'Heaps growth; randomized review order, seed {seed}')
    ax.legend(); ax.grid(alpha=.2,which='both')
    for suffix in ('png','pdf'):
        fig.savefig(output / f'heaps_loglog.{suffix}',dpi=220)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(8,5),layout='constrained')
    late_x = np.geomspace(by_percent[10]['N'],token_count,300)
    ax.loglog([p['N'] for p in points],[p['V'] for p in points],color='#2463A5',label='Observed')
    ax.loglog(late_x,prediction_model['k']*late_x**prediction_model['beta'],'--',color='#C37722',label='Fit using 10%, 30%, 50%')
    ax.loglog([token_count],[predicted],'x',markersize=9,color='#A23B3B',label=f"100% prediction; APE={prediction['absolute_percentage_error']:.2f}%")
    ax.set(xlabel='Cumulative tokens N',ylabel='Vocabulary V',title='Within-corpus extrapolation to 100%')
    ax.legend(); ax.grid(alpha=.2,which='both')
    for suffix in ('png','pdf'):
        fig.savefig(output / f'heaps_prediction.{suffix}',dpi=220)
    plt.close(fig)
    summary = {'status':'COMPLETED', 'reviews':document_count,'total_tokens':token_count,'vocabulary_size':unique_count,
               'raw_total_tokens':raw_count,'empty_after_filter_reviews':empty_reviews,
               **expected,'input':str(source),'vocabulary':str(vocabulary),'vocabulary_sha256':vocabulary_hash,
               'punctuation_filter':sorted(PUNCTUATION),'stopword_removal':False,'endpoint_matches_vocabulary':True,
               'main_fit':main,'prediction':prediction,'sensitivity':sensitivity,
               'tokenization_and_checkpoint_seconds':time.perf_counter()-started,
               'limits':['One random seed; nested checkpoint errors are correlated.',
                         'OLS log-space fits are descriptive.',
                         'k depends on token units, preprocessing, and fitted interval.']}
    write_json(summary_path,summary)
    (output / 'report_notes.md').write_text(
        f"# Heaps results\n\nReviews: {document_count:,}; filtered tokens: {token_count:,}; types: {unique_count:,}.\n\n"
        f"Main fit (10/30/50/100% reviews): k={main['k']:.6g}, beta={main['beta']:.6g}, log-space R2={main['r_squared_log_space']:.6g}.\n\n"
        f"10/30/50% fit predicts {predicted:,.1f} types at observed full N; actual {unique_count:,}; absolute percentage error {prediction['absolute_percentage_error']:.4f}%.\n\n"
        "Sensitivity: first compare the 4/10/19/91-point fits over the same 10–100% interval. The 1–100% and 30–100% fits separately examine interval sensitivity. See sensitivity_parameters.csv.\n\n"
        "These are nested, single-seed observations. Prediction uses the same corpus and its observed full token count, not an independent test corpus.\n",encoding='utf-8')
    if not options.get('keep_random_order',False):
        stage_path.unlink()
    work_path.unlink(missing_ok=True)
    print(json.dumps({'status':'COMPLETED','output':str(output),'main_fit':main,'prediction_APE_percent':prediction['absolute_percentage_error']},indent=2),flush=True)
    return summary
