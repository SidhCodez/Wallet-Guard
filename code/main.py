"""Tier 1 orchestrator: read dataset, run oracle + plan_engine, write output.csv.

Run from the code/ directory:

    python3 main.py

The pipeline is fully deterministic: no LLM calls, no randomness, no network.
"""

import sys

import pandas as pd

from src.data_loader import load_all_datasets
from src.oracle import (
    binary_search_safe_amount,
    earliest_full_payment_date,
    is_safe,
)
from src.plan_engine import (
    generate_candidate_plans,
    rank_plans,
    optimize_spending_changes,
    build_payment_plan_string,
    build_spending_changes_string,
)
from src.currency import convert

# The exact columns the grader expects, in the exact order.
OUTPUT_COLUMNS = [
    "request_id",
    "amount_safe_to_pay",
    "affordability_status",
    "recommended_payment_method",
    "payment_plan",
    "earliest_date_for_full_payment",
    "spending_changes_needed",
    "decision_explanation",
]

# Event statuses that never move cash.
DEAD_STATUSES = {"cancelled", "failed", "unrealized"}


def parse_user_accepts(raw) -> list[str]:
    """Split the profile's payment-preference field into a clean list.

    The dataset separates values with '|', but commas are accepted too so the
    code stays forgiving.  A blank field means "no preference stated", and the
    challenge default is to consider every method.
    """
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return ["full_payment", "partial_payment", "installments"]
    text = str(raw).strip()
    if not text:
        return ["full_payment", "partial_payment", "installments"]
    methods = []
    for part in text.replace("|", ",").split(","):
        part = part.strip()
        if part:
            methods.append(part)
    return methods


def as_bool(value) -> bool:
    """Normalize 'true'/'false' strings from the CSV into real booleans."""
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() == "true"


def build_timeline(row, user_events, home_currency, rates):
    """Build the minimal forecast timeline for one user.

    Why these rules: the oracle only simulates days from request_date onward,
    so past events are already baked into the current balance and must not be
    counted twice.  Pending credits are not cash yet, but pending debits are
    reserved so the user cannot spend money that is already spoken for.
    Recurrence is NOT expanded here: the dataset supplies scheduled future
    rows individually, so expanding again would double-count commitments.
    Detecting recurrence from history is deferred to a later tier.
    """
    request_date = str(row["request_date"])[:10]
    horizon_end = pd.Timestamp(request_date) + pd.Timedelta(days=90)

    timeline = []
    for _, event in user_events.iterrows():
        status = str(event.get("status", "") or "").lower()
        if status in DEAD_STATUSES:
            continue
        if pd.isna(event.get("amount")):
            # A blank amount is unknown, NOT zero — skip rather than guess.
            continue

        # Cash lands on the settlement date when one is stated.
        effective_date = event.get("settlement_date")
        if pd.isna(effective_date) or not str(effective_date).strip():
            effective_date = event.get("event_date")
        effective_date = str(effective_date)[:10]

        # Past events are already reflected in the current balance.
        if effective_date < request_date:
            continue
        # Far-future events outside the forecast window cannot matter.
        if pd.Timestamp(effective_date) > horizon_end:
            continue

        amount = float(event["amount"])
        currency = str(event.get("currency") or home_currency)
        if currency != home_currency:
            try:
                amount = convert(amount, currency, home_currency,
                                 effective_date, rates)
            except ValueError:
                # No rate row: conservatively skip rather than guess a value.
                continue

        # The dataset says debit/credit; the oracle wants in/out.
        raw_direction = str(event.get("direction", "") or "").lower()
        if raw_direction == "credit":
            direction = "in"
        else:
            direction = "out"

        # Pending credits do not count; pending debits are reserved.
        if status == "pending" and direction == "in":
            continue
        kind = "pending_debit" if status == "pending" else "one_time"

        flexibility = str(event.get("flexibility", "") or "").lower()
        is_flexible = flexibility == "flexible"
        is_essential = not is_flexible

        timeline.append({
            "event_id": str(event.get("event_id", "")),
            "date": effective_date,
            "amount": amount,
            "direction": direction,
            "kind": kind,
            "status": status,
            "is_essential": is_essential,
            "is_flexible": is_flexible,
        })

    # Deterministic order: by date, then event_id.
    timeline.sort(key=lambda e: (e["date"], e["event_id"]))
    return timeline


def build_request_options(request_id, options_df):
    """Convert the dataset's option rows into dicts plan_engine understands."""
    req_options = []
    for _, opt in options_df.iterrows():
        num_payments = opt.get("number_of_payments")
        if pd.isna(num_payments):
            num_payments = 1
        req_options.append({
            "payment_option_id": str(opt["payment_option_id"]),
            "start_date": str(opt.get("first_payment_date"))[:10],
            "interval_days": int(opt["payment_frequency_days"])
            if not pd.isna(opt.get("payment_frequency_days")) else 30,
            "total_payable": float(opt.get("total_payable_amount")),
            "per_payment": float(opt.get("payment_amount")),
            "num_payments": int(num_payments),
        })
    return req_options


def process_row(row, profiles, events, options, rates):
    """Run the oracle + plan engine for one request and return its output row."""
    profile = profiles[profiles["user_id"] == row["user_id"]].iloc[0]
    starting_balance = float(profile["current_available_balance"])
    min_balance = float(profile["minimum_balance_to_keep"])
    home_currency = str(profile["home_currency"])
    user_accepts = parse_user_accepts(profile["payment_methods_user_will_consider"])

    user_events = events[events["user_id"] == row["user_id"]]
    timeline = build_timeline(row, user_events, home_currency, rates)

    req_options = build_request_options(row["request_id"],
                                        options[options["request_id"] == row["request_id"]])

    request = {
        "request_id": row["request_id"],
        "request_date": str(row["request_date"])[:10],
        "requested_amount": float(row["requested_amount"]),
        "desired_completion_date": str(row["desired_completion_date"])[:10],
        "allows_partial_payment": as_bool(row["allows_partial_payment"]),
    }

    safe_amount = binary_search_safe_amount(
        request, timeline, starting_balance, min_balance)
    earliest_full = earliest_full_payment_date(
        request, timeline, starting_balance, min_balance)

    candidates = generate_candidate_plans(
        request, timeline, starting_balance, min_balance,
        req_options, user_accepts)
    winner = rank_plans(candidates, request["desired_completion_date"])

    # --- Decide the final output fields ---------------------------------
    if safe_amount >= request["requested_amount"]:
        status = "affordable_now"
        method = "full_payment"
        plan_str = build_payment_plan_string({
            "entries": [{"date": request["request_date"],
                         "amount": request["requested_amount"]}]})
        earliest = request["request_date"]
        changes_str = "none"
        explanation = ("Full payment is safe today and keeps balance above "
                       "minimum.")
    elif winner is not None and winner["method"] == "wait":
        # BUG 1 fix: a winning wait plan means NO payment today and one full
        # payment later, so the status is affordable_later and the plan
        # string stays "none" (nothing is scheduled at the seller today).
        status = "affordable_later"
        method = "wait"
        plan_str = "none"
        earliest = earliest_full if earliest_full else ""
        changes_str = "none"
        explanation = ("Full payment becomes safe on "
                       "earliest_full_payment_date.")
    elif winner is not None:
        status = "affordable_with_plan"
        method = winner["method"]
        plan_str = build_payment_plan_string(winner)
        earliest = earliest_full if earliest_full else ""
        changes_str = "none"
        explanation = f"Request is affordable using {method}."
    elif earliest_full is not None:
        status = "affordable_later"
        method = "wait"
        plan_str = "none"
        earliest = earliest_full
        changes_str = "none"
        explanation = ("Full payment becomes safe on "
                      "earliest_full_payment_date.")
    else:
        changes = optimize_spending_changes(
            request, timeline, starting_balance, min_balance)
        status = "not_affordable"
        method = "not_recommended"
        plan_str = "none"
        earliest = ""
        if changes:
            changes_str = build_spending_changes_string(changes)
            explanation = ("Not affordable within 90 days even with spending "
                           "changes.")
        else:
            changes_str = "none"
            explanation = ("Not affordable within 90 days. No safe plan "
                           "found.")

    return {
        "request_id": row["request_id"],
        "amount_safe_to_pay": safe_amount,
        "affordability_status": status,
        "recommended_payment_method": method,
        "payment_plan": plan_str,
        "earliest_date_for_full_payment": earliest,
        "spending_changes_needed": changes_str,
        "decision_explanation": explanation,
    }


def fallback_row(row, error):
    """A safe, schema-valid row used when processing unexpectedly fails."""
    return {
        "request_id": row["request_id"],
        "amount_safe_to_pay": 0,
        "affordability_status": "not_affordable",
        "recommended_payment_method": "not_recommended",
        "payment_plan": "none",
        "earliest_date_for_full_payment": "",
        "spending_changes_needed": "none",
        "decision_explanation": f"Processing error: {type(error).__name__}",
    }


def run():
    """Execute the whole Tier 1 pipeline and write output.csv."""
    data = load_all_datasets("../dataset")
    requests = data["requests"]
    profiles = data["financial_profiles"]
    events = data["financial_events"]
    options = data["request_payment_options"]
    rates = data["exchange_rates"]

    results = []
    failed = 0
    for _, row in requests.iterrows():
        try:
            results.append(process_row(row, profiles, events, options, rates))
        except Exception as error:  # noqa: BLE001 — never crash the batch run
            failed += 1
            print(f"Error on {row['request_id']}: {error}", file=sys.stderr)
            results.append(fallback_row(row, error))

    output_df = pd.DataFrame(results, columns=OUTPUT_COLUMNS)

    # --- Sanity checks before saving --------------------------------------
    assert len(output_df) == len(requests), (
        f"Row mismatch: {len(output_df)} vs {len(requests)}")
    assert (output_df["amount_safe_to_pay"] >= 0).all()
    assert (output_df["amount_safe_to_pay"]
            <= requests["requested_amount"].values).all()

    output_df.to_csv("../output.csv", index=False)

    # --- Diagnostics -------------------------------------------------------
    # Percentage breakdowns help spot a biased decision tree at a glance.
    status_counts = output_df["affordability_status"].value_counts()
    print("Status breakdown:")
    for k, v in status_counts.items():
        print(f"  {k}: {v} ({100*v/len(output_df):.1f}%)")
    method_counts = output_df["recommended_payment_method"].value_counts()
    print("Method breakdown:")
    for k, v in method_counts.items():
        print(f"  {k}: {v}")

    # Baseline check: a not_affordable verdict should be caused by the
    # request, not by a budget that is already underwater.  If the balance
    # breaches the minimum with NO payment at all, warn — those users need
    # attention regardless of any purchase decision.
    not_affordable_ids = set(
        output_df.loc[output_df["affordability_status"] == "not_affordable",
                      "request_id"])
    for _, row in requests.iterrows():
        if row["request_id"] not in not_affordable_ids:
            continue
        try:
            profile = profiles[profiles["user_id"] == row["user_id"]].iloc[0]
            timeline = build_timeline(
                row,
                events[events["user_id"] == row["user_id"]],
                str(profile["home_currency"]),
                rates)
            baseline_safe = is_safe(
                [],
                timeline,
                str(row["request_date"])[:10],
                float(profile["current_available_balance"]),
                float(profile["minimum_balance_to_keep"]),
            )
            if not baseline_safe:
                print(
                    f"Warning: {row['request_id']} baseline finances already "
                    "dip below minimum_balance_to_keep with no payment.",
                    file=sys.stderr)
        except Exception as error:  # noqa: BLE001 — diagnostics never stop the run
            print(f"Baseline check error on {row['request_id']}: {error}",
                  file=sys.stderr)

    print(f"Total rows processed: {len(output_df)}")
    print("By affordability_status:")
    print(output_df["affordability_status"].value_counts().to_string())
    print("By recommended_payment_method:")
    print(output_df["recommended_payment_method"].value_counts().to_string())
    if failed:
        print(f"Failed rows: {failed}")


if __name__ == "__main__":
    run()