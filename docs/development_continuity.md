# Engineering App Development Continuity

Last updated: 2026-04-12 09:30 CDT

Purpose:
Keep a durable restart point so work can resume quickly after disconnects or session loss.

## Current project location
- `/Users/stephentroxel/Documents/projects/engineering_app`

## Current verified app URL
- `http://127.0.0.1:8612`
- Verified HTTP status: 200 OK
- Browser snapshot loaded the Dashboard and Hydraulics sections successfully with no browser console errors
- Hydraulics > Pump & NPSHa rendered the pump field troubleshooting section plus the new baseline-comparison / curve-diagnosis controls during browser verification

## Current repo status
- Expect tracked edits in:
  - `README.md`
  - `core/hydraulics.py`
  - `core/pump_curves.py`
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
   - pump field baseline comparison and curve diagnosis workflow
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
12. Pump hydraulics BEP proximity & instrument bias added:
    - BEP estimation from curve using 85% shutoff head heuristic
    - BEP proximity assessment with flow/head offsets, preferred zone check, reliability risk flags
    - Instrument bias screen: whether standard gauge accuracy (2%-5%) could explain flow/head deviations
    - UI under Hydraulics > Pump & NPSHa with checkbox toggle, built-in/manual curve entry
13. Evaporator fouling/NCG allowance screening added:
    - Fouling degradation via series-resistance model (clean vs dirty U)
    - NCG partial-pressure dilution lowering effective condensing temperature
    - Combined capacity penalty with U-degradation and delta-T penalty breakdown
    - Engineering notes when degradation exceeds 25% and 50% thresholds
    - UI under Steam > Evaporator
14. Steam jets with multi-effect evaporator staging added:
    - Multi-effect evaporator screening with per-effect BPE, ΔT distribution, and steam economy
    - Effect-by-effect temperature and solids profile plots
    - Vendor presets for steam-jet workbook import (Croll-Reynolds, Graham, Schutte & Koerting, GEA)
    - Auto-detection of vendor format from sheet name and column headers
15. Citric crystallizers expanded with:
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
16. Hydraulics expanded with a pump field troubleshooting check that converts suction/discharge gauge readings into developed head, hydraulic/brake power, vapor-pressure margin, and expected-TDH comparison
17. Hydraulics expanded again with:
   - current-vs-baseline field case comparison using measured flow/head/power/suction-margin deltas
   - measured-point mismatch diagnosis against a selected pump curve at the measured flow
   - dashboard/roadmap refresh to move the next hydraulics gap to BEP proximity / instrument-bias screening

## Files most relevant now
- `web_app.py`
- `core/hydraulics.py`
- `core/pump_curves.py`
- `io/normalizers.py`
- `core/curves.py`
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
1. Evaporators
   - fouling/NCG allowance screening landed
   - next: body-by-body staging or workbook-derived calibration inputs
2. Steam jets
   - extend workbook auto-normalization with vendor-specific sheet presets and richer basis metadata
3. Citric crystallizer
   - multi-body capacity screening with feed/withdrawal balance
4. Solution BPE
   - refine >60 DS citric estimation

## Next high-value work items
1. Evaporators: body-by-body staging or workbook-derived calibration inputs
2. Steam jets: vendor-specific workbook presets / mapping aids on top of the preview normalizer
3. Citric crystallizer: multi-body crystallizer capacity screening with explicit feed/withdrawal balance
4. Solution BPE: refine >60 DS citric estimation with stronger literature-backed correlation

## Known cautions
- The app has had repeated runtime regressions from missing imports or partial edits after feature additions. After edits, always run:
  - compile check
  - direct Python import check
  - focused runtime check for the edited calculator path
  - live HTTP/browser check
- Steam-jet workbook auto-normalization is preview-based and only sees sampled rows; treat it as a screening aid for faster mapping, not a final vendor parser
- Citric >60 DS estimate is still a screening model and should stay labeled accordingly
- Parallel branch, vessel, pump field comparison, and measured-vs-curve troubleshooting tools are first-pass engineering screens, not final design calculations
- Crystallizer supersaturation bands are user-entered screening thresholds, not validated metastable-zone property data

## Resume checklist after disconnect
1. `cd /Users/stephentroxel/Documents/projects/engineering_app`
2. `git status --short`
3. Read this file first
4. Read `README.md`
5. Run compile check:
   `python3 -m py_compile $(find /Users/stephentroxel/Documents/projects/engineering_app -name '*.py' | tr '\n' ' ')`
6. Run import + focused pump-field comparison smoke test:
   `cd /Users/stephentroxel/Documents/projects && PYTHONPATH=. /usr/bin/python3 - <<'PY'
import engineering_app.web_app
from engineering_app.core.hydraulics import analyze_pump_field_check, compare_pump_field_cases
from engineering_app.core.pump_curves import compare_measured_point_to_curve, get_builtin_curve
baseline = analyze_pump_field_check(
    flow_m3_h=95.0,
    density_kg_m3=998.0,
    suction_pressure_value=8.0,
    suction_pressure_unit='psig',
    discharge_pressure_value=34.0,
    discharge_pressure_unit='psig',
    suction_pipe_id_mm=77.9,
    discharge_pipe_id_mm=77.9,
    suction_gauge_elevation_m=0.0,
    discharge_gauge_elevation_m=1.0,
    pump_efficiency_fraction=0.74,
    expected_system_head_m=20.0,
    liquid_temperature_c=30.0,
)
current = analyze_pump_field_check(
    flow_m3_h=88.0,
    density_kg_m3=998.0,
    suction_pressure_value=4.5,
    suction_pressure_unit='psig',
    discharge_pressure_value=30.0,
    discharge_pressure_unit='psig',
    suction_pipe_id_mm=77.9,
    discharge_pipe_id_mm=77.9,
    suction_gauge_elevation_m=0.0,
    discharge_gauge_elevation_m=1.0,
    pump_efficiency_fraction=0.70,
    expected_system_head_m=20.0,
    liquid_temperature_c=30.0,
)
comparison = compare_pump_field_cases(95.0, baseline, 88.0, current)
curve_diag = compare_measured_point_to_curve(get_builtin_curve('ansi_50hz_full'), 88.0, current.developed_head_m)
print('import ok', round(current.developed_head_m, 3), round(comparison.developed_head_delta_m, 3), curve_diag.status)
PY`
7. Launch a fresh Streamlit instance on a new unused port and verify with browser tools or `curl -I`
8. Continue the active work focus instead of rediscovering completed work
