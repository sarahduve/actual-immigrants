"""Shoreline-clip the NTA and tract topologies: subtract TIGER AREAWATER so dot-density
sampling (and the rendered shapes) stop extending into rivers and bays.

Waterfront tracts/NTAs legitimately extend to mid-channel in the source geography
(census boundaries run down the middle of the East River); nothing upstream ever clipped
them. Rewrites tracts_topo.json and the 'topo' key inside map_data.json.
"""
import io, json, zipfile
import shapefile, topojson
from shapely.geometry import Polygon, MultiPolygon, shape as shp_shape
from shapely.ops import unary_union
from shapely.prepared import prep

# ---- water union ----
water_polys = []
for c in ['005', '047', '061', '081', '085']:
    z = zipfile.ZipFile(f'areawater_36{c}.zip')
    base = f'tl_2023_36{c}_areawater'
    r = shapefile.Reader(shp=io.BytesIO(z.read(base + '.shp')),
                         dbf=io.BytesIO(z.read(base + '.dbf')),
                         shx=io.BytesIO(z.read(base + '.shx')))
    for sr in r.iterShapes():
        g = shp_shape(sr.__geo_interface__)
        if not g.is_valid:
            g = g.buffer(0)
        water_polys.append(g)
water = unary_union(water_polys)
# light simplify keeps the added coastline vertices under control without visible drift;
# the small outward buffer welds hairline gaps along county seams (AREAWATER is per-county
# and the seam runs mid-channel) and trims ~12m of shoreline, invisible at map scale
water = water.simplify(0.00008, preserve_topology=True).buffer(0.00012)
pwater = prep(water)
print('water union ready:', water.geom_type)

def decode(path, prop):
    tj = json.load(open(path))
    obj = list(tj['objects'].values())[0]
    sx, sy = tj['transform']['scale']; tx, ty = tj['transform']['translate']
    arcs = []
    for arc in tj['arcs']:
        x = y = 0; pts = []
        for dx, dy in arc:
            x += dx; y += dy
            pts.append((x * sx + tx, y * sy + ty))
        arcs.append(pts)
    def ring(idxs):
        pts = []
        for i in idxs:
            a = arcs[i] if i >= 0 else list(reversed(arcs[~i]))
            pts += a[1:] if pts else a
        return pts
    out = {}
    for g in obj['geometries']:
        polys = [g['arcs']] if g['type'] == 'Polygon' else g['arcs']
        shells = []
        for poly in polys:
            rings = [ring(r) for r in poly]
            rings = [r for r in rings if len(r) >= 4]
            if not rings:
                continue
            shells.append(Polygon(rings[0], rings[1:]))
        geom = MultiPolygon(shells) if len(shells) > 1 else shells[0]
        if not geom.is_valid:
            geom = geom.buffer(0)
        out[g['properties'][prop]] = geom
    return out

fcb = json.load(open('nybb.geojson'))
BOROS = {}
for f in fcb['features']:
    from shapely.geometry import shape as _shape
    BOROS[f['properties']['boroname']] = _shape(f['geometry']).buffer(0)

def drop_orphan_piers(gid, geom, own_boro):
    if geom.geom_type != 'MultiPolygon':
        return geom
    parts = sorted(geom.geoms, key=lambda g: g.area, reverse=True)
    main, keep = parts[0], [parts[0]]
    total = geom.area
    for part in parts[1:]:
        if part.area > total * 0.02 or part.distance(main) < 0.003:
            keep.append(part); continue
        other = any(part.distance(bg) < 0.0006 for b, bg in BOROS.items() if b != own_boro)
        if other:
            print(f'  dropped pier fragment from {gid}')
        else:
            keep.append(part)
    return MultiPolygon(keep) if len(keep) > 1 else keep[0]

def clip_and_encode(geoms, prop, simplify_tol, boro_of=None):
    feats = []
    n_clipped = 0
    for gid, geom in geoms.items():
        if pwater.intersects(geom):
            clipped = geom.difference(water)
            if not clipped.is_empty and clipped.area > geom.area * 0.02:
                geom = clipped.buffer(0)
                n_clipped += 1
            else:   # an (almost) all-water shape — keep original rather than vanish it
                print('  guard kept:', gid)
        if boro_of:
            geom = drop_orphan_piers(gid, geom, boro_of(gid))
        feats.append({'type': 'Feature', 'properties': {prop: gid},
                      'geometry': geom.__geo_interface__})
    print(f'  clipped {n_clipped} of {len(feats)} shapes')
    topo = topojson.Topology({'type': 'FeatureCollection', 'features': feats},
                             prequantize=1e5, toposimplify=simplify_tol,
                             prevent_oversimplify=True)
    return json.dumps(json.loads(topo.to_json()), separators=(',', ':'))

print('tracts...')
tract_geoms = decode('tracts_topo.json.prewater', 'g')
CO2B = {'005': 'Bronx', '047': 'Brooklyn', '061': 'Manhattan', '081': 'Queens', '085': 'Staten Island'}
s = clip_and_encode(tract_geoms, 'g', 0.00018, boro_of=lambda g: CO2B[g[2:5]])
open('tracts_topo.json', 'w').write(s)
print('  tracts_topo.json KB:', len(s) // 1024)

print('NTAs...')
nta_geoms = decode('nta_topo.json.prewater', 'nta')
B2B = {'MN': 'Manhattan', 'BK': 'Brooklyn', 'QN': 'Queens', 'BX': 'Bronx', 'SI': 'Staten Island'}
s = clip_and_encode(nta_geoms, 'nta', 0.00006, boro_of=lambda g: B2B.get(g[:2], ''))
open('nta_topo.json', 'w').write(s)
print('  nta_topo.json KB:', len(s) // 1024)

md = json.load(open('map_data.json'))
md['topo'] = json.loads(s)
s2 = json.dumps(md, separators=(',', ':'))
open('map_data.json', 'w').write(s2)
print('map_data.json KB:', len(s2) // 1024)

# ---- post-pass: orphan pier fragments ----
# The NY County line runs to the Brooklyn low-water mark, so after water removal a
# Manhattan NTA keeps pier slivers glued to the Brooklyn shore. Drop a fragment iff it is
# tiny (<2% of its shape), far from its shape's main body (>~300m), and hugging another
# borough's land (<~60m) — which keeps Roosevelt Island (near main), Marble Hill (9% of
# its NTA), and Liberty/Ellis (near no other borough).
