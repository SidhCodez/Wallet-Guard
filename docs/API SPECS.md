# WalletGuard — Internal API Specification (Function Interface, Not REST)

Decision: no REST API. Project = ML training/batch pipeline (Prime Directive: only `output.csv` via `python run.py` graded). REST needs banned framework (FastAPI/Flask/Django). Instead: **internal Python function API** — same discipline as REST spec (clear contract per operation) but plain function calls, in-process, no HTTP/server/auth needed.

Same 10-field format as REST, reinterpreted for function calls:
1. Call type (script/import) → 2. Function signature → 3. Purpose → 4. Auth → 5. Params → 6. Input data → 7. Example call → 8. Example return → 9. Possible errors → 10. Exit/return code

---

## Endpoint 1 — Train Model

1. **Call type:** CLI script
2. **Signature:** `python train.py [--config config.json]`
3. **Purpose:** load dataset, engineer features, train classifier + regressor, save artifacts to `models/`
4. **Auth:** none (local execution); needs `ANTHROPIC_API_KEY` in `.env` if any LLM-assisted feature extraction used during training
5. **Params:** `--config` (optional, path to config.json, default `./config.json`)
6. **Input data:** `dataset/sample_requests.csv` (labeled), `dataset/financial_*.csv`
7. **Example call:**
   ```bash
   python train.py --config config.json
   ```
8. **Example return (stdout):**
   ```
   Loaded 240 labeled samples.
   Cross-val accuracy (classifier): 0.81
   Cross-val MAE (regressor): 312.4
   Saved: models/affordability_clf.pkl
   Saved: models/safe_amount_reg.pkl
   ```
9. **Possible errors:** `FileNotFoundError` (missing dataset file), `ValueError` (empty/malformed labels), low-sample warning if `sample_requests.csv` too small for stable CV
10. **Exit code:** 0 success, 1 on any load/training failure (script halts, prints reason)

---

## Endpoint 2 — Run Inference (Main Deliverable)

1. **Call type:** CLI script
2. **Signature:** `python run.py [--config config.json]`
3. **Purpose:** load trained models, process every row in `requests.csv`, write `output.csv`
4. **Auth:** none locally; `ANTHROPIC_API_KEY` required in `.env` for vision/message calls
5. **Params:** `--config` (optional)
6. **Input data:** all `dataset/*.csv`, `models/*.pkl`
7. **Example call:**
   ```bash
   python run.py
   ```
8. **Example return (stdout + file):**
   ```
   Processing 50 requests...
   Resolved 4 blank amounts via vision.
   Applied 2 message amendments.
   Rule validator corrected 3 predictions.
   Wrote output.csv (50 rows).
   Wrote evaluation/usage_report.md.
   ```
9. **Possible errors:** missing model artifact (`FileNotFoundError` → tell user run `train.py` first), missing API key (fallback: skip vision/message calls, log warning, treat unresolved amounts as flagged/skipped per rules), malformed CSV row (skip + log, don't crash whole run)
10. **Exit code:** 0 success (even w/ some rows flagged), 1 only on unrecoverable failure (e.g. can't write output.csv)

---

## Endpoint 3 — Evaluate Single Request (Function, used by Streamlit demo)

1. **Call type:** Python function import
2. **Signature:** `evaluate_request(request_id: str) -> dict`  (in `src/decision_engine_entry.py` or similar)
3. **Purpose:** run full pipeline logic for one request only — used for interactive demo, not batch grading
4. **Auth:** none (in-process call); relies on same `.env` key as run.py
5. **Params:** `request_id: str` — must exist in loaded `requests.csv`
6. **Input data:** in-memory DataFrames (already loaded once at app/process start)
7. **Example call:**
   ```python
   from src.decision_engine_entry import evaluate_request
   result = evaluate_request("req_101")
   ```
8. **Example return:**
   ```python
   {
     "request_id": "req_101",
     "amount_safe_to_pay": 20000.00,
     "affordability_status": "affordable_with_plan",
     "recommended_payment_method": "partial_payment",
     "payment_plan": "2026-09-12:20000|2026-10-01:40000",
     "earliest_date_for_full_payment": "2026-10-01",
     "spending_changes_needed": "none",
     "decision_explanation": "Partial payment keeps buffer above min balance until rent clears."
   }
   ```
9. **Possible errors:** `KeyError`/`ValueError` if `request_id` not found → return `{"error": "request_id not found"}` instead of raising (demo-friendly), model-not-loaded → raise clear `RuntimeError("run train.py first")`
10. **Return convention:** always returns `dict`; `"error"` key present only on failure, absent on success (caller checks `"error" in result`)

---

## Endpoint 4 — Get All Predictions (Function, for Streamlit table view)

1. **Call type:** Python function import
2. **Signature:** `get_all_predictions() -> pandas.DataFrame`
3. **Purpose:** return full generated `output.csv` as DataFrame for display/inspection
4. **Auth:** none
5. **Params:** none
6. **Input data:** `output.csv` (must already exist, i.e. `run.py` already ran)
7. **Example call:**
   ```python
   from src.decision_engine_entry import get_all_predictions
   df = get_all_predictions()
   ```
8. **Example return:** pandas DataFrame, 8 columns matching output.csv schema, one row per request
9. **Possible errors:** `FileNotFoundError` if `output.csv` missing → caller (e.g. Streamlit) shows "Run pipeline first" message instead of crashing
10. **Return convention:** empty DataFrame w/ correct columns if file exists but has zero rows (never `None`)

---

## Endpoint 5 — Get Usage Report (Function, for Streamlit usage tab)

1. **Call type:** Python function import
2. **Signature:** `get_usage_summary() -> dict`
3. **Purpose:** return parsed token/cost totals for display (backs `evaluation/usage_report.md`)
4. **Auth:** none
5. **Params:** none
6. **Input data:** internal usage log (written during `run.py`/`train.py` execution, e.g. `evaluation/usage_log.json` raw data behind the markdown report)
7. **Example call:**
   ```python
   from src.usage_tracker import get_usage_summary
   summary = get_usage_summary()
   ```
8. **Example return:**
   ```python
   {
     "total_calls": 12,
     "total_input_tokens": 8400,
     "total_output_tokens": 950,
     "total_cost_usd": 0.14,
     "by_model": {
       "claude-sonnet-4-6": {"calls": 12, "cost_usd": 0.14}
     }
   }
   ```
9. **Possible errors:** returns all-zero dict if no calls logged yet (no exception)
10. **Return convention:** always dict, zero-valued default if nothing logged

---

## Endpoint 6 — Run Oracle on One Request

1. **Call type:** Python function import
2. **Signature:** `run_oracle(request_id: str) -> dict`
3. **Purpose:** expose the deterministic simulator's raw output for debugging and testing, independent of any ML/LLM helper
4. **Auth:** none (in-process call)
5. **Params:** `request_id: str` — must exist in loaded `requests.csv`
6. **Input data:** in-memory timeline/forecast for the request's user (already loaded once at process start)
7. **Example call:**
   ```python
   from src.oracle import run_oracle
   result = run_oracle("req_101")
   ```
8. **Example return:**
   ```python
   {
     "amount_safe_to_pay": 20000.00,
     "earliest_date": "2026-10-01",
     "min_balance_90d": 8500.00,
     "candidate_plans": [ {"method": "partial_payment", "plan": "2026-09-12:20000|2026-10-01:40000"} ],
     "spending_candidates": []
   }
   ```
9. **Possible errors:** `KeyError` if `request_id` not found; `RuntimeError` if dataset/timeline not loaded yet
10. **Return convention:** always a `dict` with all five keys present; empty lists (not `None`) when there are no candidates

---

## Endpoint 7 — Generate Synthetic Data

1. **Call type:** CLI script
2. **Signature:** `python -m src.synthetic_data_generator --n 5000 --seed 42 --out data/synthetic_train.csv`
3. **Purpose:** create labeled training scenarios using the oracle, for training the optional ML accelerators
4. **Auth:** none (local execution, no LLM calls involved — labels come from the oracle only)
5. **Params:** `--n` (scenario count, default 5000), `--seed` (random seed, default 42), `--out` (output path, default `data/synthetic_train.csv`)
6. **Input data:** none required beyond code (scenarios are randomly generated, not read from `dataset/`)
7. **Example call:**
   ```bash
   python -m src.synthetic_data_generator --n 5000 --seed 42 --out data/synthetic_train.csv
   ```
8. **Example return (stdout):**
   ```
   Generated 5000 scenarios (seed=42).
   Label distribution: affordable_now=1180, affordable_with_plan=2340, later=980, not_affordable=500.
   Saved: data/synthetic_train.csv
   ```
9. **Possible errors:** `FileNotFoundError` if an output directory in `--out` doesn't exist
10. **Exit code:** 0 success, 1 on any generation/write failure

---

## Endpoint 8 — Verify Output

1. **Call type:** CLI script
2. **Signature:** `python -m src.verifier --input output.csv --strict`
3. **Purpose:** run all hard-rule checks on a produced `output.csv` before submission
4. **Auth:** none
5. **Params:** `--input` (path to CSV to check, default `output.csv`), `--strict` (exit non-zero on any failed check)
6. **Input data:** the `output.csv` file plus `dataset/request_payment_options.csv` and the per-request timelines (for the safety invariant check)
7. **Example call:**
   ```bash
   python -m src.verifier --input output.csv --strict
   ```
8. **Example return (stdout):**
   ```
   Checking 50 rows...
   [PASS] schema_regex (50/50)
   [PASS] plan_sums_match (50/50)
   [PASS] partial_plan_two_payments (12/12)
   [PASS] installments_match_options (8/8)
   [PASS] safety_invariant (50/50)
   [PASS] no_stop_reduce_same_event (50/50)
   All checks passed.
   ```
9. **Possible errors:** `FileNotFoundError` if `--input` missing; any failed check prints `[FAIL]` with the offending `request_id`(s)
10. **Exit code:** 0 if all checks pass, 1 if any check fails (checks run: schema regex, plan sums, partial plan exactly 2 payments, installments match `request_payment_options.csv`, 90-day safety invariant, stop/reduce never on the same event)

---

## Why No REST Layer
- Grading = local script run (`python run.py` → `output.csv`), never a live HTTP call
- Adding FastAPI/Flask = banned framework, extra moving part, extra failure surface, zero grading benefit
- Streamlit (if built) calls these same functions **in-process** — no HTTP round-trip, no serialization overhead, no server to keep alive
- If team later wants a real hosted API (post-hackathon), swap this doc for genuine REST spec then — not needed now

## Consistency Rules (mirrors REST discipline)
- Every function returns same shape every time (dict or DataFrame), never sometimes-dict-sometimes-string
- Errors returned as data (`{"error": ...}`) for demo-facing functions, exceptions raised only for genuine setup problems (missing model file) — keeps Streamlit UI from crashing on bad input
- No function silently returns `None` on failure — always explicit error signal
- Every new function must have a deterministic fallback (a code path that works even if any optional ML/LLM helper is unavailable)
- Every function that touches money must be pure and unit-tested (no hidden state, no side effects, same input → same output)
- No function may call an LLM and use the result as a final number — LLM output only ever feeds the oracle/rule pipeline, never stands in as the answer itself
