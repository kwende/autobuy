# Autobuy — Vehicle Decision Lab

A Jupyter notebook-based decision lab for comparing new vs. used vehicle purchases.

This is **not** intended to be a dealership-style monthly-payment calculator. The purpose is to make the tradeoffs visible, auditable, and explainable: purchase price, financing, depreciation, repair risk, warranty value, ownership horizon, operating costs, and resale value.

The model exists because “always buy used” and “new is better now” are both slogans. Useful slogans, sometimes. Still slogans. The notebook exists to do the arithmetic in public.

## Why this repo exists

When shopping for a vehicle, it is easy to drown in disconnected facts:

- new price vs. used price
- new APR vs. used APR
- rebates vs. promotional financing
- taxes and registration
- mileage
- warranty remaining
- expected repairs
- fuel cost
- resale value
- depreciation curve
- whether a specific quote is actually good

This project is meant to reduce that cognitive load.

The notebook should let us sit down, pick a few candidate vehicles, enter the actual quotes we received, adjust only the assumptions that are truly ours to adjust, and watch the charts move.

## Core design principle

Separate **facts**, **quotes**, **choices**, and **assumptions**.

The notebook should not expose a wall of editable variables where every number looks equally negotiable. Some values are decisions. Some values are local rules. Some values are vehicle-specific facts. Some values are stale market snapshots. Mixing them is how a useful model turns into a haunted spreadsheet.

## Input categories

### 1. Local constants

Location-specific facts and rule assumptions.

Examples:

- state/city/county
- vehicle tax assumptions
- title and registration assumptions
- local default fuel price, if used
- notes about sources and verification dates

Stored in:

```text
config/local/lincoln_ne_vehicle_constants.json
```

These values are displayed in the notebook, but they are not treated as normal scenario knobs.

### 2. Vehicle constants

Facts and valuation snapshots tied to a specific vehicle.

Examples:

- year
- make
- model
- trim
- mileage
- fuel type
- EPA MPG
- valuation snapshot
- depreciation estimate
- warranty remaining
- source and date of lookup

Stored in:

```text
config/vehicles/
```

A key distinction:

> We do not edit “Blue Book value” while analyzing a purchase. We change the selected vehicle or refresh that vehicle’s valuation snapshot.

A valuation is not eternal truth. It is a dated snapshot.

### 3. Quote inputs

Dealer/lender terms for a specific offer.

Examples:

- out-the-door price
- APR
- loan term
- rebate
- dealer documentation fee
- warranty offer price
- trade-in allowance

Stored in:

```text
config/scenarios/
```

The same vehicle can have multiple quotes. Therefore quotes are separate from vehicle files.

### 4. Household choices

Things we actually control.

Examples:

- down payment
- ownership horizon
- annual miles
- whether to include an extended warranty
- repair-risk posture

These are the main knobs to adjust while comparing scenarios.

### 5. Model assumptions

Forecasts and uncertain estimates.

Examples:

- future fuel price
- future resale value
- maintenance reserve
- repair reserve
- opportunity cost of capital
- depreciation schedule

These should be visible and adjustable, but clearly labeled as assumptions rather than facts.

## Math visibility rule

The notebook should never become a black box.

Each major section should follow this pattern:

1. short explanation
2. LaTeX equation
3. code that mirrors the equation
4. table and/or chart output
5. sanity checks where appropriate

A major output should be traceable to:

- one visible equation
- one code cell
- one visible set of inputs

This is specifically meant to avoid replacing one expert with another expert-shaped black box.

## Core questions the notebook should answer

- How much cheaper does a used vehicle need to be to beat a new one?
- Does a lower new-car APR offset the used-car price discount?
- How long are we underwater on the loan?
- What happens if the used car needs a major repair?
- How sensitive is the decision to depreciation, APR, repairs, insurance, fuel, or ownership horizon?
- At 3, 5, 8, and 10 years, which scenario consumed less money?
- Which assumptions matter enough to change the decision?

## V1 scope

V1 includes:

- JSON-backed local constants, vehicle files, and quote/scenario files
- guided intake helpers through notebook functions
- visible input classification
- amortization math
- remaining balance math
- depreciation/value schedule
- equity curve
- cumulative ownership-cost curve
- simple scenario comparison
- stale valuation warnings
- example vehicle/scenario JSON files

V1 does **not** include:

- live Kelley Blue Book / Black Book / JD Power valuation API integration
- dealer inventory scraping
- DOT decision tree
- web app
- Monte Carlo simulation
- automatic insurance quote integration

Those may be added later, but v1 should remain small enough to understand.

## Suggested workflow

1. Copy an example vehicle JSON or use the notebook intake helper.
2. Fill in the vehicle identity and dated valuation snapshot.
3. Copy an example scenario JSON or use the notebook quote helper.
4. Enter the dealer/lender quote facts.
5. Open `new_vs_used_vehicle_decision_lab.ipynb`.
6. Load 2–5 scenarios.
7. Adjust household choices and model assumptions.
8. Review:
   - loan schedule
   - vehicle value curve
   - equity curve
   - cumulative ownership cost
   - comparison table

## Repository structure

```text
.
├── README.md
├── requirements.txt
├── pyproject.toml
├── new_vs_used_vehicle_decision_lab.ipynb
├── config/
│   ├── local/
│   │   └── lincoln_ne_vehicle_constants.json
│   ├── manifests/
│   │   ├── vehicle_input_manifest.json
│   │   └── scenario_input_manifest.json
│   ├── vehicles/
│   │   ├── example_2026_new_vehicle.json
│   │   └── example_2023_used_vehicle.json
│   └── scenarios/
│       ├── example_new_vehicle_quote.json
│       └── example_used_vehicle_quote.json
└── src/
    └── autobuy/
        ├── __init__.py
        ├── analysis.py
        ├── finance_math.py
        └── io.py
```

## Notes for future Ben and future assistants

This repo is intentionally notebook-first.

Do not rush to turn it into a website. The value is in the transparent notebook: assumptions, equations, code, tables, and charts in one place.

Do not hide core math behind clever abstractions. Helper functions are fine, but the notebook should still show the equations and enough code to verify what is happening.

Do not treat all inputs as equal. Keep the categories clean:

```text
Scenario = local constants + vehicle constants + quote inputs + household choices + model assumptions
```

The goal is not perfect prediction.

The goal is understanding which assumptions matter enough to change the decision.
