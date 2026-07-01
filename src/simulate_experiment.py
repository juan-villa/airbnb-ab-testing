"""Simulate an A/B test (instant-book prompt) over the real listings.

Listings are hash-assigned 50/50; outcomes are drawn with a known +10%
relative lift on conversion so the analysis can be validated against
ground truth.
"""

import hashlib
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = REPO_ROOT / "outputs" / "airbnb.db"

EXPERIMENT_NAME = "instant_book_prompt_v1"
TRUE_LIFT = 0.10
BASELINE_CONVERSION = 0.035
DAYS = 28
SEED = 42


def assign_group(listing_id: int) -> str:
    """Deterministic, salted 50/50 assignment from a hash of the listing id."""
    digest = hashlib.md5(f"{EXPERIMENT_NAME}:{listing_id}".encode()).hexdigest()
    return "treatment" if int(digest, 16) % 2 == 0 else "control"


def simulate(listings: pd.DataFrame) -> pd.DataFrame:
    rng = np.random.default_rng(SEED)
    df = listings.copy()

    df["experiment_group"] = df["id"].map(assign_group)

    # Traffic scales with review activity as a popularity proxy
    daily_views = 3 + 8 * df["reviews_per_month"].clip(upper=5)
    df["views"] = rng.poisson(daily_views * DAYS)

    # Baseline conversion depends on rating and price, on the log-odds scale
    base_logit = np.log(BASELINE_CONVERSION / (1 - BASELINE_CONVERSION))
    quality = 0.15 * (df["review_rate_number"] - 3)
    price_penalty = -0.20 * np.log(df["price"] / df["price"].median())
    logit = base_logit + quality + price_penalty

    is_treated = (df["experiment_group"] == "treatment").astype(int)
    logit = logit + is_treated * np.log(1 + TRUE_LIFT)

    df["conversion_prob"] = 1 / (1 + np.exp(-logit))
    df["bookings"] = rng.binomial(df["views"], df["conversion_prob"])
    df["revenue"] = df["bookings"] * df["price"]

    return df[["id", "experiment_group", "views", "bookings", "revenue"]]


def main() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        listings = pd.read_sql("SELECT * FROM listings", conn)
    print(f"Simulating {DAYS} days of traffic for {len(listings):,} listings...")

    results = simulate(listings)

    split = results["experiment_group"].value_counts(normalize=True)
    print("Group split:\n", split.round(4).to_string())

    with sqlite3.connect(DB_PATH) as conn:
        results.to_sql("ab_test_results", conn, if_exists="replace", index=False)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ab_id ON ab_test_results(id)")
    print(f"Wrote per-listing outcomes to {DB_PATH} (table: ab_test_results).")
    print(f"Ground-truth relative lift baked into the data: +{TRUE_LIFT:.0%}")


if __name__ == "__main__":
    main()
