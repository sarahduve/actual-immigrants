"""Cross-reference MOIA's 30 'immigrant enclaves' against ACS 2019-2023 tract data."""
import json, math
from collections import defaultdict
import openpyxl

# ---------- load B05006 (place of birth) ----------
meta = json.load(open('b05006_vars.json'))['variables']
lab05 = {k[len('B05006_'):-1]: v['label'].replace('Estimate!!Total:!!', '')
         for k, v in meta.items() if k.endswith('E') and k != 'B05006_001E'}
lname = lambda l: l.split('!!')[-1]
# name -> var numbers (leaf or rollup); merge UK/China variants like the map does
by_name = defaultdict(list)
for n, l in lab05.items():
    by_name[lname(l).rstrip(':')].append(n)

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
b04 = load_dat('b04006_nyc_tracts.dat')
def num(x):
    try:
        v = float(x); return v if v >= 0 else 0.0
    except (ValueError, TypeError):
        return 0.0

wb = openpyxl.load_workbook('tract_nta_xwalk.xlsx')
rows = list(wb['NYC_CT2020_Relate'].iter_rows(values_only=True)); hdr = rows[0]
gi, ni = hdr.index('GEOID'), hdr.index('NTACode')
tracts_of = defaultdict(list)
for r in rows[1:]:
    tracts_of[r[ni]].append(str(r[gi]))

CITY_POP = sum(num(d['B01003_E001']) for d in b01.values())

def measure(ntas, table, var_nums):
    """sum estimate & MOE over var_nums across tracts of the NTAs; also pop."""
    e = m2 = pop = 0.0
    for nta in ntas:
        for g in tracts_of[nta]:
            d = table.get(g, {})
            pref = 'B05006' if table is b05 else 'B04006'
            for vn in var_nums:
                e += num(d.get(f'{pref}_E{vn}'))
                m2 += num(d.get(f'{pref}_M{vn}'))**2
            pop += num(b01.get(g, {}).get('B01003_E001'))
    return e, math.sqrt(m2), pop

def city_total(table, var_nums):
    e = 0.0
    pref = 'B05006' if table is b05 else 'B04006'
    for d in table.values():
        for vn in var_nums:
            e += num(d.get(f'{pref}_E{vn}'))
    return e

def vnums(*names):
    out = []
    for n in names:
        assert n in by_name, n
        out += by_name[n]
    return out

# B04006 Palestinian / Arab lines
PAL = ['012']; ARAB_TOTAL = ['006']

ENCLAVES = [
    ("1. Chinatown in Flushing", ['QN0707', 'QN0705'], [('China', b05, vnums('China, excluding Hong Kong and Taiwan', 'Hong Kong', 'Taiwan'))]),
    ("2. Chinatown in Manhattan", ['MN0301'], [('China', b05, vnums('China, excluding Hong Kong and Taiwan', 'Hong Kong', 'Taiwan'))]),
    ("3. Chinatown in Sunset Park", ['BK0703', 'BK1201'], [('China', b05, vnums('China, excluding Hong Kong and Taiwan', 'Hong Kong', 'Taiwan'))]),
    ("4. Guyana Gateway (Crown Hts)", ['BK0802', 'BK0901'], [('Guyana', b05, vnums('Guyana'))]),
    ("5. Koreatown in Manhattan", ['MN0501', 'MN0502'], [('Korea', b05, vnums('Korea'))]),
    ("6. Koreatown in Queens (Flushing)", ['QN0707', 'QN0704'], [('Korea', b05, vnums('Korea'))]),
    ("7. Little Africa, SI (Clifton)", ['SI0102', 'SI0103'], [('Liberia', b05, vnums('Liberia')), ('W.Africa all', b05, vnums('Western Africa'))]),
    ("8. Little Africa, Bronx (167 St)", ['BX0402', 'BX0401'], [('W.Africa all', b05, vnums('Western Africa')), ('Ghana', b05, vnums('Ghana'))]),
    ("9. Little Albania (Fordham)", ['BX0503', 'BX0603', 'BX0701'], [('Albania', b05, vnums('Albania'))]),
    ("10. Little Bangladesh (Jamaica)", ['QN1201', 'QN0805'], [('Bangladesh', b05, vnums('Bangladesh'))]),
    ("11. Little Bhod-Tibet (Northern Blvd)", ['QN0203', 'QN0301'], [('Nepal', b05, vnums('Nepal')), ('Oth S.C.Asia (Bhutan)', b05, vnums('Other South Central Asia'))]),
    ("12. Little Caribbean (PLG/Church Av)", ['BK0902', 'BK1401'], [('Caribbean all', b05, vnums('Caribbean')), ('Jamaica', b05, vnums('Jamaica')), ('Haiti', b05, vnums('Haiti')), ('Trinidad&Tobago', b05, vnums('Trinidad and Tobago'))]),
    ("13. Little Colombia (Jackson Hts)", ['QN0301', 'QN0303'], [('Colombia', b05, vnums('Colombia'))]),
    ("14. Little Dominican Rep (Wash Hts)", ['MN1201', 'MN1202'], [('Dominican Rep.', b05, vnums('Dominican Republic'))]),
    ("15. Little Ecuador (Corona)", ['QN0303', 'QN0402'], [('Ecuador', b05, vnums('Ecuador'))]),
    ("16. Little Egypt (Steinway)", ['QN0101', 'QN0103'], [('Egypt', b05, vnums('Egypt'))]),
    ("17. Little Guyana, Queens", ['QN0903', 'QN0902', 'QN1002'], [('Guyana', b05, vnums('Guyana'))]),
    ("18. Little Guyana, Bronx (Nereid/StLawr)", ['BX1203', 'BX0901'], [('Guyana', b05, vnums('Guyana'))]),
    ("19. Little Haiti (Newkirk Av)", ['BK1401', 'BK1402'], [('Haiti', b05, vnums('Haiti'))]),
    ("20. Little India (Jackson Hts)", ['QN0301'], [('India', b05, vnums('India')), ('India+Bang+Pak+Nepal', b05, vnums('India', 'Bangladesh', 'Pakistan', 'Nepal'))]),
    ("21. Little Manila (Woodside)", ['QN0203', 'QN0301'], [('Philippines', b05, vnums('Philippines'))]),
    ("22. Little Mexico, Port Richmond", ['SI0106'], [('Mexico', b05, vnums('Mexico'))]),
    ("23. Little Mexico, Sunset Park", ['BK0702'], [('Mexico', b05, vnums('Mexico'))]),
    ("24. Little Odessa (Brighton Bch)", ['BK1303'], [('Ukraine', b05, vnums('Ukraine')), ('Ukraine+Russia+Belarus', b05, vnums('Ukraine', 'Russia', 'Belarus'))]),
    ("25. Little Palestine (Bay Ridge)", ['BK1001'], [('Palestinian ancestry', b04, PAL), ('Arab ancestry (all)', b04, ARAB_TOTAL), ('Born Jordan', b05, vnums('Jordan')), ('Born W.Asia all', b05, vnums('Western Asia'))]),
    ("26. Little Pakistan (Newkirk Plaza)", ['BK1402', 'BK1403', 'BK1203'], [('Pakistan', b05, vnums('Pakistan'))]),
    ("27. Little Poland (Greenpoint)", ['BK0101'], [('Poland', b05, vnums('Poland'))]),
    ("28. Little Senegal (116 St)", ['MN1001', 'MN0902'], [('Senegal', b05, vnums('Senegal')), ('W.Africa all', b05, vnums('Western Africa'))]),
    ("29. Little Ukraine (East Village)", ['MN0303'], [('Ukraine', b05, vnums('Ukraine'))]),
    ("30. Little Yemen (Bronx Park E)", ['BX1101', 'BX1104'], [('Yemen', b05, vnums('Yemen'))]),
]

city_cache = {}
for title, ntas, checks in ENCLAVES:
    print(f'\n{title}  [{", ".join(ntas)}]')
    for cname, table, vn in checks:
        key = (id(table), tuple(vn))
        if key not in city_cache:
            city_cache[key] = city_total(table, vn)
        ce = city_cache[key]
        e, moe, pop = measure(ntas, table, vn)
        if e == 0:
            print(f'   {cname:26s} 0')
            continue
        share = e / pop * 100
        cityshare = ce / CITY_POP * 100
        lq = share / cityshare if cityshare else 0
        cvv = (moe / 1.645) / e * 100
        pct_of_city = e / ce * 100 if ce else 0
        print(f'   {cname:26s} {e:8,.0f} ±{moe:6,.0f}  {share:5.1f}% of residents  LQ {lq:5.1f}  ({pct_of_city:4.1f}% of citywide {ce:,.0f})  CV {cvv:.0f}%')
