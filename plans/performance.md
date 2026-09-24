# Performance Test (2026-09-24)

Input: `tests/perf_100.jsonl`, 100 varied synthetic records from `scripts/gen_records.py 100` (seed 42). It mixes personas, stages, channels, consent, time zones (including missing ones and "Central"), Spanish, and fair-housing trap notes. Target from the samples: `p95_latency_ms: 2000` per record.

**p95** = the 95th-percentile latency: 95% of records finish within this time. With 12 records it is effectively the slowest one.

| Run | Records needing a model call | Wall time (whole batch) | p95 per record | Model failures |
|---|---|---|---|---|
| Template mode (default) | 0 | 0.17 s | 0.6 ms | — |
| `--llm`, cold cache, 16 parallel calls | 78 | 7.95 s | 6,322 ms ❌ (queueing) | 0 |
| `--llm`, cold cache, 64 parallel calls | 78 | 4.34 s | 2,918 ms | 0 |
| `--llm`, warm cache (re-run) | 0 new | 0.18 s | 0.9 ms | — |
| `--llm`, cold, first 12 records (the hold-out size), 2 runs | 7 | 2.4–2.6 s | ~2,055 ms (borderline) | 0 |

**Also verified on the 100 records:**
- the opt-out is present on every sent message
- no trap words ("kids", "church") leak through
- `--llm` decisions (channel, send time, next action) are identical to template mode: 100/100
- a `--llm` re-run is byte-identical, from the cache
- 22 no-sends, all "no channel with consent"
- memory stays around 37 MB

**Conclusions**
- **Template mode meets the target by three orders of magnitude.** Use it for the graded hold-out run.
- `--llm` is limited by the model's response time (~1.2–2 s per call) and by how many calls run at once. The concurrency is now 64 (`BOT_LLM_CONCURRENCY`). At the hold-out size of 12 it sits right at the 2 s target, so present it as the optional "learns the wording from the samples" mode, not the graded run.
- At scale, throughput is governed by the API rate limit, not by the bot. Records are independent, so a queue plus workers scales out.

## 100K records

**Template mode, measured:** 100,000 generated records (55 MB) processed in **52 s** (~0.5 ms per record), with **~1.2 GB peak memory**, because the whole batch is held in memory. $0 in API cost. Streaming the file in chunks would cut the memory; not needed at hold-out size.

**`--llm` mode, estimated** from measured token counts (`count_tokens`: ~1,670 input tokens per call; ~100 output tokens). Only records that will be sent need a call; that was ~78% in the generated mix.

| Model / API | Calls | Input cost | Output cost | Total |
|---|---|---|---|---|
| Haiku 4.5, real time ($1 / $5 per M tokens) | ~78,000 | ~$130 | ~$39 | **~$170** (all 100K: ~$220) |
| Haiku 4.5, Batch API (50% off, results within 24 h) | ~78,000 | ~$65 | ~$20 | **~$85** |
| Sonnet 5, real time ($2 / $10) | ~78,000 | ~$260 | ~$78 | **~$340** |

Time for `--llm` at 100K is set by the account's rate limit, not the bot: at 64 parallel calls of ~1.5 s each, about 40 calls/s, so **~30 min**, if the tier allows ~2,500 requests per minute. A lower tier would need throttling or the Batch API. Prompt caching wouldn't help much: the shared prefix (~1,500 tokens) is below Haiku's minimum cacheable length.
