import json
import tempfile
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services import kemitraan_machine as k

def tx(day, mid, place, outlet, amount=100, share=40, status='done', payment='paid'):
    return dict(date=day,status=status,payment_status=payment,machine_id=mid,machine_placement_id=place,outlet_name=outlet,processed_gross_amount=amount,partner_share=share)

with tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp); raw=root/'raw';raw.mkdir();cache=root/'out.json'
    t=[tx('2026-10-28',None,None,'A',100),tx('2026-10-29','M1',11,'A',500),tx('2026-10-30','M1',11,'A',100),tx('2026-10-30','M2',12,'A',200),tx('2026-10-31','M1',11,'A',999,status='pending'),tx('2026-10-31','M1',11,'A',999,payment='unpaid')]
    (raw/'2026-10.json').write_text(json.dumps(t))
    (raw/'2026-11.json').write_text(json.dumps([tx('2026-11-01','M1',21,'B',300),tx('2026-11-02',None,None,'B',50)]))
    data=k.build_cache(raw,cache);loaded,stale=k.read_cache(raw,cache);assert not stale and loaded==data
    assert k.build_cache(raw,cache)==data  # unchanged rebuild is an exact no-op
    assert k.read_cache(raw,cache)[1]==[]
    doc={'partners':[{'id':'P1','name':'One','machines':[{'machine_id':'M1','amount':1000,'date':'2026-10-30'}]},{'id':'P2','name':'Two','machines':[]}]}
    rs=[]
    for period, d in data['periods'].items():
        for outlet,a in d['outlets'].items():rs.append(dict(periode=period,outlet_name=outlet,total_revenue=a['tagged_gross']+a['untagged_gross'],partner_amount=a['tagged_share']+a['untagged_share']))
    result=k.reconcile(doc,data,'2026-11',rs);m=result['owners'][0]['machines'][0]
    assert m['entitlement']==160 and m['gross']==400 and len(m['trail'])==2,m
    doc['partners'][0]['machines'][0]['date']=''
    incomplete=k.reconcile(doc,data,'2026-11',rs)['owners'][0]['machines'][0]
    assert incomplete['progress'] is None and incomplete['entitlement']==0 and incomplete['unpriced']
    doc['partners'][0]['machines'][0]['date']='2026-10-30'
    assert result['unassigned_ids']==['M2'] and sum(a[0] for a in result['untagged'].values())==2
    assert not result['reconciliation_differences']
    # A changed month refreshes only that month, preserving the old grouped month.
    old_oct=data['periods']['2026-10']
    november=json.loads((raw/'2026-11.json').read_text())
    november.append(tx('2026-11-03','M1',21,'B',50))
    (raw/'2026-11.json').write_text(json.dumps(november))
    updated=k.build_cache(raw,cache)
    assert updated['periods']['2026-10']==old_oct
    assert k.reconcile(doc,updated,'2026-11')['owners'][0]['machines'][0]['entitlement']==180
    data=updated
    rs=[dict(periode=period,outlet_name=outlet,
             total_revenue=a['tagged_gross']+a['untagged_gross'],
             partner_amount=a['tagged_share']+a['untagged_share'])
        for period, d in data['periods'].items() for outlet,a in d['outlets'].items()]
    rs[0]['partner_amount']+=5;assert len(k.reconcile(doc,data,'2026-11',rs)['reconciliation_differences'])==1
    doc['partners'][1]['machines']=[{'machine_id':'M1','amount':500,'date':'2026-10-30'}]
    assert k.reconcile(doc,data,'2026-11',rs)['owners'][0]['machines'][0]['conflict']
    (raw/'2026-11.json').write_text('[{"date":')
    try:k.build_cache(raw,cache)
    except ValueError:pass
    else:raise AssertionError('truncated raw accepted')
    assert k.read_cache(raw,cache)[0]==data
    assert k.read_cache(raw,cache)[1]==['2026-11']
with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    raw = root/'raw'
    raw.mkdir()
    rows = [tx('2026-11-%02d' % day, 'M1', 1, 'A') for day in range(1, 21)]
    (raw/'2026-11.json').write_text(json.dumps(rows))
    data = k.build_cache(raw, root/'out.json')
    doc = {'partners':[{'id':'P1','name':'One','machines':[{'machine_id':'M1','amount':20000,'date':'2026-11-01'}]}]}
    result = k.reconcile(doc,data,'2026-11')['owners'][0]['machines'][0]
    assert result['window_days']==20 and result['run_rate']==1200 and result['poor_sales']
    # An early partial month must not be classified as weak sales.
    early = k.reconcile(doc,data,'2026-10')['owners'][0]['machines'][0]
    assert early['window_days']==0 and not early['poor_sales']
print('synthetic: move, multiple machines/outlet, untagged, paid/done, price/date, conflict, RS mismatch, atomic failure, freshness, 30-day normalized pace OK')
