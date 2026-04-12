# Engineering App

A practical process-engineering application for day-to-day plant work, focused on:
- steam jets / thermo-compressors
- steam and thermal utility calculations
- hydraulics and line checks
- evaporator operating screens
- crystallizer operating screens
- workbook inspection and curve ingestion scaffolding
- solution BPE screening for citric acid, fructose, dextrose, and sucrose
- case save/load workflows

## Current stack
- Python
- Streamlit
- Plotly
- Pandas
- OpenPyXL

## Project structure
- `app.py` — simple manifest entrypoint
- `web_app.py` — runnable Streamlit browser app
- `core/models.py` — canonical engineering case/stream/equipment models
- `core/curves.py` — curve interpolation and steam-jet operating-point helpers
- `core/evaporators.py` — evaporator calculations
- `core/crystallizers.py` — crystallizer calculations
- `core/hydraulics.py` — pipe flow and TDH calculations
- `core/steam.py` — steam duty, flash steam, and utility cost helpers
- `core/tanks.py` — tank inventory / hold-up calculations
- `core/thermal.py` — condensing/boiling temperature helpers
- `core/quicktools.py` — engineer-facing wrappers
- `core/units.py` — per-input unit conversion utilities
- `core/cases.py` — save/load case handling
- `io/` — workbook inspection and normalization scaffolding
- `state/` — central app state models/store
- `docs/` — assumptions and product requirements
- `data/cases/` — saved engineering cases

## Install
From the parent directory:

```bash
cd /Users/stephentroxel/Documents/projects
python3 -m pip install -e engineering_app
```

## Run the browser app
From the parent directory:

```bash
cd /Users/stephentroxel/Documents/projects
PYTHONPATH=. streamlit run engineering_app/web_app.py
```

Default URL:
- http://localhost:8501

## Working browser sections
- Dashboard
- Roadmap
- Solution BPE
  - citric workbook-table interpolation through 60 wt% DS
  - workbook-derived >60 DS citric screening estimate with warnings
  - fructose, dextrose, and sucrose BPE screening
  - BPE-driven capacity-impact screen
  - visible in-app priority list for next improvements
  - aligned with the hourly review loop
- Quick Tools
  - pressure conversion
  - temperature conversion
  - BPE-aware thermal point
  - flash steam estimate
  - product-specific solution properties for citric acid, fructose, dextrose, and sucrose syrups/solutions
  - Brix reconciliation against lab solids and/or density with suggested refractometer offset/factor plus downstream property screening
  - dilution water balance for syrup and liquor blend-back work
  - two-stream blend mixing for liquor, syrup, condensate, and water additions with blended solids, temperature, and downstream property screening
  - ratio-target blend solving to determine required makeup/addition flow needed to hit a target solids level from one fixed stream
  - tank inventory / hold-up screening for vertical cylindrical, horizontal cylindrical, and rectangular tanks with optional density and transfer-rate based mass and residence-time checks
  - utility cost screening for steam users and electric motors with hourly/daily/annual operating cost estimates
  - current-vs-proposed utility comparison deltas with annual savings estimates for steam and electricity
- Hydraulics
  - velocity
  - Reynolds number
  - friction factor
  - pressure drop
  - TDH
  - line volume and residence time
  - schedule 10S stainless presets from 1/2 in to 12 in
  - fitting and valve count-based K calculations
  - size comparison across common stainless lines
  - pump hydraulic/brake power
  - NPSHa screening
  - suction-vessel-to-pump NPSHa scenario with optional NPSHr margin screening
  - pump field troubleshooting check from suction/discharge gauge readings with developed head, velocity/elevation corrections, hydraulic power, and expected-TDH comparison
  - baseline-vs-current pump field comparison with flow/head/power/suction-margin deltas
  - measured-point mismatch diagnosis against a selected pump curve at the measured flow
  - segmented suction/discharge system breakdowns
  - parallel branch entered-split check with branch head mismatch / throttling-loss estimate
  - balancing-device screen for entered branch splits with required extra loss, equivalent Cv/Kv, and sharp-edge orifice diameter/beta estimate
  - self-balancing parallel branch flow solver for natural split screening
  - vessel/static-head screen
  - control-valve Cv/Kv sizing
  - pump vs system curve overlay
  - pump rerate / affinity screening from speed or impeller changes with relative power and NPSHr impact factors
  - liquid control-valve Cv/Kv sizing with valve-authority, trim-opening, cavitation-index, FL-based critical-ΔP, and flashing screening
- Steam Jets
  - manual curve editor
  - operating-point screening vs curve
  - workbook/CSV model-family import
  - workbook-preview auto-normalization for vendor-style curve tables
  - family / motive-basis filtering for imported curve libraries
  - side-by-side comparison of multiple imported curves at one operating point
  - curve interpolation
  - % of curve and deviation view
  - thermo-compressor balance screen for suction load, motive steam demand, entrainment ratio, compression ratio, and discharge saturation temperature
- Steam & Utilities
  - steam required for duty
  - duty from steam flow
  - steam header pressure-change screening for same-duty steam demand, same-flow duty loss, and optional process-side ΔT checks
  - improved steam saturation / condensing temperature screening via piecewise Antoine water correlation
- Evaporators
  - feed/product/evaporation rate
  - boiling and condensing temperature screen
  - steam demand and steam economy
  - design-calibrated U·A·ΔT capacity mode for existing evaporator bodies
  - required area vs installed area screening with achievable evaporation/product concentration estimates
  - optional product-based BPE auto-fill for citric acid, fructose, dextrose, and sucrose liquors
- Crystallizers
  - citric mother-liquor solids auto-filled from published solubility-vs-temperature data
  - crystal-volume-percent slurry basis for citric crystallizers
  - supersaturation / metastable-band screening from feed solids versus equilibrium mother liquor at operating temperature
  - equilibrium-solids, absolute supersaturation, relative supersaturation, supersaturation-ratio, and solids-above-equilibrium metrics
  - crystal yield estimate
  - slurry and mother liquor estimate
  - circulation ratio
  - residence time estimate
- Workbook Import
  - upload `.xlsx` / `.xlsm`
  - inspect sheet dimensions, hidden state, freeze panes, formulas, headers, and sample rows
  - preview normalized tables
- Case Manager
  - save the latest calculation payload
  - browse and load saved JSON cases

## Notes
- The current tools are engineering screens, not rigorous design models.
- Pressure is handled internally on an absolute kPa basis.
- The engineering calculator pages now expose selectable units on inputs and displayed outputs.
- Utility cost tools now include current-vs-proposed comparison screens so annual savings can be estimated directly in-app.
- Quick Tools now include ratio-target blend solving so operators can back-calculate required dilution/addition rates from a desired final solids target.
- Workbook inspection and steam-jet curve normalization remain conservative preview tools, intended to speed up later vendor-specific mapping rather than replace vendor performance confirmation.
- Parallel branch, vessel, pump field comparison, and measured-vs-curve troubleshooting tools are first-pass engineering screens; they should be validated against plant topology, pressure-instrument basis, and vendor pump data before design decisions.
- Crystallizer supersaturation bands are user-entered screening thresholds, not first-principles metastable-zone property data.
