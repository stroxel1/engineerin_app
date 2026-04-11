# Engineering App Product Requirements

## Purpose

A process-engineering application for day-to-day use in chemical plants, with special focus on:
- citric acid production
- fructose refining
- steam/utilities-heavy operations
- evaporation, crystallization, hydraulics, and thermo-compression problems

The app should help engineers quickly evaluate operating conditions, troubleshoot plant problems, compare scenarios, and save engineering cases without rebuilding spreadsheets for every question.

---

## Primary Goals

1. Provide quick and trustworthy engineering calculations.
2. Support both fast utility calculations and deeper saved case studies.
3. Cover the most common process-engineering needs in steam/vacuum/liquid systems.
4. Be especially useful for citric acid and fructose plant work.
5. Support desktop-first engineering workflows with an eventual iOS engineering companion.

---

## Core Product Areas

### 1. Quick Tools

Small, high-frequency calculators used daily in plant work.

Functions:
- unit conversions
- pressure conversions
- vacuum conversions
- temperature conversions
- flow conversions
- concentration conversions
- pipe volume / tank volume
- residence time
- percent solids / brix helpers
- specific gravity helpers

### 2. Fluid Flow / Hydraulics

Functions:
- mass flow and volumetric flow
- velocity in pipe
- Reynolds number
- friction factor
- straight-pipe pressure drop
- fitting / valve / equivalent length losses
- static head
- total dynamic head (TDH)
- pump suction/discharge hydraulic helpers
- line sizing checks

Inputs:
- fluid flow rate
- density
- viscosity
- pipe material/roughness
- pipe ID / schedule / nominal size
- pipe length
- fittings and valve counts
- elevation change
- fluid temperature

Outputs:
- velocity
- Reynolds number
- friction factor
- pressure drop
- head loss
- TDH
- warnings on poor velocity ranges or suspicious assumptions

### 3. Steam & Utilities

Functions:
- saturated steam pressure/temperature relationships
- condensate estimates
- latent and sensible heat calculations
- steam flow vs heat duty
- flash steam calculations
- steam header pressure effects
- steam quality assumptions
- condensate return estimates
- condensing temperature calculations
- boiling temperature calculations
- pressure/temperature normalization for thermal calculations

Outputs:
- heat duty
- steam demand
- condensate load
- flash fraction
- normalized steam conditions
- condensing temperature
- boiling temperature

### 4. Steam Jets / Thermo-Compressors

Functions:
- compare operating point to vendor/performance curves
- measure and evaluate steam jet performance curves
- calculate entrainment ratio
- estimate motive steam requirement
- estimate suction vapor handling
- assess discharge feasibility
- identify feasible/infeasible operating windows
- compare multiple models or cases
- connect vapor conditions to condensing/boiling temperature context where relevant

Outputs:
- operating point fit vs curve
- motive steam demand
- suction load estimate
- compression feasibility
- curve envelope warnings
- temperature/pressure context for evaluation

### 5. Evaporators

Target equipment:
- falling film evaporators
- multi-pass evaporators
- multi-effect logic later

Functions:
- evaporation rate
- concentration progression
- boiling point elevation (BPE) correction
- boiling temperature calculation including BPE
- condensing temperature checks for heating vapor/steam
- steam economy estimate
- vapor generation estimate
- stage/pass operating windows
- fouling or low-ΔT warnings
- crystallization risk warnings

Citric/fructose emphasis:
- viscosity rise at concentration
- BPE limiting usable driving force
- final concentration risk checks
- condenser and vapor-load awareness

### 6. Crystallizers

Target equipment:
- forced-circulation crystallizers

Functions:
- mother liquor estimation
- supersaturation logic
- slurry solids estimate
- circulation ratio
- residence time
- crystal yield estimate
- operating temperature sensitivity
- stability/operability warnings

### 7. Heat & Mass Balance Tools

Functions:
- component mass balance
- solids balance
- blending and dilution
- recycle and purge calculations
- evaporative concentration
- rough energy balance
- utility load estimates

### 8. Process Properties

Shared process-property support for:
- density
- viscosity
- boiling point elevation
- solubility
- steam properties
- saturation temperature/pressure relationships
- concentration-property correlations
- condensing temperature and boiling temperature support

### 9. Case Management

Functions:
- save cases
- duplicate cases
- compare cases
- track assumptions
- attach notes
- export/share results
- maintain scenario history

---

## Required Pressure and Vacuum Support

Pressure/vacuum support is a foundational requirement and must be built into the app from the start.

### Pressure Units
- psig
- psia
- barg
- bara
- kPag
- kPaa
- kPa
- Pa
- MPa
- bar
- mbar
- psi
- inH2O
- mmH2O

### Vacuum Units
- inHg vacuum
- mmHg
- Torr
- microns
- mbar abs
- kPa abs
- psia
- % vacuum
- cmHg
- inches of water vacuum (optional early)

### Unit Handling Rules
- clearly distinguish gauge vs absolute
- clearly distinguish pressure vs vacuum basis
- allow user input in natural units
- convert internally to a canonical absolute-pressure basis
- warn if a calculation needs absolute pressure but the user appears to have entered gauge pressure
- support fast switching of display units without changing the stored physical value

Recommended internal basis:
- kPa absolute

---

## Industry-Specific Requirements

### Citric Acid Plant Focus
The app should strongly support:
- citric liquor concentration
- boiling point elevation
- evaporation limits
- crystallizer operation
- mother liquor handling
- supersaturation control
- slurry handling
- steam economy
- thermo-compressor integration with evaporation systems
- viscosity and density effects at concentration

### Fructose Refinery Focus
The app should strongly support:
- syrup concentration
- viscosity-sensitive flow calculations
- steam and evaporator utility checks
- exchanger/evaporator duty estimates
- line sizing and friction loss
- TDH and pump checks
- flash/vapor load calculations
- blending and concentration calculations

---

## Product Structure

### Module List
1. Quick Tools
2. Pressure & Vacuum
3. Fluid Flow
4. Steam & Utilities
5. Steam Jets / Thermo-Compressors
6. Evaporators
7. Crystallizers
8. Heat & Mass Balances
9. Case Manager

---

## V1 Priorities

### V1 Must-Have
- unit conversions
- pressure/vacuum conversions
- flow and hydraulics calculations
- friction loss / TDH
- temperature and pressure handling for thermal calculations
- steam calculations
- condensing temperature and boiling temperature calculations
- steam jet / thermo-compressor operating-point comparison
- steam jet performance-curve measurement/evaluation support
- evaporator mass-balance and BPE-aware calculations
- forced-circulation crystallizer basic model
- save/load/duplicate cases
- assumptions and notes

### V1.5 / Next Layer
- richer property models
- multi-effect evaporator logic
- sensitivity studies
- better curve interpolation and feasibility ranking
- more detailed crystallizer heuristics
- report export

### Later / Advanced
- optimization tools
- exchanger/condenser modules
- NPSH helpers
- plant-wide scenario linking
- iOS companion sync

---

## UX Expectations

The app should feel like a serious engineering tool:
- fast to use
- visually clear
- strong on units and warnings
- able to save work
- transparent about assumptions
- not dependent on rebuilding spreadsheets for every calculation

---

## Guiding Principle

This should become:
- a process calculator
- a troubleshooting tool
- an engineering case notebook
- an equipment evaluation tool

not just a pile of disconnected calculators.
