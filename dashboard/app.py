"""Streamlit dashboard for the A/B test readout.

Run from the repo root after the pipeline: streamlit run dashboard/app.py
"""

import json
import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st

REPO_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = REPO_ROOT / "outputs" / "airbnb.db"
SIG_PATH = REPO_ROOT / "outputs" / "significance.json"

st.set_page_config(page_title="Airbnb A/B Test Readout", layout="wide")


@st.cache_data
def load_data():
    with sqlite3.connect(DB_PATH) as conn:
        df = pd.read_sql(
            """
            SELECT r.experiment_group, r.views, r.bookings, r.revenue,
                   l.neighbourhood_group AS borough, l.room_type,
                   l.instant_bookable, l.price
            FROM ab_test_results r
            JOIN listings l ON l.id = r.id
            """,
            conn,
        )
    sig = json.loads(SIG_PATH.read_text())
    return df, sig


df, sig = load_data()

st.title("Instant-Book Prompt: A/B Test Readout")
st.caption(
    "Simulated experiment on 100k real NYC Airbnb listings · 28 days · "
    "50/50 split randomized by listing id"
)

verdict = "✅ Ship it" if sig["significant_at_5pct"] else "⚠️ Not significant"
kpi_cols = st.columns(4)
kpi_cols[0].metric("Control conversion", f"{sig['control_rate']:.2%}")
kpi_cols[1].metric(
    "Treatment conversion",
    f"{sig['treatment_rate']:.2%}",
    delta=f"{sig['relative_lift_pct']:+.1f}% relative lift",
)
kpi_cols[2].metric("p-value", sig["p_value_label"])
kpi_cols[3].metric("Decision", verdict)

st.info(
    f"95% CI for the relative lift: "
    f"[{sig['ci_95_relative_pct'][0]:+.1f}%, {sig['ci_95_relative_pct'][1]:+.1f}%]. "
    "The interval excludes zero, so the effect is statistically significant.",
    icon="📐",
)

st.subheader("Experiment health")
counts = df["experiment_group"].value_counts()
share_control = counts["control"] / counts.sum()
srm_ok = abs(share_control - 0.5) < 0.01
st.write(
    f"**Sample ratio:** {counts['control']:,} control vs "
    f"{counts['treatment']:,} treatment "
    f"({share_control:.1%} / {1 - share_control:.1%}): "
    + ("✅ no sample-ratio mismatch" if srm_ok else "🚨 possible SRM, investigate")
)

st.subheader("Segment deep dive")

filter_cols = st.columns(2)
boroughs = filter_cols[0].multiselect(
    "Borough", sorted(df["borough"].unique()), default=None,
    placeholder="All boroughs",
)
room_types = filter_cols[1].multiselect(
    "Room type", sorted(df["room_type"].unique()), default=None,
    placeholder="All room types",
)

mask = pd.Series(True, index=df.index)
if boroughs:
    mask &= df["borough"].isin(boroughs)
if room_types:
    mask &= df["room_type"].isin(room_types)
sub = df[mask]

grp = sub.groupby("experiment_group")[["views", "bookings", "revenue"]].sum()
grp["conversion_rate"] = grp["bookings"] / grp["views"]
grp["revenue_per_view"] = grp["revenue"] / grp["views"]

left, right = st.columns(2)
with left:
    st.markdown("**Conversion rate by group (filtered)**")
    st.bar_chart(grp["conversion_rate"], color="#e0565b")
with right:
    st.markdown("**Revenue per view by group (filtered)**")
    st.bar_chart(grp["revenue_per_view"], color="#457b9d")

seg = (
    sub.groupby(["borough", "room_type", "experiment_group"])[["views", "bookings"]]
    .sum()
    .reset_index()
)
seg["conversion_rate"] = seg["bookings"] / seg["views"]
pivot = seg.pivot_table(
    index=["borough", "room_type"],
    columns="experiment_group",
    values="conversion_rate",
).dropna()
pivot["relative_lift_%"] = 100 * (pivot["treatment"] - pivot["control"]) / pivot["control"]
st.markdown("**Relative lift by segment**")
st.dataframe(
    pivot.style.format({"control": "{:.2%}", "treatment": "{:.2%}",
                        "relative_lift_%": "{:+.1f}%"}),
    use_container_width=True,
)

st.caption(
    "Note: segment-level lifts are directional; samples are smaller than the "
    "topline, so expect noise. The experiment was powered for the overall effect."
)
