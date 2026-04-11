# Engineering App Development Continuity

Last updated: 2026-04-11

Purpose:
Keep a durable restart point so work can resume quickly after disconnects or session loss.

## Current project location
- `/Users/stephentroxel/Documents/projects/engineering_app`

## Current verified app URL
- `http://127.0.0.1:8507`

## Recent completed feature tranches
1. Fresh engineering_app created in Documents/projects and initialized as git repo
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
   - vessel/static-head screen
   - control valve Cv/Kv sizing
   - cavitation/flashing screening
   - pump/system curve overlay
10. Hydraulics page bottom rendering error fixed (local pandas import shadowing `pd`)
11. Quick tools expanded with blend, brix reconciliation, and tank inventory helpers.
12. Hydraulics expanded further with parallel branch balancing and vessel/static-head screens.
13. Dashboard and roadmap are now intended to stay updated with active work and completed items shown struck through in-app.
14. Quick Tools expanded with utility cost screens for steam and electricity so plant issues can be translated into hourly/daily/annual operating-cost impact.
15. Quick Tools utility cost work now includes current-vs-proposed delta screens with annual savings estimates for steam and electricity.

## Recent git commits
- `7af1d88` Fix hydraulics page bottom rendering error
- `60cb7d8` Add hydraulics control valve sizing screen
- `79e28b6` Add pump power, NPSHa, and segmented hydraulics tools
- `6f317bf` Add solution BPE screen and schedule 10S hydraulics tools
- `a9b2c5b` Add citric BPE tools and unit-selectable outputs

## Files most relevant right now
- `web_app.py`
- `core/steam.py`
- `core/quicktools.py`
- `core/hydraulics.py`
- `core/citric_bpe.py`
- `core/solutions.py`
- `README.md`

## Current user preferences / constraints
- Keep improving the app without stopping to ask
- Keep notes so work can restart easily after disconnects
- Selectable measurement units should exist on every input and output
- Manual BPE is not wanted
- User especially cares about high-DS citric behavior and practical hydraulic/system tools

## Next high-value work items
1. Hydraulics
   - suction/discharge vessel modeling refinement
   - pump curve libraries or upload-based pump curves matched against system curves
   - optional balancing-valve/orifice coefficient sizing from the new self-balancing branch results
2. Quick tools
   - ratio-target blend solving
3. Evaporators
   - design-calibrated evaporator mode from workbook logic
4. Steam jets
   - import workbook-derived curve families and compare multiple models
5. Crystallizers
   - stronger solubility / supersaturation correlations

## If resuming after disconnect
1. Check git status in project root
2. Read this file first
3. Read `README.md`
4. Run compile check:
   `python3 -m py_compile $(find /Users/stephentroxel/Documents/projects/engineering_app -name '*.py' | tr '\n' ' ')`
5. Verify app endpoint or relaunch Streamlit if needed
6. Continue the next high-value tranche instead of redoing already completed work
