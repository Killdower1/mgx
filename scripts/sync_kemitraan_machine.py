"""Incremental machine sales cache sync, scheduled after hourly RAW/RS sync."""
from pathlib import Path
import json
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'nicegui_template'))
from services import kemitraan_machine as ledger


def main():
    _, stale = ledger.read_cache()
    if stale:
        doc = ledger.build_cache()
        print('Machine cache rebuilt:', ', '.join(stale))
    else:
        print('Machine cache unchanged')
        return
    rs = json.loads(ledger.RS.read_text(encoding='utf-8'))
    totals = ledger.reconcile({'partners': []}, doc, sorted(doc['periods'])[-1], rs)
    differences = totals['reconciliation_differences']
    if differences:
        raise RuntimeError('%d machine/RS outlet-month differences; first: %s' %
                           (len(differences), differences[0]))
    print('Reconciled with RS: no outlet-month differences')


if __name__ == '__main__':
    main()
