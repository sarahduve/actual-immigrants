"""Tract-level layer: simplified geometry + per-tract place-of-birth data for the Mosaic
and tract-resolution views."""
import io, json, math, zipfile
from collections import defaultdict
import shapefile, topojson
import openpyxl

NYC = {'005', '047', '061', '081', '085'}

# ---- geometry ----
z = zipfile.ZipFile('cb_tracts.zip')
r = shapefile.Reader(shp=io.BytesIO(z.read('cb_2023_36_tract_500k.shp')),
                     dbf=io.BytesIO(z.read('cb_2023_36_tract_500k.dbf')),
                     shx=io.BytesIO(z.read('cb_2023_36_tract_500k.shx')))
fields = [f[0] for f in r.fields[1:]]
gi, ci = fields.index('GEOID'), fields.index('COUNTYFP')
feats = []
for sr in r.iterShapeRecords():
    if sr.record[ci] not in NYC:
        continue
    feats.append({'type': 'Feature', 'properties': {'g': sr.record[gi]},
                  'geometry': sr.shape.__geo_interface__})
print('tract features:', len(feats))
fc = {'type': 'FeatureCollection', 'features': feats}
topo = topojson.Topology(fc, prequantize=1e5, toposimplify=0.00018, prevent_oversimplify=True)
s = json.dumps(json.loads(topo.to_json()), separators=(',', ':'))
open('tracts_topo.json', 'w').write(s)
print('tracts_topo.json KB:', len(s) // 1024)

# ---- data ----
meta = json.load(open('b05006_vars.json'))['variables']
labels = {k[len('B05006_'):-1]: v['label'].replace('Estimate!!Total:!!', '')
          for k, v in meta.items() if k.endswith('E') and k != 'B05006_001E'}
lname = lambda l: l.split('!!')[-1]
MERGE = {'United Kingdom, excluding England and Scotland': 'United Kingdom',
         'England': 'United Kingdom', 'Scotland': 'United Kingdom',
         'China, excluding Hong Kong and Taiwan': 'China',
         'Azores Islands': 'Portugal'}
disp = lambda l: MERGE.get(lname(l), lname(l))
def is_other(nm):
    return (nm.startswith('Other ') or 'n.e.c.' in nm or nm == 'Born at sea'
            or nm == 'West Indies')
leaves = {n: l for n, l in labels.items() if not l.endswith(':')}
leaf_country = {n: disp(l) for n, l in leaves.items()}

# 8 world groups from rollup lines (matches the map's GROUPS order)
GROUP_ROLLUPS = [
    ['Caribbean'],                                   # 0
    ['Central America', 'South America'],            # 1
    ['Eastern Asia'],                                # 2
    ['South Central Asia'],                          # 3
    ['South Eastern Asia'],                          # 4
    ['Western Asia', 'Northern Africa'],             # 5
    ['Western Africa', 'Eastern Africa', 'Middle Africa', 'Southern Africa'],  # 6
    ['Europe'],                                      # 7
]
rollup_vars = defaultdict(list)
for n, l in labels.items():
    if l.endswith(':'):
        rollup_vars[lname(l).rstrip(':')].append(n)
group_vars = [[vn for nm in names for vn in rollup_vars[nm]] for names in GROUP_ROLLUPS]

def load_dat(path):
    rows = {}
    with open(path) as f:
        h = f.readline().rstrip('\n').split('|')
        for line in f:
            p = line.rstrip('\n').split('|')
            rows[p[0][-11:]] = dict(zip(h[1:], p[1:]))
    return rows
b05 = load_dat('b05006_nyc_tracts.dat')
b01 = load_dat('b01003_nyc_tracts.dat')
def num(x):
    try:
        v = float(x); return v if v >= 0 else 0.0
    except (ValueError, TypeError):
        return 0.0

wb = openpyxl.load_workbook('tract_nta_xwalk.xlsx')
rows = list(wb['NYC_CT2020_Relate'].iter_rows(values_only=True)); hdr = rows[0]
xw = {str(r[hdr.index('GEOID')]): r[hdr.index('NTACode')] for r in rows[1:]}

countries = json.load(open('map_data.json'))['countries']
cidx = {c: i for i, c in enumerate(countries)}

tracts = {}
for geoid, d in b05.items():
    pop = num(b01.get(geoid, {}).get('B01003_E001'))
    fb = num(d['B05006_E001'])
    # dominant single country
    best = None
    for vn, c in leaf_country.items():
        if is_other(c):
            continue
        e = num(d.get(f'B05006_E{vn}'))
        if e > 0 and (best is None or e > best[1]):
            best = (c, e, num(d.get(f'B05006_M{vn}')))
    g8 = []
    for vns in group_vars:
        g8.append(round(sum(num(d.get(f'B05006_E{vn}')) for vn in vns)))
    tracts[geoid] = [round(pop), round(fb),
                     cidx.get(best[0], -1) if best else -1,
                     round(best[1]) if best else 0,
                     round(best[2]) if best else 0,
                     xw.get(geoid, '')] + g8
s = json.dumps({'tracts': tracts}, separators=(',', ':'))
open('tract_pob.json', 'w').write(s)
print('tract_pob.json KB:', len(s) // 1024)
