"""Deterministic 90-day cash-flow oracle.

This module is the source of truth for affordability math.  It never calls an
LLM, never reads files, and never uses randomness, so the same inputs always
produce the same numbers.
"""

from datetime import date, timedelta


def _parse_date(value: str) -> date:
    """Turn a YYYY-MM-DD string into a ``date``.

    The rest of the pipeline keeps dates as text.  Parsing here, in one helper,
    avoids mixing strings and date objects while we walk day by day.
    """
    return date.fromisoformat(str(value)[:10])


def _signed_cash(event: dict) -> float:
    """Return income as positive cash and expenses as negative cash."""
    amount = abs(float(event.get("amount", 0.0) or 0.0))
    direction = str(event.get("direction", "out")).lower()
    if direction == "in":
        return amount
    return -amount


def _counts_toward_cash(event: dict) -> bool:
    """Decide whether an event should move the simulated balance.

    The challenge is conservative: only cash that is already committed or
    confirmed may change the forecast.  That is why pending credits, failed
    rows, cancellations, and unrealized investments are ignored, while pending
    debits are reserved immediately.
    """
    status = str(event.get("status", "confirmed") or "confirmed").lower()
    kind = str(event.get("kind", "one_time") or "one_time").lower()
    direction = str(event.get("direction", "out") or "out").lower()

    if status in {"cancelled", "failed"}:
        return False
    if status == "unrealized" or "unrealized" in kind:
        return False
    # A pending credit is not cash until it settles.  A pending debit is.
    if status == "pending" and direction == "in" and kind != "pending_debit":
        return False
    return True


def simulate(
    timeline: list[dict],
    start_date: str,
    days: int = 90,
    extra_payments: list[dict] | None = None,
    starting_balance: float = 0.0,
) -> list[tuple[str, float]]:
    """Simulate the user's daily balance over the next ``days`` days.

    ``starting_balance`` is an explicit input so callers do not have to fake a
    timeline event for the opening cash.  Each returned pair is the end-of-day
    balance after that day's confirmed cash movements and any extra payments.
    """
    opening_date = _parse_date(start_date)
    extra_payments = extra_payments or []
    balance = float(starting_balance)
    daily_balances: list[tuple[str, float]] = []

    for offset in range(days):
        current = opening_date + timedelta(days=offset)
        current_str = current.isoformat()

        for event in timeline:
            if not _counts_toward_cash(event):
                continue
            if str(event.get("date", ""))[:10] != current_str:
                continue
            balance += _signed_cash(event)

        for payment in extra_payments:
            if str(payment.get("date", ""))[:10] != current_str:
                continue
            # Extra payments are candidate purchase cash-outflows.
            balance += _signed_cash(
                {
                    "amount": payment.get("amount", 0.0),
                    "direction": payment.get("direction", "out"),
                }
            )

        daily_balances.append((current_str, balance))

    return daily_balances


def is_safe(
    plan: list[dict],
    timeline: list[dict],
    start_date: str,
    starting_balance: float,
    min_balance: float,
    days: int = 90,
) -> bool:
    """Return True if ``plan`` never drops the balance below ``min_balance``.

    Safety is an end-of-day rule: after every simulated day, including the
    planned payments, cash must stay at or above the user's minimum.
    """
    extra_payments = [
        {
            "date": payment["date"],
            "amount": payment["amount"],
            "direction": "out",
            "kind": "one_time",
            "status": "confirmed",
            "is_essential": False,
            "is_flexible": False,
        }
        for payment in plan
    ]
    forecast = simulate(
        timeline,
        start_date,
        days=days,
        extra_payments=extra_payments,
        starting_balance=starting_balance,
    )
    return all(balance >= min_balance for _, balance in forecast)


def binary_search_safe_amount(
    request: dict,
    timeline: list[dict],
    starting_balance: float,
    min_balance: float,
    days: int = 90,
    tolerance: float = 1.0,
) -> float:
    """Return the largest amount that is safe to pay on ``request_date``.

    Binary search is used because checking every currency unit would be slow,
    but the safety test is monotonic: if amount X is unsafe, every larger
    amount is also unsafe.  The result is clipped to
    ``[0, requested_amount]``.
    """
    requested = max(0.0, float(request["requested_amount"]))
    request_date = request["request_date"]

    def _safe_today(amount: float) -> bool:
        return is_safe(
            [{"date": request_date, "amount": amount}],
            timeline,
            request_date,
            starting_balance,
            min_balance,
            days,
        )

    # If the full request is already safe, do not search below it.
    if requested == 0.0 or _safe_today(requested):
        return round(min(requested, float(request["requested_amount"])), 2)

    lo = 0.0
    hi = requested
    best = 0.0
    while hi - lo > tolerance:
        mid = (lo + hi) / 2.0
        if _safe_today(mid):
            best = mid
            lo = mid
        else:
            hi = mid

    clipped = min(max(best, 0.0), requested)
    return round(clipped, 2)


def earliest_full_payment_date(
    request: dict,
    timeline: list[dict],
    starting_balance: float,
    min_balance: float,
    days: int = 90,
) -> str | None:
    """Return the first date a single full payment stays safe.

    The search starts on ``request_date`` and walks forward one day at a time.
    Returning ``None`` means no full payment is safe inside the forecast
    window, which later becomes an empty ``earliest_date_for_full_payment``.
    """
    full_amount = float(request["requested_amount"])
    start = _parse_date(request["request_date"])

    for offset in range(days):
        pay_date = (start + timedelta(days=offset)).isoformat()
        plan = [{"date": pay_date, "amount": full_amount}]
        if is_safe(
            plan,
            timeline,
            request["request_date"],
            starting_balance,
            min_balance,
            days,
        ):
            return pay_date
    return None


if __name__ == "__main__":
    # Hand-made scenarios only.  Importing this module does not run them.
    start_date = "2026-01-01"
    salary_date = (_parse_date(start_date) + timedelta(days=13)).isoformat()
    rent_date = (_parse_date(start_date) + timedelta(days=20)).isoformat()

    shared_timeline = [
        {
            "date": salary_date,
            "amount": 50000.0,
            "direction": "in",
            "kind": "one_time",
            "status": "confirmed",
            "is_essential": False,
            "is_flexible": False,
        },
        {
            "date": rent_date,
            "amount": 15000.0,
            "direction": "out",
            "kind": "recurring",
            "status": "confirmed",
            "is_essential": True,
            "is_flexible": False,
        },
    ]

    print("Scenario A: 45000 cash, 60000 request, rent and salary ahead")
    request_a = {"request_date": start_date, "requested_amount": 60000}
    safe_a = binary_search_safe_amount(
        request_a, shared_timeline, 45000.0, 10000.0
    )
    print("  amount_safe_to_pay =", safe_a)
    print("  expected: value < 60000")

    print("Scenario B: same user, 20000 request")
    request_b = {"request_date": start_date, "requested_amount": 20000}
    safe_b = binary_search_safe_amount(
        request_b, shared_timeline, 45000.0, 10000.0
    )
    print("  amount_safe_to_pay =", safe_b)
    print("  expected: 20000")

    print("Scenario C: 5000 cash, no income, 10000 request")
    request_c = {"request_date": start_date, "requested_amount": 10000}
    earliest_c = earliest_full_payment_date(
        request_c, [], 5000.0, 1000.0
    )
    print("  earliest_full_payment_date =", earliest_c)
    print("  expected: None")
