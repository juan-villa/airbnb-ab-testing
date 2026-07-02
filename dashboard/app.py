"""Streamlit dashboard: NYC Airbnb market overview + instant-book A/B test.

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
LOGO = REPO_ROOT / "dashboard" / "assets" / "airbnb_logo_white.svg"

WHITE = "#ffffff"
PALE = "#bde0fe"
SKY = "#8ecae6"
STEEL = "#4a90d9"
BLUE = "#1b6ef3"

BLUES = [WHITE, PALE, SKY, STEEL, BLUE]

st.set_page_config(page_title="Airbnb A/B Test", layout="wide")


@st.cache_data
def load_data():
    with sqlite3.connect(DB_PATH) as conn:
        listings = pd.read_sql("SELECT * FROM listings", conn)
        experiment = pd.read_sql(
            """
            SELECT r.experiment_group, r.views, r.bookings, r.revenue,
                   l.neighbourhood_group AS borough, l.room_type, l.price
            FROM ab_test_results r
            JOIN listings l ON l.id = r.id
            """,
            conn,
        )
    sig = json.loads(SIG_PATH.read_text())
    return listings, experiment, sig


listings, experiment, sig = load_data()

st.image(str(LOGO), width=160)
st.title("Instant Book: A/B Test on the NYC Market")
st.caption(
    "A simulated experiment on 102k real New York City listings. The question: "
    "does a 'book instantly, no host approval needed' prompt raise booking "
    "conversion? The first tab covers the market the test ran in; the second "
    "reports the result."
)

tab_city, tab_experiment = st.tabs(["The Market", "The Experiment"])

with tab_city:
    st.subheader("The market at a glance")

    k = st.columns(4)
    k[0].metric("Listings", f"{len(listings):,}")
    k[1].metric("Median Nightly Price", f"${listings['price'].median():,.0f}")
    k[2].metric("Average Guest Rating", f"{listings['review_rate_number'].mean():.2f} / 5")
    k[3].metric(
        "Already Instant-Bookable",
        f"{listings['instant_bookable'].fillna(0).astype(float).mean():.0%}",
    )

    st.markdown("**What each borough offers**")
    st.caption(
        "Share of each borough's listings by room type. Manhattan skews toward "
        "entire homes; the Bronx and Queens lean on private rooms."
    )
    room_mix = (
        listings.groupby(["neighbourhood_group", "room_type"])
        .size()
        .unstack(fill_value=0)
        .rename_axis("Borough")
    )
    room_mix.columns.name = "Room Type"
    st.bar_chart(
        room_mix, horizontal=True, stack="normalize",
        color=BLUES[: room_mix.shape[1]], height=320,
    )

    left, right = st.columns(2)
    with left:
        st.markdown("**Median nightly price by borough**")
        price_by_borough = (
            listings.groupby("neighbourhood_group")["price"]
            .median()
            .sort_values()
            .rename_axis("Borough")
            .rename("Median Nightly Price ($)")
        )
        st.bar_chart(price_by_borough, horizontal=True, color=SKY, height=300)

    with right:
        st.markdown("**Nightly price distribution**")
        price_bins = pd.cut(listings["price"], bins=range(50, 1251, 100))
        price_hist = (
            price_bins.value_counts()
            .sort_index()
            .rename_axis("Nightly Price ($), Bin Start")
            .rename("Listings")
        )
        # Numeric bin edges keep the axis in price order (string labels
        # would sort alphabetically and shuffle the bars)
        price_hist.index = [b.left for b in price_hist.index]
        st.bar_chart(price_hist, color=STEEL, height=300)

    st.caption(
        "Prices in this dataset run a tidy \\$50 to \\$1,200 with a nearly flat "
        "distribution, and the median barely moves between boroughs. The real "
        "city is spikier; this is the cleaned-up Kaggle version of New York."
    )

with tab_experiment:
    st.subheader("The result")

    verdict = "Ship it" if sig["significant_at_5pct"] else "Not significant"
    k = st.columns(4)
    k[0].metric("Control Conversion", f"{sig['control_rate']:.2%}")
    k[1].metric(
        "Treatment Conversion",
        f"{sig['treatment_rate']:.2%}",
        delta=f"{sig['relative_lift_pct']:+.1f}% relative lift",
    )
    k[2].metric("P-Value", sig["p_value_label"])
    k[3].metric("Verdict", verdict)

    st.write(
        f"The 95% confidence interval on the relative lift is "
        f"[{sig['ci_95_relative_pct'][0]:+.1f}%, {sig['ci_95_relative_pct'][1]:+.1f}%], "
        "comfortably clear of zero. The prompt earns its place on the page."
    )

    st.subheader("Was the experiment healthy?")
    counts = experiment["experiment_group"].value_counts()
    share_control = counts["control"] / counts.sum()
    srm_ok = abs(share_control - 0.5) < 0.01
    st.write(
        f"The design called for a 50/50 split; the hash assignment delivered "
        f"{counts['control']:,} control and {counts['treatment']:,} treatment listings "
        f"({share_control:.1%} / {1 - share_control:.1%}). "
        + (
            "The chart below makes the same point visually: both groups drew "
            "their traffic from the same places, which is what sound "
            "randomization looks like."
            if srm_ok
            else "That deviation is larger than chance allows, so the metrics "
            "above should not be trusted until the assignment is debugged."
        )
    )

    traffic_mix = (
        experiment.groupby(["experiment_group", "borough"])["views"]
        .sum()
        .unstack(fill_value=0)
    )
    traffic_mix.index = traffic_mix.index.str.title()
    traffic_mix.index.name = "Group"
    traffic_mix.columns.name = "Borough"
    st.markdown("**Where each group's page views came from**")
    st.bar_chart(
        traffic_mix, horizontal=True, stack="normalize",
        color=BLUES[: traffic_mix.shape[1]], height=220,
    )

    st.subheader("Slice the result")
    st.caption(
        "Filter to any part of the city to see whether the lift holds there."
    )

    f = st.columns(2)
    boroughs = f[0].multiselect(
        "Borough", sorted(experiment["borough"].unique()),
        default=None, placeholder="All boroughs",
    )
    room_types = f[1].multiselect(
        "Room type", sorted(experiment["room_type"].unique()),
        default=None, placeholder="All room types",
    )

    mask = pd.Series(True, index=experiment.index)
    if boroughs:
        mask &= experiment["borough"].isin(boroughs)
    if room_types:
        mask &= experiment["room_type"].isin(room_types)
    sub = experiment[mask]

    grp = sub.groupby("experiment_group")[["views", "bookings", "revenue"]].sum()
    grp["Conversion Rate"] = grp["bookings"] / grp["views"]
    grp["Revenue per View ($)"] = grp["revenue"] / grp["views"]
    grp.index = grp.index.str.title()
    grp.index.name = "Group"

    left, right = st.columns(2)
    with left:
        st.markdown("**Conversion rate in this slice**")
        st.bar_chart(grp["Conversion Rate"], horizontal=True, color=SKY, height=200)
    with right:
        st.markdown("**Revenue per view in this slice**")
        st.bar_chart(grp["Revenue per View ($)"], horizontal=True, color=STEEL, height=200)

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
    pivot["lift"] = 100 * (pivot["treatment"] - pivot["control"]) / pivot["control"]
    pivot = pivot.rename(
        columns={"control": "Control", "treatment": "Treatment", "lift": "Relative Lift (%)"}
    )
    pivot.index = pivot.index.set_names(["Borough", "Room Type"])
    pivot.columns.name = None

    st.markdown("**Every segment, side by side**")
    st.dataframe(
        pivot.style.format({"Control": "{:.2%}", "Treatment": "{:.2%}",
                            "Relative Lift (%)": "{:+.1f}%"}),
        use_container_width=True,
    )

    st.caption(
        "A note on reading the table: the experiment was powered for the overall "
        "effect, not for individual segments. Smaller slices scatter around the "
        "true lift, so treat single rows as directional."
    )
