# Assumptions and Formula Notes

## Steam Jets / Thermo-Compressors
- Import actual vendor curve structure from workbook.
- Normalize motive/suction/discharge variables.
- Support interpolation between curves once sheet structure is known.

## Evaporators
- Add boiling point elevation correction from supplied citric workbook.
- Add stage/pass handling for multi-pass systems.
- Add rough steam economy and vapor load tracking.
- Early foundation now includes boiling and condensing temperature helpers plus lumped steam-flow estimation.

## Crystallizers
- Add citric acid solubility/supersaturation correlations.
- Add mother liquor and slurry concentration calculations.
- Add operating heuristics for forced-circulation systems.

## Utilities / Quick Tools
- Pressure/vacuum conversions exist.
- Hydraulics/friction-loss/TDH helpers exist.
- Early steam-duty and flash-steam helpers exist.
