"""Build compact map_data.json: topojson + per-NTA place-of-birth for the artifact."""
import json, math
from collections import defaultdict
import openpyxl

meta = json.load(open('b05006_vars.json'))['variables']
labels = {}
for k, v in meta.items():
    if not k.endswith('E') or k == 'B05006_001E':
        continue
    labels[k[len('B05006_'):-1]] = v['label'].replace('Estimate!!Total:!!', '')
leaves = {n: l for n, l in labels.items() if not l.endswith(':')}
MERGE = {'United Kingdom, excluding England and Scotland': 'United Kingdom',
         'England': 'United Kingdom', 'Scotland': 'United Kingdom',
         'China, excluding Hong Kong and Taiwan': 'China'}
def disp(lab):
    n = lab.split('!!')[-1]
    return MERGE.get(n, n)
def is_other(name):
    return name.startswith('Other ') or 'n.e.c.' in name or name == 'Born at sea'
leaf_country = {n: disp(l) for n, l in leaves.items()}

def load_dat(path):
    rows = {}
    with open(path) as f:
        header = f.readline().rstrip('\n').split('|')
        for line in f:
            parts = line.rstrip('\n').split('|')
            rows[parts[0][-11:]] = dict(zip(header[1:], parts[1:]))
    return rows
b05 = load_dat('b05006_nyc_tracts.dat')
b01 = load_dat('b01003_nyc_tracts.dat')
b09 = load_dat('b05009_nyc_tracts.dat')
# 2nd-gen children: US-born, living with >=1 foreign-born parent
KIDS2 = ['008', '011', '018', '026', '029', '036']

# region groups for the explorer: census rollup lines (+ two custom sums)
ROLLUPS = ['Caribbean', 'Central America', 'South America',
           'Eastern Asia', 'South Central Asia', 'South Eastern Asia', 'Western Asia',
           'Eastern Europe', 'Southern Europe', 'Western Europe', 'Northern Europe',
           'Western Africa', 'Eastern Africa', 'Northern Africa', 'Middle Africa', 'Oceania']
rollup_vars = {}
for n, l in labels.items():
    if l.endswith(':') and disp(l.rstrip(':')) in ROLLUPS:
        rollup_vars.setdefault(disp(l.rstrip(':')), []).append(n)
CUSTOM = {
    'Maghreb (NW Africa)': ['Algeria', 'Morocco', 'Other Northern Africa'],
    'Former USSR': ['Russia', 'Ukraine', 'Belarus', 'Moldova', 'Latvia', 'Lithuania',
                    'Armenia', 'Azerbaijan', 'Georgia', 'Kazakhstan', 'Uzbekistan'],
}
custom_vars = {g: [n for n, c in leaf_country.items() if c in members]
               for g, members in CUSTOM.items()}
REGION_LABELS = {'Central America': 'Central America (incl. Mexico)',
                 'Western Asia': 'Western Asia (Middle East)'}
REGIONS = ROLLUPS + list(CUSTOM)
def num(x):
    try:
        v = float(x); return v if v >= 0 else 0.0
    except (ValueError, TypeError):
        return 0.0

wb = openpyxl.load_workbook('tract_nta_xwalk.xlsx')
rows = list(wb['NYC_CT2020_Relate'].iter_rows(values_only=True))
hdr = rows[0]
ii = {c: hdr.index(c) for c in ('GEOID', 'NTACode', 'NTAName', 'NTAType', 'BoroName')}
xwalk, nta_info = {}, {}
for r in rows[1:]:
    xwalk[str(r[ii['GEOID']])] = r[ii['NTACode']]
    nta_info[r[ii['NTACode']]] = {'name': r[ii['NTAName']], 'boro': r[ii['BoroName']],
                                  'type': str(r[ii['NTAType']])}

agg = defaultdict(lambda: {'pop_e': 0.0, 'pop_m2': 0.0, 'fb_e': 0.0, 'fb_m2': 0.0,
                           'c_e': defaultdict(float), 'c_m2': defaultdict(float),
                           'r_e': defaultdict(float), 'r_m2': defaultdict(float),
                           'k2_e': 0.0, 'k2_m2': 0.0, 'kt_e': 0.0})
for geoid, d in b05.items():
    nta = xwalk[geoid]
    a = agg[nta]
    a['fb_e'] += num(d['B05006_E001']); a['fb_m2'] += num(d['B05006_M001'])**2
    p = b01.get(geoid, {})
    a['pop_e'] += num(p.get('B01003_E001')); a['pop_m2'] += num(p.get('B01003_M001'))**2
    for vn, c in leaf_country.items():
        e, m = num(d.get(f'B05006_E{vn}')), num(d.get(f'B05006_M{vn}'))
        if e or m:
            a['c_e'][c] += e; a['c_m2'][c] += m*m
    for g, vns in list(rollup_vars.items()) + list(custom_vars.items()):
        for vn in vns:
            e, m = num(d.get(f'B05006_E{vn}')), num(d.get(f'B05006_M{vn}'))
            if e or m:
                a['r_e'][g] += e; a['r_m2'][g] += m*m
    k = b09.get(geoid, {})
    for vn in KIDS2:
        a['k2_e'] += num(k.get(f'B05009_E{vn}')); a['k2_m2'] += num(k.get(f'B05009_M{vn}'))**2
    a['kt_e'] += num(k.get('B05009_E001'))

# all single countries (exclude "Other X" / n.e.c. lines), ordered by citywide total
tot = defaultdict(float)
for a in agg.values():
    for c, e in a['c_e'].items():
        if not is_other(c):
            tot[c] += e
top40 = [c for c, t in sorted(tot.items(), key=lambda x: -x[1]) if t > 0]

ntas = {}
for nta, a in agg.items():
    info = nta_info[nta]
    pop, fb = a['pop_e'], a['fb_e']
    # dominant across ALL single-country leaves
    singles = [(c, e) for c, e in a['c_e'].items() if not is_other(c) and e > 0]
    singles.sort(key=lambda x: -x[1])
    dom = singles[0] if singles else None
    dom_moe = math.sqrt(a['c_m2'][dom[0]]) if dom else 0
    vals = {}
    for idx, c in enumerate(top40):
        e = a['c_e'].get(c, 0)
        if e > 0:
            vals[idx] = [round(e), round(math.sqrt(a['c_m2'][c]))]
    rvals = {}
    for idx, g in enumerate(REGIONS):
        e = a['r_e'].get(g, 0)
        if e > 0:
            rvals[idx] = [round(e), round(math.sqrt(a['r_m2'][g]))]
    ntas[nta] = {
        'n': info['name'], 'b': info['boro'], 't': info['type'],
        'p': round(pop), 'f': round(fb), 'fm': round(math.sqrt(a['fb_m2'])),
        'd': dom[0] if dom else None,
        'de': round(dom[1]) if dom else 0,
        'dm': round(dom_moe),
        'v': vals,
        'rv': rvals,
        'k': [round(a['k2_e']), round(math.sqrt(a['k2_m2'])), round(a['kt_e'])],
    }

# world-group per country for the signature-mode coloring, derived from the label hierarchy
def world_group(label_path):
    if 'Caribbean' in label_path: return 0
    if 'Central America' in label_path or 'South America' in label_path: return 1
    if 'South Eastern Asia' in label_path: return 4   # before 'Eastern Asia' — substring collision
    if 'Eastern Asia' in label_path: return 2
    if 'South Central Asia' in label_path: return 3
    if 'Western Asia' in label_path or 'Northern Africa' in label_path: return 5
    if 'Africa' in label_path: return 6
    if 'Europe' in label_path: return 7
    return 8   # Northern America, Oceania, at-sea, historical
country_group = {}
for n, l in leaves.items():
    c = leaf_country[n]
    if c in top40:
        country_group.setdefault(c, world_group(l))

region_totals = {}
for idx, g in enumerate(REGIONS):
    region_totals[g] = round(sum(a['r_e'].get(g, 0) for a in agg.values()))

out = {
    'countries': top40,
    'totals': {c: round(tot[c]) for c in top40},
    'cgroup': [country_group.get(c, 8) for c in top40],
    'regions': [REGION_LABELS.get(g, g) for g in REGIONS],
    'rtotals': [region_totals[g] for g in REGIONS],
    'ntas': ntas,
    'topo': json.load(open('nta_topo.json')),
}
s = json.dumps(out, separators=(',', ':'))
open('map_data.json', 'w').write(s)
print('map_data.json KB:', len(s)//1024)
# how many NTAs have dominant country outside top40?
outside = [(k, v['d']) for k, v in ntas.items() if v['d'] and v['d'] not in top40]
print('dominant outside top40:', outside)
