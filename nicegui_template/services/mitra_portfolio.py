"""Mitra-level investment and revenue reconciliation; never infer physical machines."""
from __future__ import annotations

import json
import os
import re
import tempfile
from collections import defaultdict
from datetime import date
from pathlib import Path

PATH = Path(__file__).resolve().parents[2] / 'streamlit_template/data/mitra_portfolio.json'
LEGACY = PATH.with_name('mitra_units.json')


def key(value):
    return re.sub(r'[^a-z0-9]+', ' ', str(value or '').strip().lower()).strip()


def money(value):
    try:
        v = float(value or 0)
        return v if 0 <= v < 1e15 else 0.0
    except (TypeError, ValueError):
        return 0.0


def new_doc():
    return {'version': 1, 'partners': []}


def load():
    if PATH.exists():
        return json.loads(PATH.read_text(encoding='utf-8'))
    return seed()


def seed():
    """Legacy is candidate-only: guessed machine prices/placements are NOT confirmed input."""
    doc = new_doc()
    if not LEGACY.exists():
        return doc
    old = json.loads(LEGACY.read_text(encoding='utf-8'))
    for owner in old.get('partners', []):
        found = {}
        for machine in owner.get('machines', []):
            for pl in machine.get('placements', []):
                name = str(pl.get('outlet') or '').strip()
                if name:
                    found[key(name)] = name
        for name in owner.get('no_tx', []):
            if key(name):
                found[key(name)] = name
        aliases = list(owner.get('aliases') or [])
        if key(owner.get('name')) == key('Widi Official') and not any(key(a) == 'wijaya' for a in aliases):
            aliases.append('Wijaya')
        doc['partners'].append({'id': owner['id'], 'name': owner.get('name', ''),
                                'aliases': aliases, 'investments': [],
                                'outlets': [{'name': n, 'state': 'candidate'} for n in sorted(found.values())]})
    return doc


def save(doc):
    PATH.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix='.mitra_portfolio_', suffix='.json', dir=PATH.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as out:
            json.dump(doc, out, ensure_ascii=False, indent=2)
        os.replace(temp, PATH)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def next_id(rows, prefix):
    used = {r.get('id') for r in rows}
    n = 1
    while f'{prefix}-{n:02d}' in used:
        n += 1
    return f'{prefix}-{n:02d}'


def validate_investment(amount, purchase_date):
    if money(amount) <= 0:
        raise ValueError('Modal harus lebih besar dari nol')
    try:
        date.fromisoformat(purchase_date)
    except (ValueError, TypeError):
        raise ValueError('Tanggal beli harus YYYY-MM-DD yang valid') from None


def reconcile(doc, rs, month):
    """One ledger row belongs to at most one confirmed owner. No double counting."""
    all_rows = defaultdict(list)
    for r in rs:
        p = str(r.get('periode') or '')
        k = key(r.get('outlet_name'))
        if k and p <= month:
            all_rows[k].append(r)
    ownership = defaultdict(list)
    for owner in doc['partners']:
        for outlet in owner.get('outlets', []):
            if outlet.get('state') == 'confirmed':
                ownership[key(outlet.get('name'))].append(owner['id'])
    summaries = []
    for owner in doc['partners']:
        entries = [x for x in owner.get('investments', []) if x.get('date', '')[:7] <= month]
        capital = sum(money(x.get('amount')) for x in entries)
        first = min((x['date'][:7] for x in entries), default=None)
        current, returned, pending, conflicts = 0.0, 0.0, 0.0, 0
        breakdown = []
        for outlet in owner.get('outlets', []):
            k = key(outlet.get('name'))
            period_rows = all_rows.get(k, [])
            # Only actual owner share; never gross revenue or master contract percent.
            observed = sum(money(r.get('partner_amount')) for r in period_rows)
            rows = [r for r in period_rows if first and first <= r['periode'] <= month]
            amount = sum(money(r.get('partner_amount')) for r in rows)
            now = sum(money(r.get('partner_amount')) for r in rows if r['periode'] == month)
            state = outlet.get('state', 'candidate')
            conflict = len(set(ownership.get(k, []))) > 1
            if state == 'confirmed' and not conflict:
                returned += amount
                current += now
            elif state == 'candidate':
                pending += amount if first else observed
            elif conflict:
                conflicts += 1
            breakdown.append({'outlet': outlet['name'], 'state': state,
                              'first': min((r['periode'] for r in period_rows), default='—'),
                              'last': max((r['periode'] for r in period_rows), default='—'),
                              'returned': amount, 'observed': observed,
                              'current': now, 'conflict': conflict})
        summaries.append({'id': owner['id'], 'name': owner['name'], 'aliases': owner.get('aliases', []),
                          'capital': capital, 'entries': len(entries), 'first': first,
                          'returned': returned, 'current': current, 'pending': pending,
                          'remaining': max(capital - returned, 0) if capital else None,
                          'progress': returned / capital * 100 if capital else None,
                          'outlets': breakdown, 'conflicts': conflicts})
    return summaries
