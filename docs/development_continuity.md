# Engineering App Development Continuity

Last updated: 2026-04-12 02:00 CDT

Purpose:
Keep a durable restart point so work can resume quickly after disconnects or session loss.

## Current project location
- `/Users/stephentroxel/Documents/projects/engineering_app`

## Current verified app URL
- `http://127.0.0.1:8597`
- Verified HTTP status: 200 OK
- Browser snapshot loaded the Dashboard and Steam Jets sections successfully with no browser console errors
- Steam Jets > Workbook family import rendered the new family / motive-basis filter cleanly during browser verification

## Current repo status
- Expect tracked edits in:
  - `README.md`
  - `core/curves.py`
  - `io/normalizers.py`
  - `web_app.py`
  - `docs/development_continuity.md`
- Untracked paths may still exist under:
  - `data/`
- If resuming, inspect `git status --short` first because local data artifacts and later commits may have changed the tree again

## Major completed feature tranches
1. Fresh `engineering_app` created in Documents/projects and initialized as a git repo
2. Streamlit browser shell added
3. Core engineering modules expanded with per-input units
4. Steam jets / thermo-compressor curve comparison added
5. Workbook upload + inspection UI added
6. Case manager UI added
7. Citric BPE tool added using workbook table through 60 DS and provisional >60 DS estimate
8. Solution BPE expanded to fructose, dextrose, and sucrose
9. Hydraulics expanded with:
   - schedule 10S stainless presets from 1/2 in to 12 in
   - fitting and valve K-value counts
   - TDH / pressure drop / residence time / line volume
   - size comparison and line-size recommendation
   - pump power
   - NPSHa screen
   - segmented system breakdown
   - parallel branch balancing screen
   - balancing-device Cv/Kv and equivalent-orifice sizing from entered split checks
   - vessel/static-head screen
   - control valve Cv/Kv sizing
   - cavitation/flashing screening
   - pump/system curve overlay
   - built-in and uploaded pump-curve matching against system curves
   - pump rerate / affinity screening from speed or impeller changes with relative power and NPSHr factors
   - suction-vessel-to-pump NPSHa scenario with optional NPSHr margin screening
10. Hydraulics runtime bugs fixed:
   - local pandas shadowing bug on hydraulics page
   - missing `volumetric_flow_to_m3_h` import
   - missing `length_to_m` import
   - repaired corrupted `analyze_parallel_branches` self-balancing solver path
11. Steam jets expanded with:
   - workbook/CSV-driven model-family import
   - grouped curve-library building from tabular vendor data
   - side-by-side operating-point comparison across imported models
   - workbook-preview auto-normalization for vendor-style curve tables
   - family / motive-basis filtering for imported curve libraries
12. Crystallizers expanded with:
   - citric mother-liquor solids auto-filled from published solubility-vs-temperature data
   - crystal-volume-percent slurry basis for citric crystallizers
   - supersaturation / metastable-band screening from feed solids versus equilibrium mother-liquor solids
   - solids-above-equilibrium, supersaturation-ratio, and relative-supersaturation metrics
   - residence-time suppression when no crystallization is predicted at the chosen temperature/DS basis
13. Evaporators expanded with:
   - design-calibrated U·A·ΔT capacity mode for installed bodies
   - required area vs installed area screening
   - achievable evaporation / concentration estimates from installed capacity
14. Quick Tools expanded with:
   - blend tools
   - Brix reconciliation
   - tank inventory helpers
   - steam/electric utility cost screens
   - current-vs-proposed savings delta screens
   - ratio-target blend solver
15. Dashboard and roadmap now show active work and completed items with strike-through formatting in-app

## Files most relevant now
- `web_app.py`
- `io/normalizers.py`
- `core/curves.py`
- `core/hydraulics.py`
- `core/steam.py`
- `core/quicktools.py`
- `core/crystallizers.py`
- `README.md`
- `docs/development_continuity.md`

## Current user preferences / constraints
- Keep improving the app without stopping to ask
- Keep notes so work can restart easily after disconnects
- Selectable measurement units should exist on every input and output
- Manual BPE is not wanted
- User especially cares about high-DS citric behavior and practical hydraulic/system tools
- Prefer practical plant calculators before design-grade rigor

## Current active work focus
1. Hydraulics refinement
   - extend the newer suction-vessel / NPSHa scenarios into broader pump troubleshooting workflows
   - keep emphasis on practical plant line studies rather than academic hydraulics detail
2. Steam jets
   - extend workbook auto-normalization with vendor-specific sheet presets, larger preview windows if needed, and richer basis metadata display/export
   - preserve clear warnings that these are screening curves until confirmed against vendor performance data
3. Evaporators / solution properties
   - the next best non-steam-jet gap is still calibrated evaporator refinement or stronger >60 DS citric screening

## Next high-value work items
1. Hydraulics
   - add broader suction/discharge troubleshooting workflows built around the existing NPSHa and system-curve tools
2. Steam jets
   - add vendor-specific workbook presets / mapping aids on top of the new preview normalizer
3. Solution BPE
   - refine >60 DS citric estimation with stronger literature-backed correlation or clearly segmented screening bands
4. Evaporators
   - refine calibrated mode with fouling / non-condensable allowances or body-by-body staging

## Known cautions
- The app has had repeated runtime regressions from missing imports or partial edits after feature additions. After edits, always run:
  - compile check
  - direct Python import check
  - focused runtime check for the edited calculator path
  - live HTTP/browser check
- Steam-jet workbook auto-normalization is preview-based and only sees sampled rows; treat it as a screening aid for faster mapping, not a final vendor parser
- Citric >60 DS estimate is still a screening model and should stay labeled accordingly
- Parallel branch and vessel tools are first-pass engineering screens, not final design calculations
- Crystallizer supersaturation bands are user-entered screening thresholds, not validated metastable-zone property data

## Resume checklist after disconnect
1. `cd /Users/stephentroxel/Documents/projects/engineering_app`
2. `git status --short`
3. Read this file first
4. Read `README.md`
5. Run compile check:
   `python3 -m py_compile $(find /Users/stephentroxel/Documents/projects/engineering_app -name '*.py' | tr '\n' ' ')`
6. Run import + focused steam-jet normalization smoke test:
   `cd /Users/stephentroxel/Documents/projects && PYTHONPATH=. /usr/bin/python3 - <<'PY'
import engineering_app.web_app
from engineering_app.io.normalizers import normalize_curve_workbook
inspection = {
    'sheet_previews': [
        {
            'sheet_name': 'Vendor Curves',
            'sample_rows': [
                ['Model', 'Motive Steam Pressure', 'Suction Load', 'Motive Steam Consumption'],
                ['TC-A', 3.5, 2000, 3200],
                ['TC-A', 3.5, 4000, 5000],
                ['TC-B', 3.5, 2000, 3000],
                ['TC-B', 3.5, 4000, 4700],
                ['TC-C', 5.0, 2000, 2800],
                ['TC-C', 5.0, 4000, 4450],
            ],
        }
    ]
}
library = normalize_curve_workbook(inspection)
print('import ok', len(library.curves), sorted({curve.family for curve in library.curves}))
PY`
7. Launch a fresh Streamlit instance on a new unused port and verify with browser tools or `curl -I`
8. Continue the active work focus instead of rediscovering completed work
