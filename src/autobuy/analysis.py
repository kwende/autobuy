from __future__ import annotations

from datetime import date
from typing import Any, Iterable

import pandas as pd

from .finance_math import (
    annual_cost_to_monthly,
    fuel_cost_per_month,
    loan_balance_series,
    payment_for_loan,
    vehicle_value_series,
)


def scenario_label(bundle: dict[str, Any]) -> str:
    meta = bundle["scenario"].get("meta", {})
    return str(meta.get("label") or meta.get("scenario_id") or "Unnamed scenario")


def _flatten_mapping(mapping: dict[str, Any], prefix: str = "") -> list[tuple[str, Any]]:
    rows: list[tuple[str, Any]] = []
    for key, value in mapping.items():
        dotted = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            rows.extend(_flatten_mapping(value, dotted))
        else:
            rows.append((dotted, value))
    return rows


def _to_table(mapping: dict[str, Any]) -> pd.DataFrame:
    rows = [{"field": key, "value": value} for key, value in _flatten_mapping(mapping)]
    return pd.DataFrame(rows)


def build_input_tables(bundle: dict[str, Any]) -> dict[str, pd.DataFrame]:
    local_constants = dict(bundle["local_constants"])
    local_sources = local_constants.pop("sources", [])

    tables = {
        "Local constants": _to_table(local_constants),
        "Vehicle constants": _to_table(bundle["vehicle"]),
        "Quote inputs": _to_table(bundle["scenario"]["quote_inputs"]),
        "Household choices": _to_table(bundle["scenario"]["household_choices"]),
        "Model assumptions": _to_table(bundle["scenario"]["model_assumptions"]),
    }

    if local_sources:
        tables["Local sources"] = pd.DataFrame(local_sources)

    return tables


def snapshot_age_days(bundle: dict[str, Any], as_of: date | None = None) -> int | None:
    valuation = bundle["vehicle"].get("valuation", {})
    lookup_date = valuation.get("valuation_lookup_date")
    if not lookup_date:
        return None

    as_of = as_of or date.today()
    snapshot = date.fromisoformat(str(lookup_date))
    return (as_of - snapshot).days


def stale_valuation_message(bundle: dict[str, Any], as_of: date | None = None) -> str | None:
    age_days = snapshot_age_days(bundle, as_of=as_of)
    if age_days is None:
        return None

    threshold = int(bundle["local_constants"]["notebook_defaults"].get("stale_snapshot_warning_days", 45))
    if age_days <= threshold:
        return None

    label = scenario_label(bundle)
    return (
        f"{label}: valuation snapshot is {age_days} days old, which exceeds the "
        f"{threshold}-day notebook warning threshold. Refresh the market-value input before trusting the comparison."
    )


def build_purchase_audit(bundle: dict[str, Any]) -> dict[str, Any]:
    scenario = bundle["scenario"]
    quote = scenario["quote_inputs"]
    choices = scenario["household_choices"]
    local = bundle["local_constants"]["taxes_and_fees"]

    taxable_fees = float(quote.get("dealer_doc_fee_usd", 0.0)) + float(quote.get("other_taxable_fees_usd", 0.0))
    taxable_base = float(quote["sale_price_usd"]) + taxable_fees
    sales_tax = taxable_base * float(local["combined_sales_tax_rate_pct"]) / 100.0
    warranty_cost = float(quote.get("extended_warranty_price_usd", 0.0)) if quote.get("include_extended_warranty") else 0.0
    estimated_out_the_door = (
        float(quote["sale_price_usd"])
        + taxable_fees
        + sales_tax
        + float(quote.get("government_fees_usd", 0.0))
        + warranty_cost
    )

    quoted_out_the_door = quote.get("quoted_out_the_door_price_usd")
    purchase_cost_used = float(quoted_out_the_door) if quoted_out_the_door is not None else estimated_out_the_door
    down_payment = float(choices["down_payment_usd"])
    amount_financed = max(purchase_cost_used - down_payment, 0.0)
    monthly_payment = payment_for_loan(amount_financed, float(quote["apr_pct"]), int(quote["loan_term_months"]))
    total_of_payments = monthly_payment * int(quote["loan_term_months"])

    return {
        "scenario": scenario_label(bundle),
        "sale_price_usd": float(quote["sale_price_usd"]),
        "taxable_fees_usd": taxable_fees,
        "estimated_taxable_base_usd": taxable_base,
        "estimated_sales_tax_usd": sales_tax,
        "government_fees_usd": float(quote.get("government_fees_usd", 0.0)),
        "included_warranty_cost_usd": warranty_cost,
        "estimated_out_the_door_usd": estimated_out_the_door,
        "quoted_out_the_door_usd": float(quoted_out_the_door) if quoted_out_the_door is not None else None,
        "purchase_cost_used_usd": purchase_cost_used,
        "estimate_gap_usd": purchase_cost_used - estimated_out_the_door,
        "down_payment_usd": down_payment,
        "amount_financed_usd": amount_financed,
        "apr_pct": float(quote["apr_pct"]),
        "loan_term_months": int(quote["loan_term_months"]),
        "monthly_payment_usd": monthly_payment,
        "total_of_payments_usd": total_of_payments,
        "total_interest_usd": total_of_payments - amount_financed,
    }


def build_monthly_scenario_dataframe(bundle: dict[str, Any]) -> pd.DataFrame:
    audit = build_purchase_audit(bundle)
    scenario = bundle["scenario"]
    vehicle = bundle["vehicle"]
    assumptions = scenario["model_assumptions"]
    choices = scenario["household_choices"]
    warranty = vehicle["efficiency_and_warranty"]
    valuation = vehicle["valuation"]

    horizon_months = int(choices["ownership_horizon_months"])
    loan_term_months = int(scenario["quote_inputs"]["loan_term_months"])
    balances = loan_balance_series(
        audit["amount_financed_usd"],
        audit["apr_pct"],
        loan_term_months,
        horizon_months,
    )
    values = vehicle_value_series(
        float(valuation["current_market_value_usd"]),
        valuation["value_retention_pct_by_year"],
        horizon_months,
    )

    df = balances.merge(values, on="month", how="left")
    df["scenario"] = scenario_label(bundle)

    combined_mpg = float(warranty["combined_mpg"])
    annual_miles = float(choices["annual_miles"])
    fuel_price = float(assumptions["fuel_price_usd_per_gallon"])
    monthly_fuel = fuel_cost_per_month(annual_miles, combined_mpg, fuel_price)
    monthly_insurance = annual_cost_to_monthly(float(assumptions["annual_insurance_usd"]))
    monthly_maintenance = annual_cost_to_monthly(float(assumptions["annual_maintenance_usd"]))
    monthly_registration = annual_cost_to_monthly(float(assumptions["annual_registration_usd"]))

    basic_warranty_months_remaining = int(warranty.get("basic_warranty_months_remaining", 0))
    under_warranty_repair = annual_cost_to_monthly(
        float(assumptions["annual_major_repair_reserve_while_under_warranty_usd"])
    )
    after_warranty_repair = annual_cost_to_monthly(
        float(assumptions["annual_major_repair_reserve_after_warranty_usd"])
    )

    df["fuel_cost_usd"] = monthly_fuel
    df["insurance_cost_usd"] = monthly_insurance
    df["maintenance_cost_usd"] = monthly_maintenance
    df["registration_cost_usd"] = monthly_registration
    df["under_basic_warranty"] = df["month"] <= basic_warranty_months_remaining
    df["major_repair_reserve_usd"] = df["under_basic_warranty"].map(
        lambda under_warranty: under_warranty_repair if under_warranty else after_warranty_repair
    )

    # Month zero is the purchase date: no recurring costs yet.
    recurring_cost_columns = [
        "fuel_cost_usd",
        "insurance_cost_usd",
        "maintenance_cost_usd",
        "registration_cost_usd",
        "major_repair_reserve_usd",
    ]
    df.loc[df["month"] == 0, recurring_cost_columns] = 0.0

    df["monthly_operating_cost_usd"] = df[recurring_cost_columns].sum(axis=1)
    df["cumulative_operating_cost_usd"] = df["monthly_operating_cost_usd"].cumsum()

    disposition_cost_pct = float(assumptions["expected_disposition_cost_pct"])
    df["equity_usd"] = df["vehicle_value_usd"] - df["ending_balance_usd"]
    df["net_sale_cash_if_sold_usd"] = (df["vehicle_value_usd"] * (1.0 - disposition_cost_pct / 100.0)) - df[
        "ending_balance_usd"
    ]

    df["cumulative_owner_cash_out_usd"] = (
        float(audit["down_payment_usd"]) + df["cumulative_payments_usd"] + df["cumulative_operating_cost_usd"]
    )
    df["net_cost_if_sold_usd"] = df["cumulative_owner_cash_out_usd"] - df["net_sale_cash_if_sold_usd"]

    return df


def comparison_table(bundles: Iterable[dict[str, Any]], hold_months: Iterable[int]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    hold_months = list(hold_months)

    for bundle in bundles:
        audit = build_purchase_audit(bundle)
        schedule = build_monthly_scenario_dataframe(bundle).set_index("month")
        row: dict[str, Any] = {
            "scenario": scenario_label(bundle),
            "purchase_cost_used_usd": audit["purchase_cost_used_usd"],
            "amount_financed_usd": audit["amount_financed_usd"],
            "monthly_payment_usd": audit["monthly_payment_usd"],
            "total_interest_usd": audit["total_interest_usd"],
        }

        for month in hold_months:
            if month not in schedule.index:
                continue
            schedule_row = schedule.loc[month]
            row[f"net_cost_{month}m_usd"] = float(schedule_row["net_cost_if_sold_usd"])
            row[f"equity_{month}m_usd"] = float(schedule_row["equity_usd"])
            row[f"loan_balance_{month}m_usd"] = float(schedule_row["ending_balance_usd"])
            row[f"vehicle_value_{month}m_usd"] = float(schedule_row["vehicle_value_usd"])

        rows.append(row)

    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows).set_index("scenario").sort_index()
