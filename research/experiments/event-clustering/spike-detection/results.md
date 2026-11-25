# Experiment 4: volume spike detection (R6, 2026-11-25)

> **Status: Experimental result.** 
> Part of the [Newsmon research library](../../../README.md). Evidence dates default to 2026-11-25; first-person statements are by the AI research agents that wrote the notes.

**Question:** does a simple method flag the obvious spikes in a news-volume series?
**Answer:** yes, the rolling z-score catches them. Two caveats: the GDELT series has gaps, and it is short. TESTED.

## Input
`gdelt_timelinevol_ukraine_30d.json`, from the GDELT DOC 2.0 API with `mode=timelinevol`, `query=Ukraine` and
`timespan=30d`. That returns "Volume Intensity" (percent of monitored coverage) at daily resolution.

GDELT returned only **23 points for 30 days**. The calendar has gaps from 2026-10-28 to 11-02 (6 days) and on 11-17.

Two other requests failed:
- `timespan=3months` was rate-limited.
- An earlier `3months` call returned only 7 fifteen-minute points for today.

**GDELT timelines can be silently incomplete. Treat missing dates as missing, never as zero.**

## Methods
`spike_detect.py` writes `spike_results.json`. It runs two methods:
- a rolling z-score against the trailing 7 points;
- a one-sided CUSUM with k = 0.5 and h = 4, on a robust baseline (trailing median, MAD × 1.4826).

## Results
Series, from 11-03 on: 3.95 2.12 3.54 3.62 3.94 3.74 3.08 2.76 2.71 3.28 **4.39 4.96** 3.90 4.74 · 2.95 **6.72** 4.01 5.00 5.36 3.87 3.19 2.38.

| Method | Flags |
|---|---|
| z ≥ 2.5 | **11-14** (z = 2.65) and **11-19** (z = 3.48, the series maximum) |
| z ≥ 2.0 | 11-13, 11-14, 11-19 |
| CUSUM | **11-16** (sustained rise, S = 4.4). It does **not** flag 11-19, because the 11-18 dip and a wide MAD reset the accumulation. |

The obvious spike is 11-19, the maximum, at 1.7× the trailing mean. The z-score catches it, and so does the 11-13/14
step. CUSUM detects the sustained elevation but misses the sharp single-day peak.

**What happened on 11-19 was not checked.** The method's job is to flag the date; attribution is a separate step.

## Recommendation
Use a **rolling z-score**: trailing 7 days at daily resolution, or 24–48 h at hourly resolution, with a threshold of
2.5. Run it per topic or per entity, and per event cluster. Add a minimum-count floor so low-volume topics do not
fire on noise. CUSUM is optional, for detecting a sustained rise.

## Limits
- One topic and 23 points, so no precision or recall estimate is possible.
- No ground-truth spike list.
- GDELT gaps and rate limits make it unsuitable as the only volume source. The system's own per-cluster item counts
  over time are the better MVP signal: they are counted from the system's own data, so they have no rate limit and no
  missing days. That conclusion is INFERRED.
