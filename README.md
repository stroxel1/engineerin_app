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
- `core/steam.py` — steam duty and flash steam helpers
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
  - dilution water balance for syrup and liquor blend-back work
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
  - segmented suction/discharge system breakdowns
- Steam Jets
  - manual curve editor
  - operating-point screening vs curve
  - curve interpolation
  - % of curve and deviation view
- Steam & Utilities
  - steam required for duty
  - duty from steam flow
- Evaporators
  - feed/product/evaporation rate
  - boiling and condensing temperature screen
  - steam demand and steam economy
  - optional product-based BPE auto-fill for citric acid, fructose, dextrose, and sucrose liquors
- Crystallizers
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
- Workbook inspection and curve normalization are still conservative preview tools, intended to speed up later vendor-specific mapping.
