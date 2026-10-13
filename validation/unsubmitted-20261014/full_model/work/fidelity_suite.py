from full_tests import *
def compare(a,b):
    rows=[]
    if len(a['snapshots'])!=len(b['snapshots']):raise RuntimeError('Snapshot count mismatch')
    for sa,sb in zip(a['snapshots'],b['snapshots']):
        for fa,fb in zip(sa['fields'],sb['fields']):
            rows.append(dict(weather=sa['weather_start'],field=fa['name'],count=fa['count'],identical=fa['sha256']==fb['sha256']))
    same_outputs=a['payloads']==b['payloads']
    same_steps=all((ra['itime'],ra['dt'],ra['realtime'],ra['tlimit'])==(rb['itime'],rb['dt'],rb['realtime'],rb['tlimit']) for ra,rb in zip(a['integration'],b['integration']))
    return dict(status='pass' if all(r['identical'] for r in rows) and same_outputs and same_steps else 'fail',fields=rows,payloads_identical=same_outputs,steps_identical=same_steps)
