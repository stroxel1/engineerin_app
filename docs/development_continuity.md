     1|# Engineering App Development Continuity
     2|
     3|Last updated: 2026-04-12 11:06 CDT
     4|
     5|Purpose:
     6|Keep a durable restart point so work can resume quickly after disconnects or session loss.
     7|
     8|## Current project location
     9|- `/Users/stephentroxel/Documents/projects/engineering_app`
    10|
    11|## Current verified app URL
    12|- `http://127.0.0.1:8612`
    13|- Verified HTTP status: 200 OK
    14|- Browser snapshot loaded the Dashboard and Hydraulics sections successfully with no browser console errors
    15|- Hydraulics > Pump & NPSHa rendered the pump field troubleshooting section plus the new baseline-comparison / curve-diagnosis controls during browser verification
    16|
    17|## Current repo status
    18|- Expect tracked edits in:
    19|  - `README.md`
    20|  - `core/hydraulics.py`
    21|  - `core/pump_curves.py`
    22|  - `web_app.py`
    23|  - `docs/development_continuity.md`
    24|- Untracked paths may still exist under:
    25|  - `data/`
    26|- If resuming, inspect `git status --short` first because local data artifacts and later commits may have changed the tree again
    27|
    28|## Major completed feature tranches
    29|1. Fresh `engineering_app` created in Documents/projects and initialized as a git repo
    30|2. Streamlit browser shell added
    31|3. Core engineering modules expanded with per-input units
    32|4. Steam jets / thermo-compressor curve comparison added
    33|5. Workbook upload + inspection UI added
    34|6. Case manager UI added
    35|7. Citric BPE tool added using workbook table through 60 DS and provisional >60 DS estimate
    36|8. Solution BPE expanded to fructose, dextrose, and sucrose
    37|9. Hydraulics expanded with:
    38|   - schedule 10S stainless presets from 1/2 in to 12 in
    39|   - fitting and valve K-value counts
    40|   - TDH / pressure drop / residence time / line volume
    41|   - size comparison and line-size recommendation
    42|   - pump power
    43|   - NPSHa screen
    44|   - segmented system breakdown
    45|   - parallel branch balancing screen
    46|   - balancing-device Cv/Kv and equivalent-orifice sizing from entered split checks
    47|   - vessel/static-head screen
    48|   - control valve Cv/Kv sizing
    49|   - cavitation/flashing screening
    50|   - pump/system curve overlay
    51|   - built-in and uploaded pump-curve matching against system curves
    52|   - pump rerate / affinity screening from speed or impeller changes with relative power and NPSHr factors
    53|   - suction-vessel-to-pump NPSHa scenario with optional NPSHr margin screening
    54|   - pump field baseline comparison and curve diagnosis workflow
    55|10. Hydraulics runtime bugs fixed:
    56|   - local pandas shadowing bug on hydraulics page
    57|   - missing `volumetric_flow_to_m3_h` import
    58|   - missing `length_to_m` import
    59|   - repaired corrupted `analyze_parallel_branches` self-balancing solver path
    60|11. Steam jets expanded with:
    61|   - workbook/CSV-driven model-family import
    62|   - grouped curve-library building from tabular vendor data
    63|   - side-by-side operating-point comparison across imported models
    64|   - workbook-preview auto-normalization for vendor-style curve tables
    65|   - family / motive-basis filtering for imported curve libraries
    66|12. Pump hydraulics BEP proximity & instrument bias added:
    67|    - BEP estimation from curve using 85% shutoff head heuristic
    68|    - BEP proximity assessment with flow/head offsets, preferred zone check, reliability risk flags
    69|    - Instrument bias screen: whether standard gauge accuracy (2%-5%) could explain flow/head deviations
    70|    - UI under Hydraulics > Pump & NPSHa with checkbox toggle, built-in/manual curve entry
    71|13. Evaporator fouling/NCG allowance screening added:
    72|    - Fouling degradation via series-resistance model (clean vs dirty U)
    73|    - NCG partial-pressure dilution lowering effective condensing temperature
    74|    - Combined capacity penalty with U-degradation and delta-T penalty breakdown
    75|    - Engineering notes when degradation exceeds 25% and 50% thresholds
    76|    - UI under Steam > Evaporator
    77|14. Steam jets with multi-effect evaporator staging added:
    78|    - Multi-effect evaporator screening with per-effect BPE, ΔT distribution, and steam economy
    79|    - Effect-by-effect temperature and solids profile plots
    80|    - Vendor presets for steam-jet workbook import (Croll-Reynolds, Graham, Schutte & Koerting, GEA)
    81|    - Auto-detection of vendor format from sheet name and column headers
    82|15. Citric crystallizers expanded with:
    83|   - citric mother-liquor solids auto-filled from published solubility-vs-temperature data
    84|   - crystal-volume-percent slurry basis for citric crystallizers
    85|   - supersaturation / metastable-band screening from feed solids versus equilibrium mother-liquor solids
    86|   - solids-above-equilibrium, supersaturation-ratio, and relative-supersaturation metrics
    87|   - residence-time suppression when no crystallization is predicted at the chosen temperature/DS basis
    88|13. Evaporators expanded with:
    89|   - design-calibrated U·A·ΔT capacity mode for installed bodies
    90|   - required area vs installed area screening
    91|   - achievable evaporation / concentration estimates from installed capacity
    92|14. Quick Tools expanded with:
    93|   - blend tools
    94|   - Brix reconciliation
    95|   - tank inventory helpers
    96|   - steam/electric utility cost screens
    97|   - current-vs-proposed savings delta screens
    98|   - ratio-target blend solver
    99|15. Dashboard and roadmap now show active work and completed items with strike-through formatting in-app
   100|16. Hydraulics expanded with a pump field troubleshooting check that converts suction/discharge gauge readings into developed head, hydraulic/brake power, vapor-pressure margin, and expected-TDH comparison
   101|17. Hydraulics expanded again with:
   102|   - current-vs-baseline field case comparison using measured flow/head/power/suction-margin deltas
   103|   - measured-point mismatch diagnosis against a selected pump curve at the measured flow
   104|   - dashboard/roadmap refresh to move the next hydraulics gap to BEP proximity / instrument-bias screening
   105|
   106|## Files most relevant now
   107|- `web_app.py`
   108|- `core/hydraulics.py`
   109|- `core/pump_curves.py`
   110|- `io/normalizers.py`
   111|- `core/curves.py`
   112|- `core/steam.py`
   113|- `core/quicktools.py`
   114|- `core/crystallizers.py`
   115|- `README.md`
   116|- `docs/development_continuity.md`
   117|
   118|## Current user preferences / constraints
   119|- Keep improving the app without stopping to ask
   120|- Keep notes so work can restart easily after disconnects
   121|- Selectable measurement units should exist on every input and output
   122|- Manual BPE is not wanted
   123|- User especially cares about high-DS citric behavior and practical hydraulic/system tools
   124|- Prefer practical plant calculators before design-grade rigor
   125|
   126|## Current active work focus
   127|1. Evaporators
   128|   - fouling/NCG allowance screening landed
   129|   - next: body-by-body staging or workbook-derived calibration inputs
   130|2. Steam jets
   131|   - extend workbook auto-normalization with vendor-specific sheet presets and richer basis metadata
   132|3. Citric crystallizer
   133|   - multi-body capacity screening with feed/withdrawal balance
   134|4. Solution BPE
   135|   - >60 DS citric refined with continuous quadratic fit to full 15-60 wt% table
   136|
   137|## Next high-value work items
   138|1. Evaporators: body-by-body staging or workbook-derived calibration inputs
   139|2. Steam jets: vendor-specific workbook presets / mapping aids on top of the preview normalizer
   140|3. Citric crystallizer: multi-body crystallizer capacity screening with explicit feed/withdrawal balance
   141|4. Solution BPE: >60 DS citric refined with continuous quadratic fit (R² > 0.99999)
   142|
   143|## Known cautions
   144|- The app has had repeated runtime regressions from missing imports or partial edits after feature additions. After edits, always run:
   145|  - compile check
   146|  - direct Python import check
   147|  - focused runtime check for the edited calculator path
   148|  - live HTTP/browser check
   149|- Steam-jet workbook auto-normalization is preview-based and only sees sampled rows; treat it as a screening aid for faster mapping, not a final vendor parser
   150|- Citric >60 DS estimate now uses a continuous quadratic fit to the full 15-60 wt% table (R-squared > 0.99999) with only 0.0004 deg F discontinuity at the table boundary; beyond ~80 wt% mark as screening only
   151|- Parallel branch, vessel, pump field comparison, and measured-vs-curve troubleshooting tools are first-pass engineering screens, not final design calculations
   152|- Crystallizer supersaturation bands are user-entered screening thresholds, not validated metastable-zone property data
   153|
   154|## Resume checklist after disconnect
   155|1. `cd /Users/stephentroxel/Documents/projects/engineering_app`
   156|2. `git status --short`
   157|3. Read this file first
   158|4. Read `README.md`
   159|5. Run compile check:
   160|   `python3 -m py_compile $(find /Users/stephentroxel/Documents/projects/engineering_app -name '*.py' | tr '\n' ' ')`
   161|6. Run import + focused pump-field comparison smoke test:
   162|   `cd /Users/stephentroxel/Documents/projects && PYTHONPATH=. /usr/bin/python3 - <<'PY'
   163|import engineering_app.web_app
   164|from engineering_app.core.hydraulics import analyze_pump_field_check, compare_pump_field_cases
   165|from engineering_app.core.pump_curves import compare_measured_point_to_curve, get_builtin_curve
   166|baseline = analyze_pump_field_check(
   167|    flow_m3_h=95.0,
   168|    density_kg_m3=998.0,
   169|    suction_pressure_value=8.0,
   170|    suction_pressure_unit='psig',
   171|    discharge_pressure_value=34.0,
   172|    discharge_pressure_unit='psig',
   173|    suction_pipe_id_mm=77.9,
   174|    discharge_pipe_id_mm=77.9,
   175|    suction_gauge_elevation_m=0.0,
   176|    discharge_gauge_elevation_m=1.0,
   177|    pump_efficiency_fraction=0.74,
   178|    expected_system_head_m=20.0,
   179|    liquid_temperature_c=30.0,
   180|)
   181|current = analyze_pump_field_check(
   182|    flow_m3_h=88.0,
   183|    density_kg_m3=998.0,
   184|    suction_pressure_value=4.5,
   185|    suction_pressure_unit='psig',
   186|    discharge_pressure_value=30.0,
   187|    discharge_pressure_unit='psig',
   188|    suction_pipe_id_mm=77.9,
   189|    discharge_pipe_id_mm=77.9,
   190|    suction_gauge_elevation_m=0.0,
   191|    discharge_gauge_elevation_m=1.0,
   192|    pump_efficiency_fraction=0.70,
   193|    expected_system_head_m=20.0,
   194|    liquid_temperature_c=30.0,
   195|)
   196|comparison = compare_pump_field_cases(95.0, baseline, 88.0, current)
   197|curve_diag = compare_measured_point_to_curve(get_builtin_curve('ansi_50hz_full'), 88.0, current.developed_head_m)
   198|print('import ok', round(current.developed_head_m, 3), round(comparison.developed_head_delta_m, 3), curve_diag.status)
   199|PY`
   200|7. Launch a fresh Streamlit instance on a new unused port and verify with browser tools or `curl -I`
   201|8. Continue the active work focus instead of rediscovering completed work
   202|