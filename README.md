# WalletGuard

> An AI-powered financial decision agent that answers “Can I afford this?” with a 90-day cash-flow forecast — not a glance at today’s balance.

---

## Table of Contents

- [What Is WalletGuard?](#what-is-walletguard)
- [The Problem](#the-problem)
- [The Solution](#the-solution)
- [How It Works](#how-it-works)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Tech Stack](#tech-stack)
- [Installation](#installation)
- [Usage](#usage)
- [Input & Output](#input--output)
- [Design Decisions](#design-decisions)
- [Domain Classification](#domain-classification)
- [Plain-English Walkthrough](#plain-english-walkthrough)
- [Known Limitations](#known-limitations)
- [Future Improvements](#future-improvements)
- [Judge Q&A](#judge-qa)
- [Deliverables](#deliverables)
- [Author](#author)
- [Final Word](#final-word)

---

## What Is WalletGuard?

WalletGuard is the submission for the **HackerRank Orchestrate (September 2026)** challenge **Buy or Wait?**

For every purchase or payment request in `dataset/requests.csv`, it decides whether the user should:

- pay in full today,
- pay part today and the rest later,
- use a seller installment option,
- wait until a later date, or
- not proceed.

The recommendation is personal. Two users with the same balance can get different answers because WalletGuard also looks at upcoming bills, confirmed income, payment preferences, and the minimum cash the user wants to keep.

**This pipeline is fully rule-based.** No machine-learning model was trained. No LLM is called at runtime. Every number comes from a deterministic 90-day simulator.

---

## The Problem

A bank-app balance is not a “safe to spend” number.

People forget rent that lands in 12 days, a pending debit that has not cleared, or a salary that has not settled. They mix currencies. They accept an installment plan that the seller offered, not the plan that keeps them above their own minimum balance.

The challenge asks for a system that:

1. Reconstructs each user’s finances from structured CSVs.
2. Forecasts the next 90 days conservatively.
3. Recommends a payment method that never drops the balance below `minimum_balance_to_keep`.
4. Writes one row per request to `output.csv` in an exact schema.

Messages and images exist in the dataset as supporting evidence. **This submission does not parse them yet** — that is future work.

---

## The Solution

A batch Python job that:

1. Loads every CSV in `dataset/`.
2. Builds a per-user cash timeline (confirmed events + reserved pending debits).
3. Converts foreign amounts with the dated rates in `exchange_rates.csv`.
4. Simulates daily balances for 90 days.
5. Binary-searches the largest amount that is safe to pay today.
6. Finds the earliest date a single full payment would be safe.
7. Generates candidate plans (full / partial / installments / wait), ranks them with the challenge’s tie-break order, and writes a schema-exact row.
8. Re-checks every row with a verifier before anyone should submit.

The source of truth is the simulator (`code/src/oracle.py`). The plan engine never invents an installment schedule. The verifier never lets an invalid row through unnoticed.

---

## How It Works

### High-level flow

```text
 dataset/*.csv
        |
        v
 +------------------+
 |  data_loader.py  |   raw DataFrames, no joins, no date parsing
 +------------------+
        |
        v
 +------------------+
 |   currency.py    |   dated FX lookup (same-currency = no-op)
 +------------------+
        |
        v
 +------------------+     90-day daily balances
 |    oracle.py     |---- amount_safe_to_pay (binary search)
 |                  |---- earliest full-payment date
 +------------------+
        |
        v
 +------------------+
 |  plan_engine.py  |   candidates -> rank -> payment_plan string
 +------------------+
        |
        v
 +------------------+
 |     main.py      |   one output row per request
 +------------------+
        |
        v
 +------------------+
 |   verifier.py    |   13 hard checks; FAIL blocks submission
 +------------------+
        |
        v
     output.csv
```

### Step-by-step

1. **Load.** `load_all_datasets("../dataset")` reads every top-level CSV into a dict keyed by filename stem. Nothing is joined or type-cast here, so later stages see the raw values.
2. **Currency.** Foreign-currency events are converted with `convert(amount, from, to, date, rates_df)`. Same-currency amounts pass through unchanged. A missing rate raises `ValueError` instead of guessing.
3. **Simulate.** `simulate(...)` walks day by day for 90 days. Pending credits, cancelled/failed rows, and unrealized investments are ignored. Pending debits are reserved. Confirmed salary counts on its settlement date.
4. **Safe amount.** `binary_search_safe_amount` finds the largest amount payable on `request_date` that still keeps every end-of-day balance at or above `minimum_balance_to_keep`. The result is clipped to `[0, requested_amount]`.
5. **Earliest date.** `earliest_full_payment_date` tests a single full payment on each day of the window and returns the first safe date, or empty if none exists.
6. **Generate plans.** `generate_candidate_plans` builds full, partial (exactly two payments), installment (copied from `request_payment_options.csv`), and wait candidates. Each candidate must pass `is_safe` and finish on or before `desired_completion_date`.
7. **Rank plans.** `rank_plans` applies the challenge order: complete by the deadline, no spending changes, lowest total paid, earlier start, fewer payments, lowest `payment_option_id`.
8. **Verify.** `verify_output` re-reads `output.csv` and `requests.csv` and runs 13 schema, math, and coherence checks. A FAIL means do not submit.

---

## Architecture

### Layered design

```text
 Layer 0   data_loader + currency          raw tables, dated FX
 Layer 1   main.py timeline builder        per-user cash events
 Layer 2   oracle (simulator)              SOURCE OF TRUTH
 Layer 3   plan_engine (rules + ranking)   eligibility + tie-breaks
 Layer 4   verifier                        blocks unsafe / invalid rows
 Layer 5   (not in this build)             ML accelerators
 Layer 6   (not in this build)             LLM vision + message parse
```

Layers 5 and 6 can stay empty and the system still produces a valid `output.csv`. That is intentional.

### Design principles

| Principle | What it means here |
|---|---|
| Deterministic core | Same CSVs in → same `output.csv` out. No randomness, no model weights. |
| Separation of concerns | Loading, FX, simulation, ranking, and verification live in separate modules. |
| Rule-first | Affordability is decided by Python `if`/`for` over a forecast, not by a model vote. |
| Fails safely | A per-row `try/except` in `main.py` writes a `not_recommended` fallback instead of crashing the batch. The verifier then flags remaining schema problems. |

---

## Project Structure

```text
hackerrank-orchestrate-september26/
├── AGENTS.md                      # challenge contract for coding agents
├── CLAUDE.md                      # extra project rules
├── README.md                      # this file
├── problem_statement.md           # full participant-facing spec
├── requirements.txt
├── output.csv                     # 250 predictions (written by main.py)
├── code/
│   ├── main.py                    # orchestrator
│   ├── src/
│   │   ├── data_loader.py         # CSV -> DataFrame dict
│   │   ├── currency.py            # dated FX conversion
│   │   ├── oracle.py              # 90-day simulator + binary search
│   │   ├── plan_engine.py         # candidates, ranking, string builders
│   │   └── verifier.py            # pre-submission safety gate
│   ├── evaluation/
│   │   └── usage_report.md        # token/cost report (no runtime LLM calls)
│   └── tests/                     # reserved; no unit tests shipped yet
├── dataset/                       # READ-ONLY challenge data
│   ├── requests.csv               # 250 rows to predict
│   ├── sample_requests.csv        # public examples (format only)
│   ├── financial_profiles.csv
│   ├── financial_events.csv
│   ├── exchange_rates.csv
│   ├── request_payment_options.csv
│   ├── messages.csv               # not consumed in this build
│   ├── images.csv                 # not consumed in this build
│   └── media/images/
└── docs/                          # design notes (PRD, TRD, architecture)
```

---

## Tech Stack

| Layer | Choice | Notes |
|---|---|---|
| Language | Python 3.10+ | Type hints (`str \| None`), stdlib `datetime` / `math`. |
| Data | pandas | CSV load, per-user filters, `output.csv` write. |
| Computation | numpy (available) + pure Python | The oracle does **not** use pandas; daily simulation is plain loops. |
| Testing | `code/src/verifier.py` | 13 hard checks on the full `output.csv`. No pytest suite is shipped yet. |
| Report | `code/evaluation/usage_report.md` | Required submission artifact. This run made **zero** model API calls. |

`requirements.txt` also lists scikit-learn, XGBoost, and the Anthropic SDK. **They are unused at runtime.** They are leftovers for the optional ML / vision layers that this build does not implement.

---

## Installation

### Requirements

- Python 3.10 or newer
- `pandas`
- `numpy`

No database, no Docker, no API key.

### Setup

```bash
git clone <this-repo>
cd hackerrank-orchestrate-september26

# Preferred: a virtual environment (avoids PEP 668 "externally managed" errors)
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
python3 -m pip install --upgrade pip
python3 -m pip install pandas numpy
```

PEP 668 fallback if you cannot create a venv and `pip` refuses a system install:

```bash
python3 -m pip install --user pandas numpy
# last resort only:
python3 -m pip install --break-system-packages pandas numpy
```

### Verify the install

```bash
python3 -c "import pandas, numpy; print(pandas.__version__, numpy.__version__)"
```

---

## Usage

Run everything from the `code/` directory so `from src.X import Y` resolves.

### Run the pipeline

```bash
cd code
python3 main.py
```

This reads `../dataset/`, writes `../output.csv`, and prints a status / method breakdown.

### Expected output (this build)

```text
Status breakdown:
  affordable_now: 138 (55.2%)
  not_affordable: 96 (38.4%)
  affordable_later: 10 (4.0%)
  affordable_with_plan: 6 (2.4%)
Method breakdown:
  full_payment: 138
  not_recommended: 96
  wait: 10
  installments: 5
  partial_payment: 1
Total rows processed: 250
```

Counts can change if the timeline or ranking rules change. They must always sum to 250.

### Verify before submitting

```bash
cd code
python3 src/verifier.py
```

Expected:

```text
PASS — all rows verified
```

Exit code `0` means proceed. Exit code `1` prints the first 20 errors — fix them before packaging `code.zip`.

---

## Input & Output

### Input (the files this build actually reads)

| File | Role | Key columns used |
|---|---|---|
| `requests.csv` | One row to predict | `request_id`, `user_id`, `request_date`, `requested_amount`, `desired_completion_date`, `allows_partial_payment` |
| `financial_profiles.csv` | Opening cash + preferences | `user_id`, `home_currency`, `current_available_balance`, `minimum_balance_to_keep`, `payment_methods_user_will_consider` |
| `financial_events.csv` | Cash-flow evidence | `event_id`, `user_id`, `direction`, `amount`, `currency`, `event_date`, `settlement_date`, `status`, `flexibility` |
| `exchange_rates.csv` | Dated FX | `rate_date`, `from_currency`, `to_currency`, `rate` |
| `request_payment_options.csv` | Installment schedules | `payment_option_id`, `request_id`, `payment_amount`, `number_of_payments`, `first_payment_date`, `payment_frequency_days`, `total_payable_amount` |

`messages.csv` and `images.csv` are in the dataset. **This build does not read them.**

### Output columns (`output.csv`)

| Column | Meaning |
|---|---|
| `request_id` | The request being answered |
| `amount_safe_to_pay` | Largest amount safe on `request_date`, in `[0, requested_amount]` |
| `affordability_status` | `affordable_now` / `affordable_with_plan` / `affordable_later` / `not_affordable` |
| `recommended_payment_method` | `full_payment` / `partial_payment` / `installments` / `wait` / `not_recommended` |
| `payment_plan` | `YYYY-MM-DD:amount` entries joined by `\|`, or `none` |
| `earliest_date_for_full_payment` | First date a single full payment is safe; blank if never |
| `spending_changes_needed` | Up to three `stop:` / `reduce_to:` actions, or `none` |
| `decision_explanation` | Short, grounded reason |

### Example row (real output)

Input (`request_26`): family transfer of `15656000` due `2025-10-07`.

```text
request_id,amount_safe_to_pay,affordability_status,recommended_payment_method,payment_plan,earliest_date_for_full_payment,spending_changes_needed,decision_explanation
request_26,15656000.0,affordable_now,full_payment,2025-08-03:15656000.00,2025-08-03,none,Full payment is safe today and keeps balance above minimum.
```

---

## Design Decisions

### Why deterministic, not ML?

The grader checks exact schema, exact plan arithmetic, and a 90-day safety invariant. A classifier can output `affordable_now` on a row whose forecast already breaches the minimum. A regressor can output a number outside `[0, requested_amount]`.

The oracle computes the answer. If a model is added later, it may only *propose*; the oracle still *decides*. **No model was trained for this submission.**

### Why no LLM at runtime?

LLMs are useful for reading messy text and images. They are a poor calculator. This build keeps money math in Python so a rerun on the same CSVs always produces the same `output.csv`, with no API key and no token bill.

Vision extraction and message parsing are the right places to add an LLM later. They are **not implemented**.

### Why the verifier layer?

`main.py` has a per-row fallback, but a fallback is still a row. The verifier is a second, independent pass over the written file. It does not trust the pipeline that produced the CSV. If it prints `FAIL`, the zip should not be submitted.

---

## Domain Classification

| Dimension | Classification |
|---|---|
| Industry | Personal finance / consumer banking |
| Segment | Affordability and cash-flow decisioning |
| Product Category | Batch decision engine (not a live banking app) |
| Technology | Deterministic rules + dated FX; no trained ML, no runtime LLM |
| Data Types | Structured CSVs (profiles, events, rates, payment options). Unstructured messages/images are present but unused. |
| End User | An individual asking “can I afford this purchase or transfer?” |
| Potential Buyers | Digital banks, neobanks, BNPL providers, personal-finance apps that need a conservative “pay / wait / don’t” answer |

**One-line answer:** WalletGuard is a conservative, offline affordability engine for consumer payments — a simulator with a rule layer, not a chatbot and not a credit model.

---

## Plain-English Walkthrough

Meet **Priya**. She has **IDR 45,000,000** available, wants to keep **IDR 10,000,000** in the account, and is looking at a **IDR 20,000,000** purchase today. Rent of IDR 8,000,000 hits in 20 days. Confirmed salary of IDR 25,000,000 lands in 13 days. She will consider full payment, partial payment, and installments.

This is a **fictional** walkthrough of the five decision steps. It is not a row from the hidden labels.

1. **Load her world.** Profile + events + any installment options for this request. Opening cash is 45,000,000. Minimum to keep is 10,000,000.
2. **Build the timeline.** Salary on day 13 (credit, confirmed). Rent on day 20 (debit, essential). Pending credits, if any, are ignored. Pending debits are reserved.
3. **Ask the oracle.** Paying 20,000,000 today leaves 25,000,000. After salary and rent the balance stays above 10,000,000, so `amount_safe_to_pay = 20000000` and `earliest_date_for_full_payment` is today.
4. **Generate and rank plans.** Full payment is eligible, safe, and meets the deadline. It wins the tie-break (deadline met, no spending changes, lowest total, earliest start, fewest payments).
5. **Write the row and verify.**

Fictional output row:

```text
request_id,amount_safe_to_pay,affordability_status,recommended_payment_method,payment_plan,earliest_date_for_full_payment,spending_changes_needed,decision_explanation
request_priya,20000000.00,affordable_now,full_payment,2026-01-01:20000000.00,2026-01-01,none,Full payment is safe today and keeps balance above minimum.
```

If the purchase had been 40,000,000, paying today would leave 5,000,000 — below her minimum. The oracle would return a smaller `amount_safe_to_pay`, and the plan engine would look for a partial split, a seller installment option, or a wait date after salary lands.

---

## Known Limitations

Be precise about what this build does **not** do:

1. **Vision extraction is not implemented.** Events with a blank `amount` are skipped. They are never treated as zero, and they are never filled from `dataset/media/images/`.
2. **Message parsing is not implemented.** Cancellations, confirmations, or date changes that exist only in `messages.csv` are not applied.
3. **No trained ML model.** There is no classifier, ranker, or regressor. `models/` is unused.
4. **Conflict resolver is inline only.** Status filters (skip cancelled / failed / unrealized) live in the timeline builder and the oracle. There is no separate `conflict_resolver.py` with the full four-step priority order.
5. **Spending optimizer is basic.** It only considers confirmed flexible events, at most three changes, 10% reduction steps, and one action per event. It is not used to flip a `not_affordable` row into a recommended plan in `main.py` — it currently only populates `spending_changes_needed` on the not-affordable path.

Recurrence is also conservative: scheduled future rows in `financial_events.csv` are used as-is. The pipeline does **not** invent extra monthly copies of a historical rent row, because that would double-count commitments the dataset already listed.

---

## Future Improvements

In priority order:

1. **Blank-amount vision extraction** — call a vision model only for events whose `amount` is empty, cache by `image_id`, and feed the number into the existing oracle. Do not let the model write `output.csv`.
2. **Trusted-as-data message parser** — classify cancel / confirm / delay / amend, apply the result through a real conflict resolver, ignore any instructions embedded in the message text.
3. **History-backed recurrence** — expand a series only when past events actually show a stable monthly (or weekly) pattern.
4. **Full conflict resolver** — explicit cancellation > newer same-source record > settled over estimate > safer interpretation, with a logged reason string.
5. **Spending-change re-forecast** — after a valid change set, re-run plan generation so a request can move from `not_affordable` to `affordable_with_plan` when the rules allow it.
6. **Unit tests** — `tests/test_oracle_safety.py`, `tests/test_currency.py`, `tests/test_plan_engine.py` around the three `__main__` scenario blocks that already exist.
7. **Optional ML ranker** — train only on synthetic labels produced by the oracle, and keep the oracle as the override.

---

## Judge Q&A

**Q1. Did you train a model?**
No. The submission is a deterministic rule engine. scikit-learn and XGBoost appear in `requirements.txt` as optional future dependencies and are not imported by `main.py` or any `src/` module that runs at inference.

**Q2. How do you guarantee the 90-day safety invariant?**
`oracle.is_safe` resimulates the recommended payments on top of the user’s timeline and requires every end-of-day balance to stay at or above `minimum_balance_to_keep`. Candidate plans that fail this test never enter the ranker.

**Q3. Why is `not_affordable` so common (~38%)?**
The simulator is conservative: pending credits do not count, pending debits do, blank amounts are skipped rather than guessed, and no extra future salary is invented. If a full payment, a two-part partial, an option-matched installment, and a wait date all fail, the honest answer is `not_recommended`.

**Q4. How do installment plans stay honest?**
They are copied from `request_payment_options.csv` (`first_payment_date`, `payment_frequency_days`, `number_of_payments`, `total_payable_amount`). The last installment absorbs rounding so the schedule sums to `total_payable`. The verifier rebuilds that schedule independently and rejects a mismatch.

**Q5. What happens on a processing error?**
That one request is logged to stderr and replaced with a schema-valid fallback (`amount_safe_to_pay = 0`, `not_affordable` / `not_recommended`, plan `none`). The remaining 249 rows still run. The batch does not crash.

**Q6. Why ignore messages and images?**
They are untrusted evidence. Parsing them well needs a carefully prompted LLM plus a conflict resolver. Shipping a keyword hack would be worse than shipping a clean tabular baseline. Both are listed as future work, not as features.

**Q7. How is `wait` different from `affordable_with_plan`?**
`wait` means no payment today. Status is `affordable_later`, `payment_plan` is `none`, and `earliest_date_for_full_payment` holds the future date. A partial or installment plan that actually schedules payments is `affordable_with_plan`.

**Q8. Can I rerun this without an API key?**
Yes. `cd code && python3 main.py` then `python3 src/verifier.py`. There are no network calls and no secrets.

---

## Deliverables

| File | What it is |
|---|---|
| `code.zip` | Runnable package: `code/`, `README.md`, `requirements.txt`, `evaluation/usage_report.md`, this design. No `.env`, no API keys. |
| `output.csv` | 250 prediction rows at the repository root, one per `dataset/requests.csv` row, exact column order. |
| `log.txt` | Chat transcript required by `AGENTS.md` §5. Gitignored; upload separately as `chat_transcript`. |

---

## Author

Solo participant, HackerRank Orchestrate — September 2026, challenge **Buy or Wait?**

This is a personal submission. The participant is the author of the code in `code/`.

---

## Final Word

Safe-to-spend is a forecast, not a balance.

WalletGuard would rather say wait — or say no — than let a purchase silently break the next ninety days.
