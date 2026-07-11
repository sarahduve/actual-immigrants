"""Full local street network (TIGER S1400), lazy-loaded by the repo version at deep zoom."""
import io, json, zipfile
import shapefile

paths = []
for c in ['005', '047', '061', '081', '085']:
    z = zipfile.ZipFile(f'roads_36{c}.zip')
    r = shapefile.Reader(shp=io.BytesIO(z.read(f'tl_2023_36{c}_roads.shp')),
                         dbf=io.BytesIO(z.read(f'tl_2023_36{c}_roads.dbf')),
                         shx=io.BytesIO(z.read(f'tl_2023_36{c}_roads.shx')))
    fields = [f[0] for f in r.fields[1:]]
    mi = fields.index('MTFCC')
    for sr in r.iterShapeRecords():
        if sr.record[mi] != 'S1400' or len(sr.shape.points) < 2:
            continue
        pts = sr.shape.points
        # decimate: keep every other vertex on long segments, always endpoints
        keep = [pts[0]] + pts[1:-1:2] + [pts[-1]] if len(pts) > 3 else pts
        paths.append([[round(x, 4), round(y, 4)] for x, y in keep])
s = json.dumps(paths, separators=(',', ':'))
open('streets_full.json', 'w').write(s)
print('segments:', len(paths), 'KB:', len(s) // 1024)
