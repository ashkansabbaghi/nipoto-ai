# LLM provider validation (T0.3)

> Status: **pending**. No provider key yet; the pipeline runs on `FakeLLM` until one is
> set. Fill this file from the output of `make check-provider` (after setting `LLM_*` in `.env`).

## Measurements

_Paste the table printed by `scripts/check_provider.py` here, then fill in prices._

| model | stream | include_usage | JSON mode | TTFT p50 (ms) | total p50 (ms) | tokens in/out | price in/out ($/1M) |
|---|---|---|---|---|---|---|---|
| | | | | | | | |

## Choice

- `CHAT_MODEL` = _…_ (draft.generate, auto.generate)
- `SMALL_MODEL` = _…_ (router.classify)
- Prices copied into `config/routes.yaml` → `prices`.

## Data policy (§10.5, §17 Q4)

| question | answer | source (link/date) |
|---|---|---|
| Is request/response data retained? For how long? | | |
| Is data used for training? Opt-out available? | | |
| Where is it processed (region)? | | |
| Zero-retention / enterprise terms available? | | |

Until Q4 is decided, only synthetic data is sent to the provider (MVP-PLAN §8).
