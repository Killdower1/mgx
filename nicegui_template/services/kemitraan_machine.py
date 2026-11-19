"""Physical-machine sales ledger. No outlet-to-machine or price inference."""
from __future__ import annotations

import json
import math
import os
import re
import tempfile
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / 'streamlit_template/data/api_cache/raw_by_month'
RS = ROOT / 'streamlit_template/data/api_cache/rs_outlet.json'
CACHE = ROOT / 'streamlit_template/data/api_cache/kemitraan_machine_sales.json'


def stream_json_array(path):
    """Bounded streaming of a top-level JSON array; reject truncated input."""
    decoder = json.JSONDecoder()
    with open(path, encoding='utf-8') as fh:
        buffer = ''
        opened = False
        while True:
            chunk = fh.read(65536)
            buffer += chunk
            if not opened:
                buffer = buffer.lstrip()
                if not buffer:
                    if chunk:
                        continue
                    raise ValueError('Empty raw JSON array')
                if buffer[0] != '[':
                    raise ValueError('Expected raw JSON array')
                buffer = buffer[1:]
                opened = True
            while True:
                buffer = buffer.lstrip()
                if buffer.startswith(']'):
                    if buffer[1:].strip() or fh.read(1).strip():
                        raise ValueError('Trailing data after raw array')
                    return
                if buffer.startswith(','):
                    buffer = buffer[1:]
                    continue
                if not buffer:
                    break
                try:
                    obj, end = decoder.raw_decode(buffer)
                except json.JSONDecodeError:
                    if not chunk:
                        raise ValueError('Truncated raw JSON array')
                    break
                if not isinstance(obj, dict):
                    raise ValueError('Expected transaction object')
                yield obj
                buffer = buffer[end:]
            if not chunk:
                raise ValueError('Truncated raw JSON array')


def positive(value):
    try:
        n = float(value or 0)
        return n if math.isfinite(n) and n >= 0 else 0.0
    except (TypeError, ValueError):
        return 0.0


def aggregate(files):
    """Keep only grouped daily machine/outlet/placement totals, not raw transactions."""
    result = {}
    for path in sorted(files):
        period = path.stem
        groups = defaultdict(lambda: [0, 0.0, 0.0, '', ''])
        outlets = defaultdict(lambda: [0, 0.0, 0.0, 0, 0.0, 0.0])
        for t in stream_json_array(path):
            if t.get('status') != 'done' or t.get('payment_status') != 'paid':
                continue
            day = str(t.get('date') or '')[:10]
            if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', day) or day[:7] != period:
                continue
            outlet = str(t.get('outlet_name') or '').strip()
            gross = positive(t.get('processed_gross_amount'))
            share = gross * min(positive(t.get('partner_share')), 100) / 100
            machine = str(t.get('machine_id') or '').strip()
            placement = str(t.get('machine_placement_id') or '').strip()
            a = groups[(machine, outlet, placement, day)]
            a[0] += 1; a[1] += gross; a[2] += share
            a[3] = min(a[3] or day, day); a[4] = max(a[4], day)
            b = outlets[outlet]
            side = 0 if machine else 3
            b[side] += 1; b[side+1] += gross; b[side+2] += share
        result[period] = {
            'source_mtime_ns': path.stat().st_mtime_ns, 'source_size': path.stat().st_size,
            'rows': [{'machine_id': m, 'outlet': o, 'placement_id': pl, 'day': day,
                      'transactions': a[0], 'gross': round(a[1], 2), 'entitlement': round(a[2], 2)}
                     for (m,o,pl,day),a in sorted(groups.items())],
            'outlets': {o: {'tagged_count': a[0], 'tagged_gross': round(a[1],2),
                            'tagged_share': round(a[2],2), 'untagged_count': a[3],
                            'untagged_gross': round(a[4],2), 'untagged_share': round(a[5],2)}
                        for o,a in outlets.items()},
        }
    return result


def build_cache(raw_dir=RAW, cache_path=CACHE):
    """Update changed RAW periods atomically; retain untouched grouped periods."""
    files = sorted(raw_dir.glob('[0-9][0-9][0-9][0-9]-[0-9][0-9].json'))
    if not files:
        raise ValueError('No raw periods found')
    previous = {}
    if cache_path.exists():
        old = json.loads(cache_path.read_text(encoding='utf-8'))
        if old.get('version') == 1:
            previous = old.get('periods', {})
    periods = {}
    changed = []
    for path in files:
        item = previous.get(path.stem)
        if (item and item.get('source_mtime_ns') == path.stat().st_mtime_ns
                and item.get('source_size') == path.stat().st_size):
            periods[path.stem] = item
        else:
            changed.append(path)
    if not changed and len(periods) == len(previous):
        return {'version': 1, 'periods': periods}
    periods.update(aggregate(changed))
    doc = {'version': 1, 'periods': periods}
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.kemitraan_machine_', suffix='.json', dir=cache_path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(doc, f, ensure_ascii=False)
            f.flush(); os.fsync(f.fileno())
        with open(tmp, encoding='utf-8') as f:
            assert json.load(f)['version'] == 1
        os.replace(tmp, cache_path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)
    return doc


def read_cache(raw_dir=RAW, cache_path=CACHE):
    if not cache_path.exists():
        return None, ['Cache mesin belum dibuat; jalankan rebuild di pengaturan.']
    doc = json.loads(cache_path.read_text(encoding='utf-8'))
    stale = []
    files = {p.stem:p for p in raw_dir.glob('[0-9][0-9][0-9][0-9]-[0-9][0-9].json')}
    for month, path in files.items():
        entry = doc.get('periods', {}).get(month)
        if not entry or entry.get('source_mtime_ns') != path.stat().st_mtime_ns or entry.get('source_size') != path.stat().st_size:
            stale.append(month)
    return doc, sorted(stale)


def reconcile(doc, cache, month, rs_rows=()):
    """Entitlement only for explicitly assigned, priced machines, never transfers."""
    periods = {k:v for k,v in cache['periods'].items() if k <= month}
    ownership = defaultdict(list)
    for owner in doc.get('partners', []):
        for m in owner.get('machines', []):
            ownership[str(m.get('machine_id') or '').strip()].append(owner['id'])
    indexed = defaultdict(list)
    for period, data in periods.items():
        for row in data['rows']:
            if row['machine_id']: indexed[row['machine_id']].append(row)
    all_tagged_days = [row['day'] for rows in indexed.values() for row in rows]
    asof = max(all_tagged_days, default=None)
    first_tagged = min(all_tagged_days, default=None)
    owners = []
    assigned = set()
    for owner in doc.get('partners', []):
        machines = []
        for m in owner.get('machines', []):
            mid = str(m.get('machine_id') or '').strip()
            if not mid: continue
            rows = indexed.get(mid, [])
            conflict = len(ownership[mid]) != 1
            if not conflict: assigned.add(mid)
            amount = positive(m.get('amount'))
            bought = str(m.get('date') or '')
            valid = bool(amount and bought and not conflict)
            eligible = [r for r in rows if valid and r['day'] >= bought]
            entitlement = round(sum(r['entitlement'] for r in eligible),2)
            monthly = defaultdict(float)
            for r in eligible: monthly[r['day'][:7]] += r['entitlement']
            # Normalize the observed last 90 calendar days to 30 days. Include idle
            # days but never treat pre-rollout days as zero. Wait for a 14-day sample.
            run_rate = 0.0
            window_days = 0
            if valid and asof and first_tagged:
                start = max(first_tagged, bought, (date.fromisoformat(asof) - timedelta(days=89)).isoformat())
                window_days = max(0, (date.fromisoformat(asof) - date.fromisoformat(start)).days + 1)
                if window_days >= 14:
                    run_rate = sum(r['entitlement'] for r in eligible if r['day'] >= start) * 30 / window_days
            trail = defaultdict(lambda: {'first':'', 'last':'', 'gross':0., 'entitlement':0., 'transactions':0})
            for r in rows:
                key = (r['placement_id'], r['outlet'])
                a=trail[key]; a['first']=min(a['first'] or r['day'],r['day']); a['last']=max(a['last'],r['day'])
                a['gross']+=r['gross'];a['entitlement']+=r['entitlement'];a['transactions']+=r['transactions']
            machines.append({'machine_id':mid, 'amount':amount, 'date':bought,
                'entitlement':entitlement, 'gross':round(sum(r['gross'] for r in eligible),2),
                'remaining':max(amount-entitlement,0) if valid else None,
                'progress':entitlement/amount*100 if valid else None,
                'run_rate':round(run_rate,2), 'window_days':window_days,
                'months_to_payback':max(amount-entitlement,0)/run_rate if valid and window_days>=14 and run_rate>0 else None,
                'poor_sales':bool(valid and rows and window_days>=14 and run_rate < amount/12),
                'conflict':conflict, 'unpriced':not bool(amount and bought),
                'monthly':dict(monthly),
                'trail':[dict(placement_id=k[0],outlet=k[1],**v) for k,v in sorted(trail.items(), key=lambda x:x[1]['first'])]})
        owners.append({'id':owner['id'],'name':owner['name'],'machines':machines})
    unassigned = sorted(mid for mid in indexed if mid not in ownership)
    untagged = defaultdict(lambda: [0,0.,0.])
    raw_totals = defaultdict(lambda: [0.,0.,0.,0.,0.,0.])
    for period, data in periods.items():
        for outlet, a in data['outlets'].items():
            key=(period,outlet)
            raw_totals[key]=[a['tagged_gross'],a['tagged_share'],a['untagged_gross'],a['untagged_share'],a['tagged_count'],a['untagged_count']]
            u=untagged[period];u[0]+=a['untagged_count'];u[1]+=a['untagged_gross'];u[2]+=a['untagged_share']
    checks=[]
    for r in rs_rows:
        key=(str(r.get('periode')),str(r.get('outlet_name') or '').strip())
        if key not in raw_totals: continue
        a=raw_totals[key]
        delta_g=round(a[0]+a[2]-positive(r.get('total_revenue')),2)
        delta_s=round(a[1]+a[3]-positive(r.get('partner_amount')),2)
        if abs(delta_g)>1 or abs(delta_s)>1:
            checks.append({'period':key[0],'outlet':key[1],'gross_delta':delta_g,'share_delta':delta_s})
    return {'owners':owners, 'unassigned_ids':unassigned, 'untagged':dict(untagged),
            'reconciliation_differences':checks, 'covered_months':sorted(periods)}
