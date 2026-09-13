"""Pre-submission safety gate for output.csv.

This module re-checks every prediction row against the challenge's hard
output rules BEFORE anything is submitted.  It reads files only when a
function is called, so importing it has no side effects.
"""

import re
import sys

import pandas as pd

# Allowed values straight from the output contract.
STATUSES = {
    "affordable_now",
    "affordable_with_plan",
    "affordable_later",
    "not_affordable",
}
METHODS = {
    "full_payment",
    "partial_payment",
    "installments",
    "wait",
    "not_recommended",
}

# payment_plan: 'none' OR date:amount pairs joined by '|'.
PLAN_RE = re.compile(
    r"^(none|(\d{4}-\d{2}-\d{2}:\d+(\.\d+)?)(\|\d{4}-\d{2}-\d{2}:\d+(\.\d+)?)*)$"
)
# spending_changes: up to three stop:/reduce_to: actions joined by '|'.
CHANGES_RE = re.compile(
    r"^(none|(stop|reduce_to):event_\w+(:\d+(\.\d+)?)?"
    r"(\|(stop|reduce_to):event_\w+(:\d+(\.\d+)?)?){0,2})$"
)

# The output contract allows this ONE column to be blank (a request may never
# become safely payable in full within the forecast window).  Every other
# required column must contain a real value.
REQUIRED_COLUMNS = [
    "request_id",
    "amount_safe_to_pay",
    "affordability_status",
    "recommended_payment_method",
    "payment_plan",
    "earliest_date_for_full_payment",
    "spending_changes_needed",
    "decision_explanation",
]
EMPTY_ALLOWED = {"earliest_date_for_full_payment"}

TOLERANCE = 0.01  # money is compared to the cent, never for exact equality


def _parse_plan(plan_str: str) -> list[tuple[str, float]]:
    """Split 'date:amount|date:amount' into (date, amount) pairs."""
    entries = []
    for part in str(plan_str).split("|"):
        date_str, amount_str = part.split(":", 1)
        entries.append((date_str, float(amount_str)))
    return entries


def _option_schedule(option) -> list[tuple[str, float]]:
    """Rebuild the installment schedule a payment option implies.

    The verifier must compare the plan against the option row itself, because
    the rules say an installment plan may only come from a supplied option —
    never from an invented schedule.
    """
    start = str(option.get("first_payment_date", ""))[:10]
    if not start or start == "nan":
        return []
    interval = option.get("payment_frequency_days")
    interval = 30 if pd.isna(interval) else int(interval)
    total = float(option.get("total_payable_amount"))
    per = float(option.get("payment_amount"))
    num = option.get("number_of_payments")
    num = int(num) if not pd.isna(num) else 1

    entries = []
    start_ts = pd.Timestamp(start)
    for i in range(num):
        pay_date = (start_ts + pd.Timedelta(days=interval * i)).strftime("%Y-%m-%d")
        if i == num - 1:
            paid = sum(amount for _, amount in entries)
            amount = round(total - paid, 2)
        else:
            amount = round(per, 2)
        entries.append((pay_date, amount))
    return entries


def _plans_match(plan_entries: list[tuple[str, float]],
                 schedule: list[tuple[str, float]]) -> bool:
    """True when the plan and the option schedule agree on dates and cents."""
    if len(plan_entries) != len(schedule):
        return False
    for (plan_date, plan_amount), (opt_date, opt_amount) in zip(plan_entries, schedule):
        if plan_date != opt_date:
            return False
        if abs(plan_amount - opt_amount) > TOLERANCE:
            return False
    return True


def verify_output(output_csv_path: str,
                  requests_csv_path: str) -> tuple[bool, list[str]]:
    """Validate every row of output.csv against the hard output rules.

    Returns (all_passed, errors).  If all_passed is False the submission
    must not proceed — a broken row is worse than a late one.
    """
    errors: list[str] = []

    output = pd.read_csv(output_csv_path)
    requests = pd.read_csv(requests_csv_path)

    # The options file lives next to requests.csv; installment plans are
    # only valid if they match one of its rows exactly.
    options_path = requests_csv_path.rsplit("/", 1)[0] + "/request_payment_options.csv"
    options = pd.read_csv(options_path)

    # --- Global checks first: wrong shape makes per-row checks meaningless --
    missing = [c for c in REQUIRED_COLUMNS if c not in output.columns]
    extra = [c for c in output.columns if c not in REQUIRED_COLUMNS]
    if missing:
        errors.append(f"Missing columns: {missing}")
    if extra:
        errors.append(f"Unexpected columns: {extra}")
    if errors:
        return False, errors

    if len(output) != len(requests):  # check 12
        errors.append(
            f"Row count mismatch: output has {len(output)}, "
            f"requests has {len(requests)}")

    requests_by_id = requests.set_index("request_id")

    for index, row in output.iterrows():
        rid = str(row["request_id"])
        context = f"row {index} ({rid})"

        # --- check 13: no NaN / empty strings in required columns -----------
        # earliest_date_for_full_payment is the one column the contract
        # allows to be blank (a request may never become safely payable in
        # full within the forecast window), so NaN there is expected, not an
        # error.  Everywhere else a missing value means a broken row.
        for column in REQUIRED_COLUMNS:
            if column in EMPTY_ALLOWED:
                continue
            value = row[column]
            if pd.isna(value):
                errors.append(f"{context}: NaN in '{column}'")
            elif str(value).strip() == "":
                errors.append(f"{context}: empty value in '{column}'")

        if rid not in requests_by_id.index:
            errors.append(f"{context}: request_id not found in requests.csv")
            continue

        request = requests_by_id.loc[rid]
        requested_amount = float(request["requested_amount"])
        request_date = str(request["request_date"])[:10]

        # --- check 1: bounds on the safe amount ------------------------------
        try:
            safe_amount = float(row["amount_safe_to_pay"])
            if not (0 <= safe_amount <= requested_amount):
                errors.append(
                    f"{context}: amount_safe_to_pay {safe_amount} outside "
                    f"[0, {requested_amount}]")
        except (TypeError, ValueError):
            errors.append(f"{context}: amount_safe_to_pay is not numeric")

        # --- checks 2-3: allowed categorical values ---------------------------
        status = str(row["affordability_status"])
        if status not in STATUSES:
            errors.append(f"{context}: invalid affordability_status '{status}'")
        method = str(row["recommended_payment_method"])
        if method not in METHODS:
            errors.append(f"{context}: invalid payment method '{method}'")

        # --- checks 4, 10: string schemas -------------------------------------
        plan_str = str(row["payment_plan"])
        if not PLAN_RE.match(plan_str):
            errors.append(f"{context}: payment_plan '{plan_str}' fails regex")
        changes_str = str(row["spending_changes_needed"])
        if not CHANGES_RE.match(changes_str):
            errors.append(f"{context}: spending_changes '{changes_str}' fails regex")

        # --- check 5: affordable_now coherence ---------------------------------
        if status == "affordable_now":
            if str(row["earliest_date_for_full_payment"]) != request_date:
                errors.append(
                    f"{context}: affordable_now but earliest date != request_date")
            if plan_str == "none":
                errors.append(f"{context}: affordable_now but payment_plan is 'none'")

        # --- check 6: wait coherence ------------------------------------------
        if method == "wait":
            if plan_str != "none":
                errors.append(f"{context}: wait but payment_plan != 'none'")
            if status != "affordable_later":
                errors.append(f"{context}: wait but status is '{status}'")
            if pd.isna(row["earliest_date_for_full_payment"]) \
                    or not str(row["earliest_date_for_full_payment"]).strip():
                errors.append(f"{context}: wait but earliest date is empty")

        # --- check 7: partial plans have exactly two payments ------------------
        if method == "partial_payment":
            parts = plan_str.split("|")
            if plan_str == "none" or len(parts) != 2:
                errors.append(
                    f"{context}: partial_payment must have exactly 2 entries, "
                    f"got {0 if plan_str == 'none' else len(parts)}")
            else:
                try:
                    entries = _parse_plan(plan_str)
                except ValueError:
                    errors.append(f"{context}: unparseable partial payment_plan")
                else:
                    total = sum(amount for _, amount in entries)
                    if abs(total - requested_amount) > TOLERANCE:
                        errors.append(
                            f"{context}: partial plan sums to {total}, "
                            f"expected {requested_amount}")

        # --- check 8: installments match a supplied option ---------------------
        if method == "installments":
            try:
                plan_entries = _parse_plan(plan_str)
            except ValueError:
                errors.append(f"{context}: unparseable installment plan")
            else:
                req_options = options[options["request_id"] == rid]
                matched = any(
                    _plans_match(plan_entries, _option_schedule(opt))
                    for _, opt in req_options.iterrows()
                )
                if not matched:
                    errors.append(
                        f"{context}: installment plan matches no row in "
                        f"request_payment_options.csv")

        # --- check 9: not_recommended means no plan ---------------------------
        if method == "not_recommended" and plan_str != "none":
            errors.append(f"{context}: not_recommended but payment_plan != 'none'")

        # --- check 11: no stop AND reduce_to on the same event -----------------
        stops, reduces = set(), set()
        if changes_str != "none":
            for part in changes_str.split("|"):
                pieces = part.split(":")
                if pieces[0] == "stop":
                    stops.add(pieces[1])
                elif pieces[0] == "reduce_to":
                    reduces.add(pieces[1])
        conflict = stops & reduces
        if conflict:
            errors.append(
                f"{context}: stop and reduce_to on same event(s): "
                f"{sorted(conflict)}")

    return (len(errors) == 0), errors


if __name__ == "__main__":
    ok, all_errors = verify_output("../output.csv", "../dataset/requests.csv")
    if ok:
        print(f"PASS — all rows verified")
        sys.exit(0)
    print(f"FAIL — {len(all_errors)} errors")
    for error in all_errors[:20]:
        print(f"  {error}")
    sys.exit(1)