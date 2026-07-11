"""Build compact major-roads layer from TIGER 2023 ROADS (primary S1100 + secondary S1200)."""
import io, json, zipfile
import shapefile
from shapely.geometry import LineString
from shapely.ops import linemerge, unary_union

lines = {'p': [], 's': [], 'l': []}   # primary, secondary, long local streets (the grid)
for c in ['005', '047', '061', '081', '085']:
    z = zipfile.ZipFile(f'roads_36{c}.zip')
    shp = io.BytesIO(z.read(f'tl_2023_36{c}_roads.shp'))
    dbf = io.BytesIO(z.read(f'tl_2023_36{c}_roads.dbf'))
    shx = io.BytesIO(z.read(f'tl_2023_36{c}_roads.shx'))
    r = shapefile.Reader(shp=shp, dbf=dbf, shx=shx)
    fields = [f[0] for f in r.fields[1:]]
    mi = fields.index('MTFCC')
    ni = fields.index('FULLNAME')
    # group local segments by street name so a boulevard chopped into blocks merges back together
    for sr in r.iterShapeRecords():
        m = sr.record[mi]
        if len(sr.shape.points) < 2:
            continue
        nm = sr.record[ni] or ''
        if m == 'S1100':
            lines['p'].append((c + '|' + nm, LineString(sr.shape.points)))
        elif m == 'S1200':
            lines['s'].append((c + '|' + nm, LineString(sr.shape.points)))
        elif m == 'S1400' and nm:
            lines['l'].append((c + '|' + nm, LineString(sr.shape.points)))

from collections import defaultdict
def merge_by_name(pairs, min_len, tol):
    byname = defaultdict(list)
    for name, g in pairs:
        byname[name].append(g)
    paths = []
    for name, gs in byname.items():
        u = unary_union(gs)
        merged = linemerge(u) if u.geom_type == 'MultiLineString' else u
        geoms = list(merged.geoms) if merged.geom_type == 'MultiLineString' else [merged]
        disp = name.split('|', 1)[1]
        for g in geoms:
            if g.length < min_len:
                continue
            g = g.simplify(tol)
            paths.append([disp, [[round(x, 5), round(y, 5)] for x, y in g.coords]])
    return paths

out = {}
out['p'] = merge_by_name(lines['p'], 0.0, 0.00025)
out['s'] = merge_by_name(lines['s'], 0.002, 0.00025)
out['l'] = merge_by_name(lines['l'], 0.02, 0.0004)
for k in out:
    print(k, len(lines[k]), 'segments ->', len(out[k]), 'polylines,', sum(len(p[1]) for p in out[k]), 'points')

s = json.dumps(out, separators=(',', ':'))
open('roads.json', 'w').write(s)
print('roads.json KB:', len(s) // 1024)
