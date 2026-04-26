from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK_PATH = ROOT / "new_vs_used_vehicle_decision_lab.ipynb"


def markdown_cell(source: str) -> dict:
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": source.splitlines(keepends=True),
    }


def code_cell(source: str) -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": source.splitlines(keepends=True),
    }


cells = [
    markdown_cell(
        """# New vs. Used Vehicle Decision Lab

This notebook is meant to keep the arithmetic visible. It is not trying to predict the future perfectly, and it is not pretending every number is equally editable.

The working pattern is:

1. pick the candidate vehicle facts
2. load the quote you actually received
3. adjust only the household choices and model assumptions that are truly yours to change
4. inspect the equations, tables, and charts together
"""
    ),
    markdown_cell(
        """## Scope and Ground Rules

- Local rules such as sales tax live in JSON so they do not clutter the discussion.
- Vehicle facts and valuation snapshots live in per-vehicle JSON files.
- Dealer quote terms live in per-scenario JSON files.
- The notebook shows both an estimated out-the-door calculation and the quoted out-the-door total, because dealer worksheets often contain line items that do not fit a simple tax model.
"""
    ),
    code_cell(
        """from pathlib import Path
import sys

import matplotlib.pyplot as plt
import pandas as pd
from IPython.display import Markdown, display

ROOT = Path.cwd()
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from autobuy.analysis import (
    build_input_tables,
    build_monthly_scenario_dataframe,
    build_purchase_audit,
    comparison_table,
    scenario_label,
    stale_valuation_message,
)
from autobuy.io import build_template_from_manifest, load_manifest, load_scenario_bundle, project_path

pd.set_option("display.max_rows", 200)
pd.set_option("display.float_format", lambda value: f"{value:,.2f}")
plt.style.use("seaborn-v0_8-whitegrid")
"""
    ),
    code_cell(
        """scenario_paths = [
    project_path("config", "scenarios", "example_new_vehicle_quote.json"),
    project_path("config", "scenarios", "example_used_vehicle_quote.json"),
]

scenario_bundles = [load_scenario_bundle(path) for path in scenario_paths]
[scenario_label(bundle) for bundle in scenario_bundles]
"""
    ),
    markdown_cell(
        """## Input Classification

The whole point of the structure is to keep the inputs separated by type. That way we do not treat a valuation snapshot, a Lincoln tax rate, and a household down payment choice as if they were the same kind of number.
"""
    ),
    code_cell(
        """for bundle in scenario_bundles:
    display(Markdown(f"## {scenario_label(bundle)}"))
    warning = stale_valuation_message(bundle)
    if warning:
        display(Markdown(f"> **Warning:** {warning}"))

    for title, table in build_input_tables(bundle).items():
        display(Markdown(f"### {title}"))
        display(table)
"""
    ),
    markdown_cell(
        r"""## Purchase Math

The notebook uses a simple audit calculation for the quote worksheet:

\[
\text{Estimated Taxable Base} = P_{\text{sale}} + F_{\text{taxable}}
\]

\[
\text{Estimated Sales Tax} = \tau \cdot \text{Estimated Taxable Base}
\]

\[
\text{Estimated OTD} = P_{\text{sale}} + F_{\text{taxable}} + \text{Estimated Sales Tax} + F_{\text{government}} + W
\]

where:

- \(P_{\text{sale}}\) is the negotiated sale price
- \(F_{\text{taxable}}\) are taxable fees such as dealer doc fees if applicable
- \(\tau\) is the combined sales-tax rate
- \(F_{\text{government}}\) are non-tax government/title fees
- \(W\) is the warranty amount if you choose to include it

If the dealer gives you a quoted out-the-door number, the notebook uses that as the source of truth and treats the formula as a sanity check.
"""
    ),
    code_cell(
        """purchase_audit = pd.DataFrame([build_purchase_audit(bundle) for bundle in scenario_bundles]).set_index("scenario")
purchase_audit
"""
    ),
    markdown_cell(
        r"""## Loan Math

For a financed amount \(L\), monthly rate \(r\), and term \(n\), the standard payment formula is:

\[
\text{PMT} = \frac{Lr}{1 - (1 + r)^{-n}}
\]

The monthly schedule then decomposes each payment into:

\[
\text{Interest}_t = r \cdot \text{Balance}_{t-1}
\]

\[
\text{Principal}_t = \text{PMT} - \text{Interest}_t
\]

\[
\text{Balance}_t = \text{Balance}_{t-1} - \text{Principal}_t
\]
"""
    ),
    code_cell(
        """schedules = {scenario_label(bundle): build_monthly_scenario_dataframe(bundle) for bundle in scenario_bundles}

for name, schedule in schedules.items():
    display(Markdown(f"### {name}: first 12 months"))
    display(
        schedule.head(13)[
            [
                "month",
                "payment_usd",
                "interest_paid_usd",
                "principal_paid_usd",
                "ending_balance_usd",
                "vehicle_value_usd",
                "equity_usd",
            ]
        ]
    )
"""
    ),
    markdown_cell(
        r"""## Value Curve and Equity

Vehicle value is modeled from the dated market snapshot in the vehicle JSON:

\[
\text{Value}_t = \text{Snapshot Value} \cdot \text{Retention Factor}_t
\]

That makes the valuation date explicit. If the snapshot is stale, the notebook warns you instead of quietly assuming the number is still fresh.

Equity before selling friction is:

\[
\text{Equity}_t = \text{Value}_t - \text{Loan Balance}_t
\]
"""
    ),
    code_cell(
        """fig, axes = plt.subplots(len(schedules), 1, figsize=(10, 4 * len(schedules)), sharex=True)
if len(schedules) == 1:
    axes = [axes]

for axis, (name, schedule) in zip(axes, schedules.items()):
    axis.plot(schedule["month"], schedule["vehicle_value_usd"], label="Vehicle value")
    axis.plot(schedule["month"], schedule["ending_balance_usd"], label="Loan balance")
    axis.set_title(name)
    axis.set_ylabel("USD")
    axis.legend()

axes[-1].set_xlabel("Month")
plt.tight_layout()
plt.show()
"""
    ),
    markdown_cell(
        r"""## Net Cost If Sold at Month \(t\)

One useful summary is:

\[
\text{Net Cost}_t = D + \sum_{i=1}^{t} (\text{Payment}_i + \text{Operating Cost}_i) - \text{Sale Cash Flow}_t
\]

with:

\[
\text{Sale Cash Flow}_t = \text{Value}_t (1 - s) - \text{Loan Balance}_t
\]

where:

- \(D\) is the down payment
- \(s\) is the disposition haircut for trade-in/private-sale friction

This answers a practical question: if we bought this car and sold it after month \(t\), how much money would the scenario have consumed?
"""
    ),
    code_cell(
        """fig, ax = plt.subplots(figsize=(10, 5))

for name, schedule in schedules.items():
    ax.plot(schedule["month"], schedule["net_cost_if_sold_usd"], label=name)

ax.set_title("Cumulative net cost if sold")
ax.set_xlabel("Month")
ax.set_ylabel("USD")
ax.legend()
plt.tight_layout()
plt.show()
"""
    ),
    markdown_cell(
        """## Hold-Period Comparison

This table gives a quick answer for a few hold periods. Lower net cost is better. Equity is included separately because some people think more clearly when cost and asset position are shown side by side.
"""
    ),
    code_cell(
        """hold_months = scenario_bundles[0]["local_constants"]["notebook_defaults"]["default_hold_months"]
comparison_table(scenario_bundles, hold_months)
"""
    ),
    markdown_cell(
        """## Blank Intake Templates

These templates come from the manifests in `config/manifests/`. They are useful when you want a reminder of the fields without manually searching old JSON files.
"""
    ),
    code_cell(
        """vehicle_template = build_template_from_manifest(load_manifest("vehicle"))
scenario_template = build_template_from_manifest(load_manifest("scenario"))

vehicle_template, scenario_template
"""
    ),
    markdown_cell(
        """## Next Step for Real Shopping

Before using this for a real purchase discussion:

1. copy the example vehicle JSON and replace the valuation snapshot with a real dated lookup
2. copy the example scenario JSON and replace sale price, fees, APR, and insurance assumptions with the live quote
3. rerun the notebook and compare at the hold periods that actually matter to your household
"""
    ),
]

notebook = {
    "cells": cells,
    "metadata": {
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3",
        },
        "language_info": {
            "name": "python",
            "version": "3.11",
        },
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}

NOTEBOOK_PATH.parent.mkdir(parents=True, exist_ok=True)
NOTEBOOK_PATH.write_text(json.dumps(notebook, indent=2) + "\n", encoding="utf-8")
print(f"Wrote {NOTEBOOK_PATH}")
