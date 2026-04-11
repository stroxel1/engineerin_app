# Engineering App

A practical process-engineering application for day-to-day plant work, focused on:
- steam jets / thermo-compressors
- steam and thermal utility calculations
- hydraulics and line checks
- evaporator operating screens
- crystallizer operating screens
- workbook inspection and curve ingestion scaffolding
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
- Quick Tools
  - pressure conversion
  - temperature conversion
  - BPE-aware thermal point
  - flash steam estimate
- Hydraulics
  - velocity
  - Reynolds number
  - friction factor
  - pressure drop
  - TDH
  - line volume and residence time
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
- Per-input unit selectors are built into the browser shell.
- Workbook inspection and curve normalization are still conservative preview tools, intended to speed up later vendor-specific mapping.
