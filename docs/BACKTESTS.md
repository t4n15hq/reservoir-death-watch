# Backtests

Three historical water crises are this project's truth-test. The model has not earned the right to call itself useful until it would have flagged each of them, using only data available at the time, before the crisis was public knowledge.

**Backtests are not for tuning. They are for validation.** If a backtest fails, the model is wrong. Do not adjust thresholds to make it pass.

---

## Case 1: Krishnaraja Sagar (KRS), Bengaluru, March 2024

### What happened

Bengaluru's primary water source, the KRS reservoir on the Kaveri, dropped to roughly 16% of capacity in early 2024 — the worst level in over a decade. The 2023 southwest monsoon (El Niño year) was deficient. Bengaluru, a city of 13 million, faced its worst water crisis since the lakes era. Restrictions on commercial water use, tanker-mafia activity, IT companies going work-from-home.

### What was visible from satellites in late 2023

- JRC monthly history showed KRS at well below 5-year averages from August 2023 onward.
- Sentinel-2 showed steady area decline through fall 2023.
- ONI was strongly positive (El Niño) throughout 2023.
- CWC bulletins were already showing KRS as deficit by November 2023.

### The backtest

```python
def test_krs_jan_2024_flagged_critical():
    """KRS should be Critical when the model is run as of Dec 31, 2023."""
    snapshot = run_pipeline(
        as_of=date(2023, 12, 31),
        reservoirs=["krs"]
    )
    krs = snapshot.reservoirs[0]
    assert krs.tier == "critical", (
        f"Expected critical, got {krs.tier}. "
        f"Days to dead storage: {krs.projection.neutral_monsoon.days_to_dead_storage}"
    )
    # Sanity check
    assert krs.projection.neutral_monsoon.days_to_dead_storage < 60
```

### Why this case matters

It's the most recent, best-documented water crisis with a clear satellite trail. If the model can't flag it, the model can't flag anything.

### Hard rules

- Use only data with timestamps ≤ Dec 31, 2023.
- Do not hardcode reservoir-specific thresholds to make this pass.
- If failing: investigate KRS's area-volume curve first, then the regression window, then the El Niño delta. Do not tune `tier` boundaries.

---

## Case 2: Mettur, Tamil Nadu, summer 2019

### What happened

Mettur reservoir on the Kaveri reached its lowest summer level in years. This fed into the broader Chennai 2019 crisis — by June 2019 Chennai's four main reservoirs (Poondi, Cholavaram, Red Hills, Chembarambakkam) were essentially dry. Mettur is upstream context: its low levels were already visible months earlier.

### What was visible in early 2019

- 2018 northeast monsoon (Tamil Nadu's primary monsoon) had been 44% deficient.
- Mettur was below average from late 2018.
- The trajectory toward the June 2019 crisis was discernible in March data.

### The backtest

```python
def test_mettur_march_2019_flagged():
    """Mettur should be Critical or Warning when run as of Mar 31, 2019."""
    snapshot = run_pipeline(
        as_of=date(2019, 3, 31),
        reservoirs=["mettur"]
    )
    mettur = snapshot.reservoirs[0]
    assert mettur.tier in ("critical", "warning"), (
        f"Expected critical/warning, got {mettur.tier}"
    )
```

### Why this case matters

It tests the model in a non-El Niño year (2018/19 was ENSO-neutral going into La Niña) — the Tamil Nadu deficit was driven by a failed northeast monsoon, not by the southwest one. This catches over-reliance on ONI as the dominant signal.

### Hard rules

- Use only data ≤ Mar 31, 2019.
- This case validates that the depletion signal works without an El Niño tailwind in the model.

---

## Case 3: Jayakwadi, Marathwada, 2016 and 2019

### What happened

Jayakwadi reservoir on the Godavari, serving the Marathwada region of Maharashtra, has had recurring near-dead-storage events. 2016 and 2019 were both crisis years for Marathwada, driven by failed/weak monsoons. The recurring nature of this case is its key feature.

### The backtest

```python
def test_jayakwadi_2016_and_2019_both_flagged():
    """Jayakwadi should be flagged in both 2016 and 2019."""
    s2016 = run_pipeline(
        as_of=date(2016, 3, 31),
        reservoirs=["jayakwadi"]
    )
    s2019 = run_pipeline(
        as_of=date(2019, 3, 31),
        reservoirs=["jayakwadi"]
    )
    assert s2016.reservoirs[0].tier in ("critical", "warning")
    assert s2019.reservoirs[0].tier in ("critical", "warning")
```

### Why this case matters

It tests robustness rather than one-shot fit. A model that flags one crisis but misses the other is brittle.

### Hard rules

- Use only data ≤ the respective `as_of` date.
- Both must pass. One out of two is failure.

---

## Running the backtests

The backtests live in `pipeline/tests/test_backtest.py` and run via:

```bash
cd pipeline
uv run pytest tests/test_backtest.py -v
```

The metadata/collection check runs in CI on every PR. The live backtests are
Earth Engine-bound and opt in via `RDW_RUN_BACKTESTS=1`; run them manually
before claiming Phase 1 or "shipped" status.

---

## What to do if backtests fail

In order of likelihood:

1. **Area-to-volume curve is wrong for the reservoir.** Check the hypsometric fit. R² should be > 0.85. If lower, the SRTM approximation is failing — try a smaller AOI, or check for upstream check-dams confusing the fit.

2. **Regression window is too long.** A 90-day window may average over a regime change. Try Chow test for breakpoint; shorten window if needed.

3. **El Niño delta is computed wrong.** Verify the per-reservoir monsoon inflow regression against ONI history.

4. **The linear model is genuinely wrong for this reservoir.** This would be a major finding. Document carefully. Consider segmented linear (early decline vs late decline regimes). Do NOT switch to ML; if linear isn't sufficient, the project's premise needs rethinking.

5. **You're tempted to lower the threshold.** Stop. Read the AGENT.md non-negotiables again. Surface to Tanishq.

---

## Adding new backtest cases

If during development you find another well-documented historical case (e.g. Cauvery delta 2017, Chennai 2019 specifically), add it. Format follows the three above. More backtests = stronger validation. **Do NOT remove existing backtest cases.**
