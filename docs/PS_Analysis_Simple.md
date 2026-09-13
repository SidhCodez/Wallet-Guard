# Buy or Wait? — PS Analysis (Simple Version)

## Simple Explanation

Build AI money-helper. User ask "Can I afford X?" Bot look at user's money (balance, bills, income, debts, pref) + files/images/msgs → tell user: pay full now, pay part, pay in installments, wait, or don't do it. Bot also give payment dates, safe amount, explain why.

Data given: user profiles, money events (past+future), exchange rates, payment options, msgs, images, sample answers, blank output template. Fill blank template correct.

---

## 1. Actual Problem

People buy things without check if safe for wallet long-term. Bank apps show balance only, not future. Need bot predict: "if you pay this, you broke in 3 weeks?" and recommend safe way.

## 2. Target Users

- Normal people w/ salary, bills, want buy something (laptop, trip, gift)
- People juggle multiple money goals (rent + save + debt)
- People w/ irregular income or spending in different currency

## 3. User Pain Points

- Don't know true "safe to spend" number (balance ≠ safe amount)
- Forget upcoming bills when decide buy
- Hard track: pending payments, EMIs, family transfers, investments
- Confuse: pay full vs installment vs wait — which safest?
- No personalized advice (generic budget app treat all same)

## 4. Existing Solutions

- Budget apps (Mint, YNAB): track spend, show categories, no "can I afford X" answer
- Manual spreadsheet: user calc self, tedious, error-prone
- Bank "buy now pay later" offers: pushed by seller, not user's real safety
- Mental math / gut feeling

## 5. Limitations of Existing

- No forecast (don't simulate next 90 days)
- No multi-source input (ignore msgs, images, informal info)
- Not personalized (ignore user's own priorities/preferences)
- No payment-plan generation (just say "yes/no", not "here's schedule")
- Currency mixing not handled well

## 6. Proposed Solution Ideas

- AI agent read all user data → build financial timeline
- Simulate 90 days forward, check never dip below min balance
- Read msgs/images to catch info not in tables (e.g. bonus mentioned in chat)
- Output structured decision + plan + explanation

## 7. Core Features (must build)

- Load & join all CSV data (user, events, requests, rates, options)
- Currency conversion (fixed rates given)
- 90-day balance forecast engine (recurring income/expense + confirmed future events)
- Affordability decision logic (full/partial/installment/wait/no) per strict rules in PS
- Payment plan generator (match to sample_requests.csv format)
- Basic message/image parsing for amendments (e.g. "cancelled", extract amount from image)
- Output CSV writer matching exact schema

## 8. Nice-to-Have (if time left)

- Smarter LLM reasoning for ambiguous msgs (conflicting info resolution)
- Better OCR/image understanding for blank amounts
- Config file for model swap / caching to save tokens
- Confidence score per decision
- Simple dashboard UI to see one user's finances visually

## 9. What NOT to Build (hackathon scope)

- Full production bank integration
- Real user auth / security system
- Fancy frontend app (unless free time, extra)
- Investment price prediction / stock advice (PS explicitly say NOT needed)
- Multi-language support
- Mobile app version

## 10. What Makes This Unique

- True forecast-based safety check (not just current balance check)
- Multimodal: text + image + tabular data fused into one decision
- Fully rule-based tie-breaking (deterministic, explainable — not black box)
- Personalization via user preferences/priorities baked into logic

## 11. Realistic MVP (hackathon-buildable)

1. Python script: load CSVs into pandas
2. Currency converter fn using exchange_rates.csv
3. Build per-user event timeline (recurring + one-time + confirmed income)
4. Forecast fn: simulate day-by-day balance 90 days
5. Decision fn: apply PS rules (affordable_now/with_plan/later/not) + payment method ranking
6. Message/image handler: simple keyword rules ("cancelled","confirmed") + call vision LLM for blank-amount images
7. Write output.csv matching schema exactly
8. Token usage log (usage_report.md) — count API calls manual or via SDK response metadata

## 12. Potential Technologies

- **Language:** Python (best for data + beginner-friendly)
- **Data handling:** pandas (read/join CSVs easy)
- **LLM:** Claude API (via Anthropic SDK) — for reading messages/images, reasoning ambiguous cases
- **Image reading:** send image to Claude vision (base64) to extract $ amount
- **Rules engine:** plain Python functions/if-else (deterministic, easy debug — NOT everything needs LLM)
- **Testing:** compare few rows manually against sample_requests.csv before full run
- **Version control:** Git/GitHub for code.zip submission

---

## 13. The Nine Things the Grader Will Test

1. Does the bot correctly check if user stays safe for 90 days before allowing a purchase?
2. Does the bot correctly calculate the max amount user can safely pay right now (amount_safe_to_pay)?
3. Does the bot correctly find the earliest date user could pay in full without breaking safety?
4. Does the bot correctly generate a payment plan — full, partial, installments, or wait — when full-now isn't safe?
5. Does the bot correctly suggest spending changes, like stopping or reducing flexible expenses, when needed to make a purchase work?
6. Does the bot correctly pull dollar amounts out of images (like a screenshot of a bill)?
7. Does the bot correctly read messages and update the data (e.g. "trip cancelled", "bonus confirmed")?
8. Does the bot correctly pick the right answer when two sources of info disagree?
9. Does the bot's output CSV match the exact schema, with a clear explanation and a usage report attached?

## 14. What a Naive Solution Gets Wrong

- **Using only current balance** — checking today's number and ignoring bills/income coming in the next 90 days.
- **Treating blank amount as zero** — if an image or message doesn't state a number clearly, assuming $0 instead of asking or extracting it properly.
- **Letting LLM calculate money** — asking the AI to "do the math" instead of using plain code, which can be wrong or inconsistent.
- **Ignoring payment_methods_user_will_consider** — recommending a plan the user already said they don't want (e.g. suggesting installments to someone who only wants to pay full or not at all).
- **Skipping the 90-day forecast** — deciding affordability from a snapshot instead of simulating the days ahead.

## 15. What the Winner Actually Builds

- **A simulator, not a chatbot** — something that plays out the user's finances day by day, not something that just replies to a question.
- **Rules first, ML second** — the core decision comes from clear, plain logic; AI is only used where rules can't help (messy text/images).
- **Synthetic data for training** — if extra examples are needed to test edge cases, made-up data can help without touching real user data.
- **Multimodal extraction** — pulling useful info out of both images and messages, not just the clean CSV tables.
- **Deterministic plan ranking** — given the same inputs, the payment-plan recommendation is always the same, never random or "it depends on the AI's mood."
- **Strict verifier before writing output.csv** — a final check step that catches bad or incomplete answers before they get written to the file.

## 16. Simple Mental Model

Think of it like a team with four jobs. The LLM reads and explains — it's good at making sense of messy text or images and putting the final answer into plain words. The simulator decides — it plays out the days ahead and knows what's actually going to happen to the balance. The rule layer enforces — it applies the PS's exact affordability rules so the decision is always consistent and explainable. The ML layer only helps — it's a backup for fuzzy cases, never the one holding the calculator.

### Beginner Notes
- "Recurring expense" = happens repeat, like rent every month.
- "Flexible expense" = can reduce/skip if need (e.g. eating out), vs "essential" (rent, food) can't skip.
- "Forecast" = predict future balance day by day, not just look at today's number.
- Keep logic in plain code where possible — only use AI/LLM for messy text/image understanding. Easier to debug, cheaper, more reliable for hackathon judging.
