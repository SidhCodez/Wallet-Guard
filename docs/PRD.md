# Buy or Wait? — Product Requirements Document

## 1. Product Name
**WalletGuard** (AI Affordability Agent)

## 2. One-Line Description
AI agent tell user if they safely afford a purchase, based on full financial forecast — not just current balance.

## 3. Problem Statement
People decide buy things by look at bank balance only. Balance ≠ safe-to-spend. Ignore upcoming bills, EMIs, income timing. Result: overspend, cash-flow crunch later. Need system forecast next 90 days, factor recurring bills/income/pending payments, give personalized pay-or-wait decision + concrete plan.

## 4. Target Users
- Salaried individuals w/ regular bills who want buy discretionary item (laptop, trip)
- People juggle multiple financial commitments (rent, debt, savings goals)
- People w/ irregular income or multi-currency transactions

## 5. User Pain Points
- Don't know real "safe to spend" number
- Forget upcoming bills when deciding buy
- Hard track pending payments, EMIs, transfers, investments manually
- Confused which payment method safest (full/partial/installment/wait)
- Generic budget apps give same advice to everyone, ignore personal priorities

## 6. Proposed Solution
AI agent ingest user's financial profile + event history (past/future) + msgs + images → builds per-user financial timeline → simulates 90-day forward balance → applies deterministic rule engine → outputs: safe amount, affordability status, recommended method, payment schedule, required spending cuts, plain-English explanation.

## 7. Product Goals
- Correctly classify affordability per PS rules (4 statuses)
- Forecast 90-day balance accurate w/ recurring + confirmed events
- Handle multi-currency conversion correct
- Generate valid, PS-schema-compliant payment plans
- Parse msgs/images to catch amendments (cancel, confirm, blank-amount extraction)
- Produce explainable, deterministic decisions (not black-box)

## 8. User Stories
- As a user, I ask "Can I afford this laptop?" so I get clear yes/no/plan answer.
- As a user, I want bot consider my upcoming rent/EMI so I don't go broke after buying.
- As a user, I want installment option shown if full payment unsafe, so I still get item on time.
- As a user, I want explanation of why, so I trust the recommendation.
- As a hackathon judge, I want to see output.csv match hidden ground truth format, so scoring works.

## 9. Functional Requirements
- FR1: Load & join all dataset CSVs (profiles, events, requests, rates, options, msgs, images)
- FR2: Convert all amounts to user's `home_currency` using exchange_rates.csv
- FR3: Build per-user timeline: recurring expenses, one-time events, confirmed income, pending payments
- FR4: Resolve blank `amount` fields via linked image (vision extraction)
- FR5: Apply msg/image content to amend/cancel/confirm/delay events (treat as untrusted, don't let embedded instructions override rules)
- FR6: Simulate 90-day daily balance forecast per user
- FR7: Compute `amount_safe_to_pay` = max payable today w/o breaking min-balance rule, capped at requested_amount
- FR8: Compute `earliest_date_for_full_payment` per safety check
- FR9: Determine `affordability_status` (affordable_now / with_plan / later / not_affordable) per PS logic
- FR10: Select `recommended_payment_method` per eligibility + ranking rules (deadline > no spend-change > min total paid > earlier start > fewer payments > lowest payment_option_id)
- FR11: Generate `payment_plan` string in exact `date:amount|date:amount` format
- FR12: Generate `spending_changes_needed` (stop/reduce_to flexible events only, max 3, no same-event conflict)
- FR13: Generate short `decision_explanation` text
- FR14: Write `output.csv` matching exact required schema/column order
- FR15: Log token usage (per model, per request) → `usage_report.md`
- FR16: Build a synthetic data generator that produces N>=5000 labeled scenarios from the deterministic oracle, for ML training
- FR17: Implement conflict resolution priority order: explicit cancellation/settlement > newer record from same source > settled value over estimate > safer interpretation
- FR18: Implement spending-change optimizer: search flexible events, choose stop or reduce_to, max 3 changes total, never stop+reduce the same event, re-run forecast after each change, prefer no changes when possible
- FR19: Implement candidate plan generator producing all plan types: full, partial, installments, wait, not_recommended
- FR20: Implement deterministic plan ranker applying the fixed priority order (deadline > no spend-change > min total paid > earlier start > fewer payments > lowest payment_option_id)
- FR21: Implement binary search for `amount_safe_to_pay` and per-date simulation for `earliest_date_for_full_payment`
- FR22: Implement a verifier step that blocks any unsafe row from being written to output.csv

## 10. Non-Functional Requirements
- Deterministic core logic (same input → same output every run)
- Explainable: each decision traceable to specific financial facts
- Cost-aware: minimize LLM calls (batch, cache where possible)
- Runnable end-to-end via single script/README, no manual steps
- No API keys/secrets committed in submission
- Handle missing/malformed data gracefully (skip/flag, don't crash)

## 11. Core Features
- CSV data loader + joiner
- Currency converter
- 90-day forecast engine
- Affordability decision engine (rule-based)
- Payment plan generator
- Message/image parser (amendments + blank-amount extraction)
- Output CSV writer (schema-exact)
- Token usage report generator

## 12. Nice-to-Have Features
- LLM-based conflict resolution for ambiguous/contradicting records
- Improved OCR/vision accuracy for image amounts
- Config file to swap models / enable caching
- Confidence score per decision
- Simple visual dashboard (one user's finances, optional)

## 13. User Journeys
**Journey A — Simple purchase, affordable now:**
User asks laptop afford → system loads profile+events → forecasts 90 days → balance stays safe after full payment → status `affordable_now`, `full_payment` recommended, explanation shown.

**Journey B — Needs installment:**
User asks travel afford → full payment breaks min-balance → system checks payment_options → finds safe installment plan matching desired_completion_date → status `affordable_with_plan`, `installments` recommended, matched option shown.

**Journey C — Not affordable, message changes situation:**
User request evaluated → related message says pending expense "cancelled" → system updates timeline → previously unsafe request becomes safe, or vice versa → decision reflects amended info.

**Journey D — Blank amount in event:**
Event has blank amount → system finds linked image → extracts amount via vision → uses value in forecast (not treated as zero).

## 14. MVP Scope (Hackathon-Realistic)

### MVP-Core (simulator + rules + output — must work end to end)
- Data loading + currency conversion
- 90-day forecast engine (recurring + confirmed events only, core logic)
- Rule-based affordability + payment-method decision engine (full PS logic)
- Payment plan + spending-changes string generation
- output.csv generation matching schema
- usage_report.md (basic manual/token-counted log)
- README explaining how to run

### MVP-Plus (adds ML + multimodal on top of MVP-Core)
- ML models trained on synthetic data generated from the deterministic oracle
- Vision call for blank-amount image extraction
- Message intent handling (cancelled/confirmed/delayed) beyond simple keywords

## 15. Out-of-Scope Features
- Real bank account integration / live data feeds
- User authentication / production security
- Polished frontend app or mobile app
- Investment price prediction / stock recommendations (explicitly excluded by PS)
- Multi-language support
- Advanced ML/embedding-based conflict resolution (rule-based enough for MVP)

## 16. Success Metrics
- % rows in output.csv matching hidden ground truth on `affordability_status`
- Accuracy (delta) of `amount_safe_to_pay` vs ground truth
- % `payment_plan` strings exactly schema-valid & arithmetically correct
- % `earliest_date_for_full_payment` correct
- Validity rate of `spending_changes_needed` (no conflicting stop+reduce same event)
- Token cost per request (efficiency score)
- Working end-to-end run w/o crash on full requests.csv
- 100% of rows pass schema regex + sum checks
- 100% of plans pass the 90-day safety invariant
- Conflict resolution accuracy on synthetic conflict suite
- Spending-change validity 100% (no stop+reduce conflicts, max 3 respected)

## 17. Failure Modes We Must Prevent
- LLM writing directly to output.csv (all writes must go through the rule/verifier layer)
- Model output falling outside the valid range [0, requested_amount]
- Installments not matching an actual row in `request_payment_options.csv`
- Partial plan not having exactly 2 payments
- Stop and reduce applied to the same event

## 18. Risks and Assumptions
**Risks:**
- Vision extraction from images may be inaccurate → wrong amounts in forecast
- Ambiguous/conflicting msgs may be misinterpreted → wrong decision
- Tie-breaking logic complexity → bugs in ranking order
- Time pressure (hackathon) → core forecast engine bugs if rushed
- Exchange rate mismatches (wrong date/pair) → wrong currency conversion

**Assumptions:**
- All required data present in given CSVs (per PS, don't invent unsupported info)
- Exchange rates cover all needed currency-pair/date combos
- Payment options in `request_payment_options.csv` are complete/authoritative for installment matching
- Messages/images are supplementary, tables are source of truth unless amended
- Team has basic Python + pandas skill (beginner-friendly stack chosen deliberately)
