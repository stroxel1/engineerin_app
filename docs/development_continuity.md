# Engineering App Development Continuity

Last updated: 2026-04-11 15:58 CDT

Purpose:
Keep a durable restart point so work can resume quickly after disconnects or session loss.

## Current project location
- `/Users/stephentroxel/Documents/projects/engineering_app`

## Current verified app URL
- `http://127.0.0.1:8506`
- Verified HTTP status: 200 OK

## Current repo status
- Working tree mostly clean
- Untracked path:
  - `data/`
- If resuming, inspect `git status --short` first

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
   - vessel/static-head screen
   - control valve Cv/Kv sizing
   - cavitation/flashing screening
   - pump/system curve overlay
10. Hydraulics runtime bugs fixed:
   - local pandas shadowing bug on hydraulics page
   - missing `volumetric_flow_to_m3_h` import
   - missing `length_to_m` import
11. Quick Tools expanded with:
   - blend tools
   - Brix reconciliation
   - tank inventory helpers
   - steam/electric utility cost screens
   - current-vs-proposed savings delta screens
   - ratio-target blend solver
12. Dashboard and roadmap now show active work and completed items with strike-through formatting in-app

## Most recent relevant commits
- `d841a40` Add ratio-target blend quick tool
- `3d33167` Add utility cost comparison quick tools
- `98ba1ec` Show active and completed progress on dashboard and roadmap
- `604089e` Add branch and vessel hydraulics screens
- `8fc01a3` Fix missing volumetric flow import in hydraulics page
- `ee6c8e3` Add branch balance and vessel head hydraulics tools
- `7af1d88` Fix hydraulics page bottom rendering error

## Files most relevant now
- `web_app.py`
- `core/steam.py`
- `core/quicktools.py`
- `core/hydraulics.py`
- `core/citric_bpe.py`
- `core/solutions.py`
- `core/tanks.py`
- `README.md`
- `docs/development_continuity.md`

## Current user preferences / constraints
- Keep improving the app without stopping to ask
- Keep notes so work can restart easily after disconnects
- Selectable measurement units should exist on every input and output
- Manual BPE is not wanted
- User especially cares about high-DS citric behavior and practical hydraulic/system tools
- If a real blocking question comes up, ask; otherwise continue

## Current active work focus
1. Hydraulics refinement
   - smarter branch-network balancing beyond fixed split assumptions
   - better suction/discharge vessel interaction with pump and NPSH workflows
2. Evaporator enhancement planning
   - design-calibrated evaporator mode from workbook-style logic

## Next high-value work items
1. Hydraulics
   - suction/discharge vessel modeling refinement tied into pump/NPSH screens
   - pump curve libraries or upload-based pump curves matched against system curves
   - optional balancing-valve/orifice coefficient sizing from self-balancing branch results
2. Evaporators
   - design-calibrated evaporator mode from workbook logic
3. Steam jets
   - import workbook-derived curve families and compare multiple models
4. Crystallizers
   - stronger solubility / supersaturation correlations
5. Quick tools
   - further plant economics / what-if screens as needed

## Known cautions
- The app has had repeated runtime regressions from missing imports after feature additions. After edits, always run:
  - compile check
  - direct Python import check
  - live HTTP check
- Citric >60 DS estimate is still a screening model and should stay labeled accordingly
- Parallel branch and vessel tools are first-pass engineering screens, not final design calculations

## Resume checklist after disconnect
1. `cd /Users/stephentroxel/Documents/projects/engineering_app`
2. `git status --short`
3. Read this file first
4. Read `README.md`
5. Run compile check:
   `python3 -m py_compile $(find /Users/stephentroxel/Documents/projects/engineering_app -name '*.py' | tr '\n' ' ')`
6. Run import smoke test:
   `cd /Users/stephentroxel/Documents/projects && PYTHONPATH=. python - <<'PY'
import engineering_app.web_app
print('import ok')
PY`
7. Check live app:
   `curl -I -s http://127.0.0.1:8506`
8. Continue the active work focus instead of rediscovering completed work
