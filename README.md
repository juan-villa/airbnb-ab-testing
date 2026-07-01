# Airbnb A/B Test Analysis: Instant-Book Prompt

An end-to-end, fully reproducible A/B testing project built on ~102k real NYC
Airbnb listings ([Kaggle Airbnb Open Data](https://www.kaggle.com/datasets/arianazmoudeh/airbnbopendata)).
It simulates a product experiment, analyzes it with **SQL + statistics**, and
presents the readout in a **Streamlit dashboard**.

## The experiment

> **Hypothesis:** adding a prominent *"Book instantly, no host approval
> needed"* prompt on a listing page increases booking conversion.

| Design choice | Value |
|---|---|
| Unit of randomization | Listing (deterministic hash of listing id, salted by experiment name) |
| Split | 50 / 50 |
| Primary metric | Booking conversion rate (bookings / page views) |
| Secondary metric | Revenue per page view |
| Duration | 28 simulated days |
| Ground-truth effect | **+10% relative lift** baked into the simulation |

Because the outcomes are simulated with a *known* effect, the project doubles
as a validation exercise: does the analysis pipeline correctly recover a +10%
lift that we know is really there? **It does**: the estimate lands at
+10.0% with a 95% CI of [+9.7%, +10.4%].

## Results

| Metric | Control | Treatment | Lift |
|---|---|---|---|
| Conversion rate | 3.90% | 4.29% | **+10.0%** (p < 1e-300) |
| Revenue / view | $22.72 | $24.85 | +9.4% |

![Conversion by group](outputs/chart_conversion_by_group.png)

The lift is broad-based: every borough x room-type segment moved in the same
direction, which is what you want to see before shipping:

![Segment lift](outputs/chart_segment_lift.png)

Experiment health: the observed split was 50.03% / 49.97%, and the sample-ratio
mismatch (SRM) chi-square check passes (χ² = 0.03, well under the 3.84
threshold), so the randomization is trustworthy.

## Project structure

```
├── data/                    # raw Kaggle CSV (zipped)
├── src/
│   ├── clean_data.py        # 1. clean raw CSV -> SQLite (listings table)
│   ├── simulate_experiment.py # 2. hash-based 50/50 assignment + simulated outcomes
│   └── run_analysis.py      # 3. run SQL readout, z-test, CI, charts
├── sql/
│   ├── 01_group_summary.sql # headline metrics per group
│   ├── 02_lift.sql          # absolute + relative lift (CTE pivot)
│   ├── 03_segment_breakdown.sql # lift by borough x room type
│   └── 04_srm_check.sql     # sample-ratio-mismatch health check
├── dashboard/
│   └── app.py               # Streamlit readout dashboard
└── outputs/                 # readout CSVs, significance.json, charts
```

## Reproduce it

```bash
pip install -r requirements.txt
make all          # runs clean -> simulate -> analyze (or run the 3 scripts in src/ in order)
make dashboard    # launches the Streamlit dashboard
```

Everything is seeded (`SEED = 42`), so a fresh clone reproduces the exact
numbers above.

## Methodology notes

- **Deterministic hash assignment** (`md5(experiment_name + listing_id)`)
  mirrors how real experimentation platforms randomize: stateless,
  reproducible, and re-salted per experiment.
- **Heterogeneous units**: traffic follows listing popularity (Poisson on
  reviews/month) and baseline conversion depends on rating and price via a
  logistic model, so the groups are messy in realistic ways, not uniform.
- **Two-proportion z-test** with pooled standard error for the hypothesis
  test; unpooled standard error for the confidence interval on the lift.
- **SRM check first**: if the observed split deviates from the designed
  50/50 beyond chance, no metric can be trusted, so the health check is
  part of the standard readout.
- **Segment results are directional**: the experiment is powered for the
  topline; borough x room-type cuts are smaller samples and read as noise
  bands around the true effect (visible in the segment chart: 4-17% around
  the true +10%).
