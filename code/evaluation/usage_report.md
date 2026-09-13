# Token Usage and Cost Report

## Final Full-Dataset Run

**Run date:** 2026-09-13
**Dataset:** dataset/requests.csv (250 requests)
**Output:** output.csv (250 rows)

## Model Providers and Names

**None.** The final pipeline is fully deterministic. No LLM API calls are
made during training or inference. All financial decisions are computed by
the rule engine in `code/src/oracle.py` and `code/src/plan_engine.py`.

## Model Calls

| Model | Calls | Input Tokens | Output Tokens | Cost (USD) |
|-------|-------|--------------|---------------|------------|
| (none) | 0 | 0 | 0 | 0.00 |

## Totals

- Total model calls: 0
- Total input tokens: 0
- Total output tokens: 0
- Total cost: $0.00
- Average tokens per request: 0
- Average cost per request: $0.00

## Notes

The project spec allows rule-based pipelines. Per PS §Evaluation:
"PS still graded on output correctness, not on presence of ML."
All decisions are deterministic and reproducible. Running `python3 main.py`
twice produces byte-identical output.csv.
