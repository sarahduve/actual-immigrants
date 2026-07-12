"""Per-country median age / share 65+ / median arrival for NYC, from ACS 2019-2023 PUMS.

Writes ages.json {country: [medAge, pct65, medArrival, n]} for countries in the map's list
with an unweighted sample of >= 60 people, and injects it as map_data.json['ages'].
PUMS is a different slice of the ACS than the B05006 tables: citywide only (PUMA floor),
counts won't reconcile exactly with the map's — we deliberately never display PUMS counts.
"""
import csv, json, collections

P20 = set(open('nyc_puma20.txt').read().split())
md = json.load(open('map_data.json'))
MAPC = set(md['countries'])

MANUAL = {
    'Myanmar': 'Burma (Myanmar)',
    'Czechoslovakia': 'Czechoslovakia (includes Czech Republic and Slovakia)',
    'Czech Republic': 'Czechoslovakia (includes Czech Republic and Slovakia)',
    'Slovakia': 'Czechoslovakia (includes Czech Republic and Slovakia)',
    'Macedonia': 'North Macedonia (Macedonia)',
    'England': 'United Kingdom', 'Scotland': 'United Kingdom',
    'Northern Ireland': 'United Kingdom', 'United Kingdom, Not Specified': 'United Kingdom',
    'Azores Islands': 'Portugal',
}
CODE2C = {}
for row in csv.reader(open('pums_dict.csv')):
    if len(row) >= 7 and row[0] == 'VAL' and row[1] == 'POBP':
        label = row[6]
        c = label if label in MAPC else MANUAL.get(label)
        if c:
            CODE2C[row[4].lstrip('0') or '0'] = c

per = collections.defaultdict(list)          # country -> [(age, w, yoep)]
per_puma = collections.defaultdict(list)     # (country, puma) -> [(age, w, yoep)]
with open('psam_p36.csv') as f:
    r = csv.reader(f)
    hdr = next(r)
    i = {c: hdr.index(c) for c in ('PUMA', 'AGEP', 'POBP', 'PWGTP', 'YOEP')}
    for row in r:
        puma = row[i['PUMA']]
        if puma not in P20:
            continue
        c = CODE2C.get(row[i['POBP']].lstrip('0'))
        if not c:
            continue
        rec = (int(row[i['AGEP']]), int(row[i['PWGTP']]), row[i['YOEP']])
        per[c].append(rec)
        per_puma[(c, puma)].append(rec)

def wmedian(pairs):
    s = sorted(pairs)
    tot = sum(w for _, w in s)
    acc = 0
    for v, w in s:
        acc += w
        if acc >= tot / 2:
            return v

def stats(tr, floor):
    if len(tr) < floor:
        return None
    med = wmedian([(a, w) for a, w, _ in tr])
    tot = sum(w for _, w, _ in tr)
    p65 = round(sum(w for a, w, _ in tr if a >= 65) / tot * 100)
    ent = [(int(y), w) for _, w, y in tr if y]
    return [med, p65, wmedian(ent), len(tr)]

city = {c: st for c, tr in per.items() if (st := stats(tr, 60))}

# ---- district (PUMA) layer: names, NTA->PUMA assignment, per-country-per-district stats ----
import io, zipfile
import shapefile
from shapely.geometry import shape as shp_shape, Point
z = zipfile.ZipFile('puma20_ny.zip')
rr = shapefile.Reader(shp=io.BytesIO(z.read('tl_2023_36_puma20.shp')),
                      dbf=io.BytesIO(z.read('tl_2023_36_puma20.dbf')),
                      shx=io.BytesIO(z.read('tl_2023_36_puma20.shx')))
fields = [f[0] for f in rr.fields[1:]]
ci2, ni2 = fields.index('PUMACE20'), fields.index('NAMELSAD20')
pcodes, pnames, pshapes = [], [], []
for sr in rr.iterShapeRecords():
    nm = sr.record[ni2]
    if not nm.startswith('NYC-'):
        continue
    pcodes.append(sr.record[ci2])
    pnames.append(nm.split('--', 1)[-1].replace(' PUMA', ''))   # "Bensonhurst & Bath Beach"
    pshapes.append(shp_shape(sr.shape.__geo_interface__))
PIDX = {c: k for k, c in enumerate(pcodes)}

tj = json.load(open('nta_topo.json'))
obj = list(tj['objects'].values())[0]
sx, sy = tj['transform']['scale']; tx, ty = tj['transform']['translate']
arcs = []
for arc in tj['arcs']:
    x = y = 0; pts = []
    for dx, dy in arc:
        x += dx; y += dy
        pts.append((x * sx + tx, y * sy + ty))
    arcs.append(pts)
nta2p = {}
for g in obj['geometries']:
    xs = ys = n = 0
    polys = [g['arcs']] if g['type'] == 'Polygon' else g['arcs']
    for poly in polys:
        for idx in poly[0]:
            for x, y in (arcs[idx] if idx >= 0 else arcs[~idx]):
                xs += x; ys += y; n += 1
    pt = Point(xs / n, ys / n)
    for k, shp in enumerate(pshapes):
        if shp.contains(pt):
            nta2p[g['properties']['nta']] = k
            break

puma_stats = collections.defaultdict(dict)   # country -> {pumaIdx: stats}
for (c, puma), tr in per_puma.items():
    st = stats(tr, 50)
    if st and c in city:
        puma_stats[c][PIDX[puma]] = st

ages = {'city': city, 'puma': dict(puma_stats), 'pnames': pnames, 'nta2p': nta2p}
json.dump(ages, open('ages.json', 'w'), separators=(',', ':'))
md['ages'] = ages
open('map_data.json', 'w').write(json.dumps(md, separators=(',', ':')))
ncells = sum(len(v) for v in puma_stats.values())
print('countries citywide:', len(city), '| district cells:', ncells, '| NTAs mapped:', len(nta2p))
for c in ['Italy', 'United Kingdom', 'Venezuela']:
    print(' ', c, city.get(c))
