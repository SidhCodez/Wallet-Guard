#  Database Schema

Note: core system use CSV + pandas (no DB needed for grading, per Architecture doc §4). This schema = **logical/optional** design — useful if team want SQLite for easier querying/debugging, or want clear data model reference. Same tables map 1:1 to given CSV files. Not required to implement as real DB; can stay CSV-only and just follow this schema as mental model.

---

## 1. Tables (Overview)

| Table | Why it exists |
|---|---|
| `users` | One row per user, holds balance/preference/currency info — root of all personalization |
| `financial_events` | Every past/future transaction/investment — core data forecast engine runs on |
| `exchange_rates` | Dated conversion rates — needed for multi-currency math |
| `payment_options` | Installment offers per request — needed to match `installments` method |
| `messages` | Unstructured notes — may amend events, read by LLM |
| `images` | Links image files to events/users/requests — used when event amount blank |
| `requests` | User's affordability questions — the rows we must predict for |
| `predictions` | Our own output (mirrors output.csv) — stores model+rule-validated final answer |
| `rule_overrides_log` | Audit trail — every time rule layer corrected model output (matches `evaluation/rule_overrides.log` requirement) |
| `synthetic_scenarios` | Oracle-labeled training scenarios for ML accelerators — training data only, never used for grading output |
| `extraction_log` | Raw record of every vision/message LLM call — mirrors the data behind `usage_report.md` |
| `verifier_log` | Per-check pass/fail record from the final verifier gate, before a row is allowed into predictions/output.csv |

12 tables total. Small, flat, beginner-friendly — mirrors given CSVs almost exactly, plus a few internal-only tables for our own outputs, training data, and audit trails.

---

## 2 & 3. Columns and Data Types

### `users`
| Column | Type | Note |
|---|---|---|
| user_id | TEXT (PK) | e.g. "user_01" |
| home_currency | TEXT | INR/ZAR/IDR/USD/EUR |
| available_balance | REAL | current balance in home_currency |
| minimum_balance_to_keep | REAL | safety floor |
| priorities | TEXT | comma/JSON list |
| payment_methods_user_will_consider | TEXT | comma/JSON list (full_payment,installments,...) |
| spending_preferences | TEXT | optional free text/JSON |

### `financial_events`
| Column | Type | Note |
|---|---|---|
| event_id | TEXT (PK) | |
| user_id | TEXT (FK → users) | |
| event_type | TEXT | e.g. rent, salary, EMI, transfer, investment |
| amount | REAL, NULLABLE | blank → resolve via linked image |
| currency | TEXT | may differ from home_currency |
| event_date | DATE | |
| is_recurring | BOOLEAN | |
| is_flexible | BOOLEAN | flexible = can stop/reduce |
| status | TEXT | confirmed / pending / cancelled / failed / estimate |
| linked_event_id | TEXT, NULLABLE (FK → financial_events.event_id) | points to earlier event in same lifecycle |

### `exchange_rates`
| Column | Type | Note |
|---|---|---|
| rate_id | INTEGER (PK, autoincrement) | surrogate key, not in original CSV |
| rate_date | DATE | |
| currency_pair | TEXT | e.g. "USD_INR" |
| rate | REAL | |

### `payment_options`
| Column | Type | Note |
|---|---|---|
| payment_option_id | TEXT (PK) | |
| request_id | TEXT (FK → requests) | |
| start_date | DATE | |
| interval_days | INTEGER | days between recurring payments |
| financing_fee | REAL, NULLABLE | |
| total_payable | REAL | |

### `messages`
| Column | Type | Note |
|---|---|---|
| message_id | TEXT (PK) | |
| user_id | TEXT, NULLABLE (FK → users) | |
| request_id | TEXT, NULLABLE (FK → requests) | |
| related_event_id | TEXT, NULLABLE (FK → financial_events) | present only if directly describes an event |
| message_text | TEXT | untrusted content |
| message_date | DATE, NULLABLE | for newest-record conflict resolution |

### `images`
| Column | Type | Note |
|---|---|---|
| image_id | TEXT (PK) | maps to file `media/images/<image_id>.png` |
| user_id | TEXT, NULLABLE (FK → users) | |
| request_id | TEXT, NULLABLE (FK → requests) | |
| related_event_id | TEXT, NULLABLE (FK → financial_events) | |

### `requests`
| Column | Type | Note |
|---|---|---|
| request_id | TEXT (PK) | |
| user_id | TEXT (FK → users) | |
| request_date | DATE | |
| request_type | TEXT | purchase/travel/education/family_transfer/debt_repayment/investment/housing/emergency_expense/other |
| requested_amount | REAL | |
| desired_completion_date | DATE | |
| allows_partial_payment | BOOLEAN | |
| request_text | TEXT | |

### `predictions` (our output, mirrors output.csv)
| Column | Type | Note |
|---|---|---|
| request_id | TEXT (PK, FK → requests) | one row per request |
| amount_safe_to_pay | REAL | |
| affordability_status | TEXT | affordable_now/with_plan/later/not_affordable |
| recommended_payment_method | TEXT | full_payment/partial_payment/installments/wait/not_recommended |
| payment_plan | TEXT | `date:amount|date:amount` string, or "none" |
| earliest_date_for_full_payment | DATE, NULLABLE | empty if never safe in forecast window |
| spending_changes_needed | TEXT | `stop:event_id|reduce_to:event_id:amount`, or "none" |
| decision_explanation | TEXT | |

### `rule_overrides_log` (audit trail, matches required `evaluation/rule_overrides.log`)
| Column | Type | Note |
|---|---|---|
| override_id | INTEGER (PK, autoincrement) | |
| request_id | TEXT (FK → requests) | |
| field_name | TEXT | which output field was corrected |
| model_value | TEXT | model's original draft value |
| corrected_value | TEXT | rule-validator's final value |
| reason | TEXT | why override happened (e.g. "breached min balance") |
| timestamp | DATETIME | |

### `synthetic_scenarios` (training data only — not used for grading output)
| Column | Type | Note |
|---|---|---|
| scenario_id | TEXT (PK) | |
| user_id | TEXT | synthetic user, not a real dataset user |
| generated_at | DATETIME | when this scenario was generated |
| seed | INTEGER | random seed used, for reproducibility |
| label_status | TEXT | oracle-computed `affordability_status` ground truth |
| label_safe_amount | REAL | oracle-computed `amount_safe_to_pay` ground truth |
| label_earliest_date | DATE, NULLABLE | oracle-computed `earliest_date_for_full_payment` ground truth |
| label_method | TEXT | oracle-computed `recommended_payment_method` ground truth |
| label_plan | TEXT | oracle-computed `payment_plan` ground truth |
| label_spending_changes | TEXT | oracle-computed `spending_changes_needed` ground truth |

### `extraction_log` (mirrors raw data behind `usage_report.md`)
| Column | Type | Note |
|---|---|---|
| extraction_id | INTEGER (PK, autoincrement) | |
| source_type | TEXT | "image" or "message" |
| source_id | TEXT | image_id or message_id |
| extracted_json | TEXT | raw strict-JSON response from the LLM call |
| confidence | REAL | confidence field from the extraction |
| model_name | TEXT | e.g. "claude-sonnet-4-6" |
| input_tokens | INTEGER | |
| output_tokens | INTEGER | |
| cost_usd | REAL | |
| called_at | DATETIME | |

### `verifier_log` (per-check result from the final verifier gate)
| Column | Type | Note |
|---|---|---|
| verify_id | INTEGER (PK, autoincrement) | |
| request_id | TEXT (FK → requests) | |
| check_name | TEXT | e.g. "amount_in_range", "min_balance_safe", "installments_match_options" |
| passed | BOOLEAN | |
| detail | TEXT | human-readable reason, especially useful when passed = false |
| checked_at | DATETIME | |

---

## 4. Primary Keys
- `users.user_id`
- `financial_events.event_id`
- `exchange_rates.rate_id` (surrogate, since date+pair not always unique across sources)
- `payment_options.payment_option_id`
- `messages.message_id`
- `images.image_id`
- `requests.request_id`
- `predictions.request_id` (1:1 with requests)
- `rule_overrides_log.override_id` (surrogate)
- `synthetic_scenarios.scenario_id`
- `extraction_log.extraction_id` (surrogate)
- `verifier_log.verify_id` (surrogate)

---

## 5. Foreign Keys
- `financial_events.user_id` → `users.user_id`
- `financial_events.linked_event_id` → `financial_events.event_id` (self-referencing)
- `payment_options.request_id` → `requests.request_id`
- `messages.user_id` → `users.user_id` (nullable)
- `messages.request_id` → `requests.request_id` (nullable)
- `messages.related_event_id` → `financial_events.event_id` (nullable)
- `images.user_id` → `users.user_id` (nullable)
- `images.request_id` → `requests.request_id` (nullable)
- `images.related_event_id` → `financial_events.event_id` (nullable)
- `requests.user_id` → `users.user_id`
- `predictions.request_id` → `requests.request_id`
- `rule_overrides_log.request_id` → `requests.request_id`
- `verifier_log.request_id` → `requests.request_id`

---

## 6. Relationships

```
users (1) ──< (many) financial_events
users (1) ──< (many) requests
requests (1) ──< (many) payment_options
requests (1) ──1── predictions
requests (1) ──< (many) rule_overrides_log
financial_events (1) ──< (many) financial_events   [self-ref via linked_event_id, lifecycle chain]
messages / images ──> (0..1) users, requests, financial_events  [polymorphic-ish, one of three FK typically set]
```

Messages/images use nullable multi-FK pattern (only one of user_id/request_id/related_event_id typically filled) — simplest for beginner team, avoids extra junction tables.

---

## 7. Required Fields
- `users`: user_id, home_currency, available_balance, minimum_balance_to_keep
- `financial_events`: event_id, user_id, event_type, event_date, is_recurring, is_flexible, status (amount nullable — must resolve via image if blank, never treat as zero)
- `requests`: all columns required (per PS input schema)
- `predictions`: all columns required (matches required output.csv schema)
- `payment_options`: payment_option_id, request_id, start_date, total_payable

## 8. Optional Fields
- `financial_events.amount` (blank → needs image resolution)
- `financial_events.linked_event_id`
- `payment_options.interval_days`, `financing_fee` (some options may be lump-sum, no fee)
- `messages`/`images`: user_id/request_id/related_event_id (only one typically set, others null)
- `predictions.earliest_date_for_full_payment` (empty when never safe)

---

## 9. Indexes (Where Useful)

```sql
CREATE INDEX idx_events_user_date ON financial_events(user_id, event_date);
CREATE INDEX idx_events_linked ON financial_events(linked_event_id);
CREATE INDEX idx_options_request ON payment_options(request_id);
CREATE INDEX idx_messages_request ON messages(request_id);
CREATE INDEX idx_messages_event ON messages(related_event_id);
CREATE INDEX idx_images_event ON images(related_event_id);
CREATE INDEX idx_requests_user ON requests(user_id);
CREATE INDEX idx_overrides_request ON rule_overrides_log(request_id);
CREATE INDEX idx_synth_user ON synthetic_scenarios(user_id);
CREATE INDEX idx_extract_source ON extraction_log(source_type, source_id);
CREATE INDEX idx_verify_request ON verifier_log(request_id);
```
Indexes speed up the joins forecast engine + feature builder do repeatedly per user/request — matters even on small hackathon dataset if run many times during dev/testing.

---

## 10. Example Records

**users**
```
user_01 | INR | 45000.00 | 10000.00 | ["rent","savings"] | ["full_payment","installments"] | null
```

**financial_events**
```
event_14 | user_01 | rent            | 15000.00 | INR | 2026-10-01 | true  | false | confirmed | null
event_21 | user_01 | dining_out       | 3000.00  | INR | 2026-09-15 | true  | true  | confirmed | null
event_30 | user_01 | bonus_investment | NULL     | INR | 2026-09-20 | false | false | estimate  | null
```

**requests**
```
req_101 | user_01 | 2026-09-12 | purchase | 60000.00 | 2026-10-10 | true | "Can I afford this laptop?"
```

**payment_options**
```
opt_1 | req_101 | 2026-09-12 | 30 | 500.00 | 61500.00
```

**predictions**
```
req_101 | 20000.00 | affordable_with_plan | partial_payment | 2026-09-12:20000|2026-10-01:40000 | 2026-10-01 | none | "Partial payment keeps buffer above min balance until rent clears."
```

**rule_overrides_log**
```
1 | req_101 | amount_safe_to_pay | 35000.00 | 20000.00 | "model draft breached min_balance in 90d forecast" | 2026-09-12 10:03:00
```

**synthetic_scenarios**
```
synth_0042 | synth_user_07 | 2026-09-10 14:22:00 | 42 | affordable_with_plan | 18500.00 | 2026-10-05 | partial_payment | 2026-09-10:18500|2026-10-05:31500 | none
```

**extraction_log**
```
1 | image | img_034 | {"amount":4200.00,"currency":"INR","date":"2026-09-08","status":"confirmed","event_id":"event_30","confidence":0.94} | 0.94 | claude-sonnet-4-6 | 812 | 46 | 0.0031 | 2026-09-12 09:58:11
```

**verifier_log**
```
1 | req_101 | min_balance_safe | true | "min forecast balance 12500.00 >= min_balance_to_keep 10000.00" | 2026-09-12 10:03:05
```

---

## 11. SQL Schema (SQLite-compatible, optional)

```sql
CREATE TABLE users (
    user_id TEXT PRIMARY KEY,
    home_currency TEXT NOT NULL,
    available_balance REAL NOT NULL,
    minimum_balance_to_keep REAL NOT NULL,
    priorities TEXT,
    payment_methods_user_will_consider TEXT,
    spending_preferences TEXT
);

CREATE TABLE financial_events (
    event_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(user_id),
    event_type TEXT NOT NULL,
    amount REAL,
    currency TEXT,
    event_date DATE NOT NULL,
    is_recurring BOOLEAN NOT NULL,
    is_flexible BOOLEAN NOT NULL,
    status TEXT NOT NULL,
    linked_event_id TEXT REFERENCES financial_events(event_id)
);

CREATE TABLE exchange_rates (
    rate_id INTEGER PRIMARY KEY AUTOINCREMENT,
    rate_date DATE NOT NULL,
    currency_pair TEXT NOT NULL,
    rate REAL NOT NULL
);

CREATE TABLE requests (
    request_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(user_id),
    request_date DATE NOT NULL,
    request_type TEXT NOT NULL,
    requested_amount REAL NOT NULL,
    desired_completion_date DATE NOT NULL,
    allows_partial_payment BOOLEAN NOT NULL,
    request_text TEXT
);

CREATE TABLE payment_options (
    payment_option_id TEXT PRIMARY KEY,
    request_id TEXT NOT NULL REFERENCES requests(request_id),
    start_date DATE NOT NULL,
    interval_days INTEGER,
    financing_fee REAL,
    total_payable REAL NOT NULL
);

CREATE TABLE messages (
    message_id TEXT PRIMARY KEY,
    user_id TEXT REFERENCES users(user_id),
    request_id TEXT REFERENCES requests(request_id),
    related_event_id TEXT REFERENCES financial_events(event_id),
    message_text TEXT NOT NULL,
    message_date DATE
);

CREATE TABLE images (
    image_id TEXT PRIMARY KEY,
    user_id TEXT REFERENCES users(user_id),
    request_id TEXT REFERENCES requests(request_id),
    related_event_id TEXT REFERENCES financial_events(event_id)
);

CREATE TABLE predictions (
    request_id TEXT PRIMARY KEY REFERENCES requests(request_id),
    amount_safe_to_pay REAL NOT NULL,
    affordability_status TEXT NOT NULL,
    recommended_payment_method TEXT NOT NULL,
    payment_plan TEXT NOT NULL,
    earliest_date_for_full_payment DATE,
    spending_changes_needed TEXT NOT NULL,
    decision_explanation TEXT NOT NULL
);

CREATE TABLE rule_overrides_log (
    override_id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id TEXT NOT NULL REFERENCES requests(request_id),
    field_name TEXT NOT NULL,
    model_value TEXT,
    corrected_value TEXT NOT NULL,
    reason TEXT NOT NULL,
    timestamp DATETIME NOT NULL
);

CREATE TABLE synthetic_scenarios (
    scenario_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    generated_at DATETIME NOT NULL,
    seed INTEGER NOT NULL,
    label_status TEXT NOT NULL,
    label_safe_amount REAL NOT NULL,
    label_earliest_date DATE,
    label_method TEXT NOT NULL,
    label_plan TEXT NOT NULL,
    label_spending_changes TEXT NOT NULL
);

CREATE TABLE extraction_log (
    extraction_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type TEXT NOT NULL,
    source_id TEXT NOT NULL,
    extracted_json TEXT NOT NULL,
    confidence REAL,
    model_name TEXT NOT NULL,
    input_tokens INTEGER,
    output_tokens INTEGER,
    cost_usd REAL,
    called_at DATETIME NOT NULL
);

CREATE TABLE verifier_log (
    verify_id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id TEXT NOT NULL REFERENCES requests(request_id),
    check_name TEXT NOT NULL,
    passed BOOLEAN NOT NULL,
    detail TEXT,
    checked_at DATETIME NOT NULL
);

CREATE INDEX idx_events_user_date ON financial_events(user_id, event_date);
CREATE INDEX idx_events_linked ON financial_events(linked_event_id);
CREATE INDEX idx_options_request ON payment_options(request_id);
CREATE INDEX idx_messages_request ON messages(request_id);
CREATE INDEX idx_messages_event ON messages(related_event_id);
CREATE INDEX idx_images_event ON images(related_event_id);
CREATE INDEX idx_requests_user ON requests(user_id);
CREATE INDEX idx_overrides_request ON rule_overrides_log(request_id);
CREATE INDEX idx_synth_user ON synthetic_scenarios(user_id);
CREATE INDEX idx_extract_source ON extraction_log(source_type, source_id);
CREATE INDEX idx_verify_request ON verifier_log(request_id);
```

---

## 12. Which Tables Are Required for Grading

- **Required** (grading depends on these): `users`, `financial_events`, `requests`, `payment_options`, `predictions`
- **Optional** (used by the pipeline, but not directly graded): `messages`, `images`, `exchange_rates` — these feed the timeline/forecast but aren't checked as tables themselves
- **Internal only** (never touched by grading, exist to support the build): `rule_overrides_log`, `synthetic_scenarios`, `extraction_log`, `verifier_log`

---

### Beginner Note
Team can skip actual DB entirely — load CSVs into pandas DataFrames named same as these tables, treat this doc as the "shape" of the data. Only build real SQLite file if want practice SQL or easier ad-hoc querying during debugging (`df.to_sql()` one-liner converts DataFrame → SQLite table if desired).
