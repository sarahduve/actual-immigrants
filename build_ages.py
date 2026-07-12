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

per = collections.defaultdict(list)
with open('psam_p36.csv') as f:
    r = csv.reader(f)
    hdr = next(r)
    i = {c: hdr.index(c) for c in ('PUMA', 'AGEP', 'POBP', 'PWGTP', 'YOEP')}
    for row in r:
        if row[i['PUMA']] not in P20:
            continue
        c = CODE2C.get(row[i['POBP']].lstrip('0'))
        if not c:
            continue
        per[c].append((int(row[i['AGEP']]), int(row[i['PWGTP']]), row[i['YOEP']]))

def wmedian(pairs):
    s = sorted(pairs)
    tot = sum(w for _, w in s)
    acc = 0
    for v, w in s:
        acc += w
        if acc >= tot / 2:
            return v

ages = {}
for c, tr in per.items():
    if len(tr) < 60:
        continue
    med = wmedian([(a, w) for a, w, _ in tr])
    tot = sum(w for _, w, _ in tr)
    p65 = round(sum(w for a, w, _ in tr if a >= 65) / tot * 100)
    ent = [(int(y), w) for _, w, y in tr if y]
    ages[c] = [med, p65, wmedian(ent), len(tr)]
json.dump(ages, open('ages.json', 'w'), separators=(',', ':'))
md['ages'] = ages
open('map_data.json', 'w').write(json.dumps(md, separators=(',', ':')))
print('countries with age stats:', len(ages), 'of', len(MAPC))
for c in ['Italy', 'United Kingdom', 'Venezuela', 'Grenada', 'Sri Lanka']:
    print(' ', c, ages.get(c))
