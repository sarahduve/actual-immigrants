# Actual Immigrants

An interactive map of NYC neighborhoods by country of birth, inspired by [Mapgate](https://www.nbcnewyork.com/new-york-city/mamdani-to-add-more-neighborhoods-to-nyc-immigrant-enclave-list-after-perceived-snubs/6524448/).

Interactive map of where foreign-born New Yorkers live, built from ACS 2019–2023 place-of-birth
data. Five views: top birthplace, signature groups (location quotient, with statistical ties
declared when margins of error overlap), tract-level Mosaic (blended region colors), dot-density
Dots, and a by-country/region explorer — plus the city's "Immigrant Enclaves" list audited
against the data. Residual census write-in lines ("West Indies", "Other …") count toward totals
but never compete as countries; all "× citywide" multiples compare shares of all residents
(group share of the neighborhood vs group share of the city).

**Place of birth, not ancestry.** Unlike ancestry maps (e.g. the NYT's 2026 "American Mosaic"),
this counts only people actually born abroad. Ancestry is an identity claim that persists across
generations; place of birth is a biographical fact. The Mosaic view borrows the NYT blended-color
convention, applied to actual immigrants.

## Run it

Any static file server works (the page fetches `data/*.json` lazily for the tract Mosaic and the
full street grid):

```
python3 -m http.server 8742
# open http://localhost:8742/
```

### GitHub Pages

```
git remote add origin git@github.com:<you>/actual-immigrants.git
git push -u origin main
# repo Settings → Pages → deploy from branch `main`, root
```

`index.html` is fully self-contained except for the two lazy layers in `data/` (tract mosaic,
full streets), which degrade gracefully if absent — the single file also runs as a claude.ai
artifact without them.

## Files

| File | What |
|---|---|
| `index.html` | the map for GitHub Pages (data inlined; doctype/viewport head prepended) |
| `nyc-diaspora-map.template.html` | source template (`__DATA__` / `__ROADS__` placeholders) |
| `build_mapdata.py` | tract→NTA aggregation → `map_data.json` (needs `openpyxl`) |
| `build_roads.py` | TIGER major roads + names → `roads.json` (needs `pyshp`, `shapely`) |
| `build_tracts.py` | tract geometry + per-tract data → `data/tracts_topo.json`, `data/tract_pob.json` (needs `topojson`) |
| `build_streets_full.py` | full S1400 street grid → `data/streets_full.json` |
| `enclave_check.py` | audit of the 30 MOIA enclaves against ACS |
| `b05006/b01003/b04006/b05009_nyc_tracts.dat` | filtered Census FTP extracts (place of birth, population, ancestry, children by parents' nativity) |
| `tract_nta_xwalk.xlsx` | DCP 2020 tract→NTA crosswalk |

## Rebuilding

```
python3 build_mapdata.py
python3 build_roads.py          # needs roads_36*.zip (TIGER 2023 ROADS per county)
python3 build_tracts.py         # needs cb_tracts.zip (cartographic boundary tracts)
python3 build_streets_full.py
python3 - <<'EOF'
data = open('map_data.json').read()
roads = open('roads.json').read()
tpl = open('nyc-diaspora-map.template.html').read()
open('index.html','w').write(tpl.replace('__DATA__', data).replace('__ROADS__', roads))
EOF
```

## Data sources & method notes

- **Place of birth**: ACS 2019–2023 5-year, table B05006, census-tract level, pulled keylessly
  from the Census FTP table-based summary files
  (`www2.census.gov/programs-surveys/acs/summary_file/2023/table-based-SF/data/5YRData/`,
  one national pipe-delimited file per table, stream-filtered by GEO_ID). Same approach for
  B01003 (population), B04006 (ancestry), B05009 (children by parents' nativity).
- **Geography**: DCP 2020 NTAs (Socrata `9nt8-h7nd`), DCP tract→NTA crosswalk (`hm78-6dwm`),
  Census cartographic-boundary tracts, TIGER 2023 ROADS.
- B05006 is a nested hierarchy — rollup lines (ending `:`) excluded from country logic;
  UK constituents merged; "China" = mainland; "Other X"/"n.e.c." never count as a country.
- MOEs aggregated by root-sum-of-squares; reliability = CV (≤12% ok, 12–40% caution, >40% poor).
- "Signature" = location quotient (neighborhood share ÷ citywide share), min 400 people, CV ≤ 40.
- Mosaic blend: per-tract region weights over 8 world groups, blended in squared-RGB space;
  opacity scales with foreign-born share of the tract.
