from __future__ import annotations

from typing import Sequence

import numpy as np
import pandas as pd


def monthly_rate(apr_pct: float) -> float:
    return float(apr_pct) / 100.0 / 12.0


def payment_for_loan(principal: float, apr_pct: float, term_months: int) -> float:
    if term_months <= 0:
        raise ValueError("term_months must be positive.")
    if principal <= 0:
        return 0.0

    rate = monthly_rate(apr_pct)
    if abs(rate) < 1e-12:
        return float(principal) / float(term_months)

    return float(principal) * rate / (1.0 - (1.0 + rate) ** (-term_months))


def amortization_schedule(principal: float, apr_pct: float, term_months: int) -> pd.DataFrame:
    if term_months <= 0:
        raise ValueError("term_months must be positive.")

    balance = max(float(principal), 0.0)
    rate = monthly_rate(apr_pct)
    scheduled_payment = payment_for_loan(balance, apr_pct, term_months)
    rows: list[dict[str, float | int]] = []

    for month in range(1, term_months + 1):
        beginning_balance = balance
        interest_paid = beginning_balance * rate if rate else 0.0
        principal_paid = min(max(scheduled_payment - interest_paid, 0.0), beginning_balance)
        actual_payment = principal_paid + interest_paid
        ending_balance = max(beginning_balance - principal_paid, 0.0)

        rows.append(
            {
                "month": month,
                "beginning_balance_usd": beginning_balance,
                "payment_usd": actual_payment,
                "interest_paid_usd": interest_paid,
                "principal_paid_usd": principal_paid,
                "ending_balance_usd": ending_balance,
            }
        )

        balance = ending_balance

    schedule = pd.DataFrame(rows)
    if schedule.empty:
        return schedule

    schedule["cumulative_interest_usd"] = schedule["interest_paid_usd"].cumsum()
    schedule["cumulative_principal_usd"] = schedule["principal_paid_usd"].cumsum()
    schedule["cumulative_payments_usd"] = schedule["payment_usd"].cumsum()
    return schedule


def loan_balance_series(principal: float, apr_pct: float, term_months: int, horizon_months: int) -> pd.DataFrame:
    if horizon_months < 0:
        raise ValueError("horizon_months must be non-negative.")

    amort = amortization_schedule(principal, apr_pct, max(term_months, 1))
    rows: list[dict[str, float | int]] = [
        {
            "month": 0,
            "payment_usd": 0.0,
            "interest_paid_usd": 0.0,
            "principal_paid_usd": 0.0,
            "ending_balance_usd": max(float(principal), 0.0),
            "cumulative_interest_usd": 0.0,
            "cumulative_principal_usd": 0.0,
            "cumulative_payments_usd": 0.0,
        }
    ]

    for month in range(1, horizon_months + 1):
        if month <= len(amort):
            row = amort.iloc[month - 1].to_dict()
            rows.append(
                {
                    "month": month,
                    "payment_usd": float(row["payment_usd"]),
                    "interest_paid_usd": float(row["interest_paid_usd"]),
                    "principal_paid_usd": float(row["principal_paid_usd"]),
                    "ending_balance_usd": float(row["ending_balance_usd"]),
                    "cumulative_interest_usd": float(row["cumulative_interest_usd"]),
                    "cumulative_principal_usd": float(row["cumulative_principal_usd"]),
                    "cumulative_payments_usd": float(row["cumulative_payments_usd"]),
                }
            )
            continue

        last = rows[-1]
        rows.append(
            {
                "month": month,
                "payment_usd": 0.0,
                "interest_paid_usd": 0.0,
                "principal_paid_usd": 0.0,
                "ending_balance_usd": 0.0,
                "cumulative_interest_usd": float(last["cumulative_interest_usd"]),
                "cumulative_principal_usd": float(last["cumulative_principal_usd"]),
                "cumulative_payments_usd": float(last["cumulative_payments_usd"]),
            }
        )

    return pd.DataFrame(rows)


def vehicle_value_series(
    current_market_value_usd: float,
    value_retention_pct_by_year: Sequence[float],
    horizon_months: int,
) -> pd.DataFrame:
    if horizon_months < 0:
        raise ValueError("horizon_months must be non-negative.")
    if not value_retention_pct_by_year:
        raise ValueError("value_retention_pct_by_year must not be empty.")

    year_marks = np.arange(0, len(value_retention_pct_by_year) + 1, dtype=float) * 12.0
    retention_points = np.asarray([1.0, *value_retention_pct_by_year], dtype=float)
    month_axis = np.arange(0, horizon_months + 1, dtype=float)

    final_month = year_marks[-1]
    if horizon_months > final_month:
        tail_months = np.arange(final_month + 12.0, horizon_months + 12.0, 12.0)
        if tail_months.size:
            last_ratio = retention_points[-1]
            previous_ratio = retention_points[-2] if retention_points.size > 1 else last_ratio
            annual_tail_factor = last_ratio / previous_ratio if previous_ratio else 1.0
            annual_tail_factor = min(max(annual_tail_factor, 0.80), 0.98)
            extra_points = []
            current_ratio = last_ratio
            for _ in tail_months:
                current_ratio *= annual_tail_factor
                extra_points.append(current_ratio)
            year_marks = np.concatenate([year_marks, tail_months])
            retention_points = np.concatenate([retention_points, np.asarray(extra_points, dtype=float)])

    interpolated_retention = np.interp(month_axis, year_marks, retention_points)
    values = float(current_market_value_usd) * interpolated_retention

    return pd.DataFrame(
        {
            "month": month_axis.astype(int),
            "retained_value_pct": interpolated_retention,
            "vehicle_value_usd": values,
        }
    )


def fuel_cost_per_month(annual_miles: float, combined_mpg: float, fuel_price_usd_per_gallon: float) -> float:
    if combined_mpg <= 0:
        raise ValueError("combined_mpg must be positive.")
    return (float(annual_miles) / 12.0 / float(combined_mpg)) * float(fuel_price_usd_per_gallon)


def annual_cost_to_monthly(annual_cost_usd: float) -> float:
    return float(annual_cost_usd) / 12.0
