import csv,json,itertools,statistics
from pathlib import Path
root=Path(__file__).resolve().parents[1]
rows=list(csv.DictReader((root/'data/processed/bookings_clean.csv').open()))
config={'month':'booking_month','channel':'booking_channel','type':'booking_type','status':'booking_status','route':'route'}
values={k:sorted({r[col] for r in rows}) for k,col in config.items()}
scenarios=[('All records',{})]
for k,vs in values.items():
    for v in vs: scenarios.append((f'{k}: {v}',{k:v}))
scenarios.extend([
    ('January app confirmed',{'month':'2025-01','channel':'IRCTC App','status':'Confirmed'}),
    ('December partners Premium Tatkal Delhi Mumbai',{'month':'2025-12','channel':'Authorised Partners','type':'Premium Tatkal','route':'Delhi - Mumbai'}),
    ('Cancelled reserved Delhi Howrah',{'status':'Cancelled','type':'Reserved','route':'Delhi - Howrah'}),
    ('Small-value single booking',{'month':'2025-05','channel':'IRCTC Website','type':'Tatkal','status':'Waitlisted (WL)','route':'Mumbai - Pune'}),
])
observed={tuple(r[col] for col in config.values()) for r in rows}
for combo in itertools.product(*values.values()):
    if combo not in observed:
        scenarios.append(('Empty intersection',dict(zip(config,combo))))
        break
out=[]
for name,filters in scenarios:
    selected=[r for r in rows if all(r[config[k]]==v for k,v in filters.items())]
    n=len(selected)
    invalid=sum(int(r['flag_invalid_chronology']) for r in selected)
    out.append({'name':name,'filters':filters,'expected':{
        'count':n,'value':sum(int(r['booking_value_inr']) for r in selected),
        'passengers':sum(int(r['passenger_count']) for r in selected),
        'users':len({r['user_id'] for r in selected}), 'trains':len({r['train_number'] for r in selected}),
        'invalid':invalid,'validLeadCount':n-invalid,
        'occupancy':statistics.mean(float(r['occupancy_percentage']) for r in selected) if n else None}})
(root/'tests/fixtures/dashboard_expected.json').write_text(json.dumps(out,indent=2))
print(f'{len(out)} independent CSV scenarios created')
