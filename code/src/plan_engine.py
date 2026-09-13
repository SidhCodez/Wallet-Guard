"""Deterministic payment-plan engine.

This module turns a request into candidate payment plans, checks each one
against the oracle's safety rule, and picks the best plan with a fixed
tie-break order.  It never calls an LLM, never reads files, and never uses
randomness, so the same inputs always give the same winning plan.
"""

import math
from datetime import date, timedelta

try:
    # Normal case: run from code/ so "src" is a package.
    from src import oracle
except ImportError:
    # Direct execution: add code/ to sys.path so src.oracle still resolves.
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from src import oracle


def _parse_date(value: str) -> date:
    """Turn a YYYY-MM-DD string into a date for day arithmetic."""
    return date.fromisoformat(str(value)[:10])


def _format_amount(amount: float) -> str:
    """Round to 2 decimals and drop a trailing '.0' for clean plan strings."""
    rounded = round(float(amount), 2)
    if rounded == int(rounded):
        return str(int(rounded))
    return str(rounded)


def _plan_dict(method, entries, total_paid, payment_option_id=None,
               desired_completion_date=None):
    """Bundle a candidate plan with the fields the ranker compares.

    Keeping this in one helper guarantees every candidate has the same keys.
    """
    end_date = max(entry["date"] for entry in entries) if entries else None
    completes = (
        end_date is not None
        and desired_completion_date is not None
        and end_date <= desired_completion_date
    )
    return {
        "method": method,
        "entries": entries,
        "total_paid": total_paid,
        "num_payments": len(entries),
        "start_date": entries[0]["date"] if entries else None,
        "payment_option_id": payment_option_id,
        "completes_by_deadline": completes,
    }


def generate_candidate_plans(request, timeline, starting_balance, min_balance,
                             payment_options, user_accepts):
    """Build every eligible plan that the oracle confirms as safe.

    A plan only qualifies when the simulated balance stays at or above
    ``min_balance`` for the full forecast AND the last payment lands on or
    before ``desired_completion_date``.  Late plans are dropped here so the
    ranker never has to rescue them.
    """
    request_date = request["request_date"]
    requested = float(request["requested_amount"])
    deadline = request.get("desired_completion_date")
    user_accepts = set(user_accepts or [])
    candidates = []

    def _safe(entries):
        return oracle.is_safe(entries, timeline, request_date,
                              starting_balance, min_balance)

    # 1. Full payment today, if the user would consider it and it is safe.
    if "full_payment" in user_accepts:
        full_entries = [{"date": request_date, "amount": requested}]
        if _safe(full_entries):
            candidates.append(_plan_dict(
                "full_payment", full_entries, requested,
                desired_completion_date=deadline))

    # Reusable safety numbers for partial and wait plans.
    safe_amount = oracle.binary_search_safe_amount(
        request, timeline, starting_balance, min_balance)
    earliest = oracle.earliest_full_payment_date(
        request, timeline, starting_balance, min_balance)

    # 2. Partial payment: pay what is safe today, the rest on the earliest
    #    safe full-payment date.  Exactly two entries that sum to the request.
    if (request.get("allows_partial_payment")
            and "partial_payment" in user_accepts
            and 0 < safe_amount < requested
            and earliest is not None
            and earliest <= deadline):
        partial_entries = [
            {"date": request_date, "amount": safe_amount},
            {"date": earliest, "amount": requested - safe_amount},
        ]
        if _safe(partial_entries):
            candidates.append(_plan_dict(
                "partial_payment", partial_entries, requested,
                desired_completion_date=deadline))

    # 3. Installments: one candidate per supplied payment option.  The
    #    schedule must come from the option itself, never be invented.
    if "installments" in user_accepts:
        for option in payment_options:
            option_id = str(option.get("payment_option_id", ""))
            start = str(option.get("start_date", request_date))[:10]
            interval = int(option.get("interval_days", 30) or 30)
            total_payable = float(option.get("total_payable", requested))
            per_payment = option.get("per_payment")
            if per_payment is None:
                per_payment = option.get("installment_amount")
            if per_payment is None:
                num_payments = int(option.get("num_payments", 1) or 1)
                per_payment = total_payable / num_payments if num_payments else 0
            else:
                per_payment = float(per_payment)
                num_payments = math.ceil(total_payable / per_payment)
            if per_payment <= 0 or num_payments <= 0:
                continue

            installment_entries = []
            start_d = _parse_date(start)
            for i in range(num_payments):
                pay_date = (start_d + timedelta(days=interval * i)).isoformat()
                if i == num_payments - 1:
                    # Final payment absorbs any rounding remainder so the
                    # schedule sums to exactly total_payable.
                    paid = sum(e["amount"] for e in installment_entries)
                    amount = round(total_payable - paid, 2)
                else:
                    amount = round(per_payment, 2)
                installment_entries.append({"date": pay_date, "amount": amount})

            if not installment_entries:
                continue
            if max(e["date"] for e in installment_entries) > deadline:
                continue
            if _safe(installment_entries):
                candidates.append(_plan_dict(
                    "installments", installment_entries, total_payable,
                    payment_option_id=option_id,
                    desired_completion_date=deadline))

    # 4. Wait: a single full payment on the earliest safe date.  If that
    #    date is today, the full_payment candidate already covers it, so a
    #    duplicate wait plan would add nothing.
    if (earliest is not None and earliest > request_date
            and "full_payment" in user_accepts):
        wait_entries = [{"date": earliest, "amount": requested}]
        if wait_entries[0]["date"] <= deadline and _safe(wait_entries):
            candidates.append(_plan_dict(
                "wait", wait_entries, requested,
                desired_completion_date=deadline))

    return candidates


def rank_plans(candidates, desired_completion_date):
    """Pick the winning plan with the PS tie-break order.

    The comparison is a tuple, so Python's sort applies the criteria in order:
    deadline first, then no spending changes (base plans never need them),
    cheapest total, earliest start, fewest payments, lowest option id.
    """
    if not candidates:
        return None

    def _sort_key(plan):
        # None payment_option_id sorts last: empty string sorts after digits.
        option_id = plan.get("payment_option_id")
        option_key = (1, "") if option_id is None else (0, str(option_id))
        return (
            0 if plan.get("completes_by_deadline") else 1,   # deadline met
            0,                                               # no spending changes
            float(plan.get("total_paid", 0.0)),
            str(plan.get("start_date") or "9999-12-31"),
            int(plan.get("num_payments", 0)),
            option_key,
        )

    return sorted(candidates, key=_sort_key)[0]


def optimize_spending_changes(request, timeline, starting_balance, min_balance):
    """Find the smallest set of flexible-spending cuts that makes the request safe.

    Preference order: no changes at all, then fewest changes, then the
    smallest reduction.  The search is deterministic: change sets are tried
    in ascending size, and within a size every combination is enumerated in a
    fixed order.
    """
    request_date = request["request_date"]
    requested = float(request["requested_amount"])
    plan = [{"date": request_date, "amount": requested}]

    def _safe_with(changes):
        modified = []
        stopped_ids = {c["event_id"] for c in changes if c["action"] == "stop"}
        reduced = {c["event_id"]: c["new_amount"]
                   for c in changes if c["action"] == "reduce_to"}
        for event in timeline:
            event_id = event.get("event_id")
            if event_id in stopped_ids:
                continue
            new_event = dict(event)
            if event_id in reduced:
                new_event["amount"] = reduced[event_id]
            modified.append(new_event)
        return oracle.is_safe(plan, modified, request_date,
                               starting_balance, min_balance)

    if _safe_with([]):
        return []

    # Only confirmed flexible events may be changed, sorted for determinism.
    flexible = sorted(
        (e for e in timeline
         if e.get("is_flexible") and str(e.get("status", "")).lower() == "confirmed"),
        key=lambda e: str(e.get("event_id", "")),
    )

    # Sizes 1..3: fewer changes always preferred over more.  For each set
    # of events we pick exactly ONE action per event, so itertools.product is
    # the right enumerator (it never mixes two actions for the same event).
    import itertools

    def _combinations(items, size):
        for base in itertools.combinations(items, size):
            yield base

    for size in (1, 2, 3):
        for base in _combinations(flexible, size):
            options = []
            for event in base:
                amount = float(event.get("amount", 0.0) or 0.0)
                actions = [{"action": "reduce_to",
                            "event_id": event.get("event_id"),
                            "new_amount": round(amount * step / 10.0, 2)}
                           for step in range(9, 0, -1)]
                actions.append({"action": "stop",
                                "event_id": event.get("event_id")})
                options.append(actions)
            for combo in itertools.product(*options):
                changes = list(combo)
                if _safe_with(changes):
                    return changes

    return []


def build_payment_plan_string(plan):
    """Format a plan as 'YYYY-MM-DD:amount|YYYY-MM-DD:amount' or 'none'."""
    if not plan:
        return "none"
    entries = plan.get("entries", plan) if isinstance(plan, dict) else plan
    if not entries:
        return "none"
    parts = ["{}:{}".format(e["date"], _format_amount(e["amount"]))
             for e in sorted(entries, key=lambda e: e["date"])]
    return "|".join(parts)


def build_spending_changes_string(changes):
    """Format changes as 'stop:event_14|reduce_to:event_21:100' or 'none'."""
    if not changes:
        return "none"
    parts = []
    for change in changes:
        if change["action"] == "stop":
            parts.append("stop:{}".format(change["event_id"]))
        else:
            parts.append("reduce_to:{}:{}".format(
                change["event_id"], _format_amount(change["new_amount"])))
    return "|".join(parts)


if __name__ == "__main__":
    # Hand-made scenarios only; importing this module runs nothing.
    request_date = "2026-01-01"
    deadline = "2026-03-01"

    # Scenario A: 45000 cash, no obligations, 20000 request, min 10000.
    request_a = {
        "request_id": "rA",
        "request_date": request_date,
        "requested_amount": 20000.0,
        "desired_completion_date": deadline,
        "allows_partial_payment": True,
    }
    candidates_a = generate_candidate_plans(
        request_a, [], 45000.0, 10000.0, [], ["full_payment", "partial_payment"])
    winner_a = rank_plans(candidates_a, deadline)
    print("Scenario A winner:", winner_a["method"] if winner_a else None)
    print("  plan:", build_payment_plan_string(winner_a))
    print("  expected: full_payment")

    # Scenario B: 30000 cash, salary 50000 on day 13, rent 15000 on day 20,
    # 25000 request, min 10000.  Full payment today is unsafe (only 5000
    # would remain), so the partial plan must step around the rent.
    salary_date = "2026-01-14"
    rent_date = "2026-01-20"
    timeline_b = [
        {
            "date": salary_date,
            "amount": 50000.0,
            "direction": "in",
            "kind": "one_time",
            "status": "confirmed",
            "is_essential": False,
            "is_flexible": False,
            "event_id": "event_salary",
        },
        {
            "date": rent_date,
            "amount": 15000.0,
            "direction": "out",
            "kind": "recurring",
            "status": "confirmed",
            "is_essential": True,
            "is_flexible": False,
            "event_id": "event_rent",
        },
    ]
    request_b = {
        "request_id": "rB",
        "request_date": request_date,
        "requested_amount": 25000.0,
        "desired_completion_date": deadline,
        "allows_partial_payment": True,
    }
    candidates_b = generate_candidate_plans(
        request_b, timeline_b, 30000.0, 10000.0, [],
        ["full_payment", "partial_payment", "installments"])
    winner_b = rank_plans(candidates_b, deadline)
    print("Scenario B winner:", winner_b["method"] if winner_b else None)
    print("  plan:", build_payment_plan_string(winner_b))
    print("  expected: partial_payment")