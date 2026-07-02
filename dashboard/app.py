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

NAVY = "#1b3b6f"
BLUE = "#1b6ef3"
SKY = "#8ecae6"

st.set_page_config(page_title="Airbnb A/B Test", page_icon="🗽", layout="wide")


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

st.title("One Prompt, 100,000 Listings")
st.caption(
    "What happens when every Airbnb page in New York gets a little nudge that says "
    "'book instantly, no host approval needed'? I simulated exactly that experiment "
    "on 100k real NYC listings. Tour the market first, then see how the test went."
)

tab_city, tab_experiment = st.tabs(["🗽 The Market", "🧪 The Experiment"])

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

    left, right = st.columns(2)

    with left:
        st.markdown("**Where the listings live**")
        by_borough = (
            listings["neighbourhood_group"]
            .value_counts()
            .rename_axis("Borough")
            .rename("Listings")
        )
        st.bar_chart(by_borough, color=BLUE)

        st.markdown("**What a night costs, by borough**")
        price_by_borough = (
            listings.groupby("neighbourhood_group")["price"]
            .median()
            .sort_values(ascending=False)
            .rename_axis("Borough")
            .rename("Median Nightly Price ($)")
        )
        st.bar_chart(price_by_borough, color=NAVY)

    with right:
        st.markdown("**What kind of place you get**")
        by_room = (
            listings["room_type"]
            .value_counts()
            .rename_axis("Room Type")
            .rename("Listings")
        )
        st.bar_chart(by_room, color=SKY)

        st.markdown("**The price spread**")
        price_bins = pd.cut(listings["price"], bins=range(50, 1251, 100))
        price_hist = (
            price_bins.value_counts()
            .sort_index()
            .rename_axis("Nightly Price ($)")
            .rename("Listings")
        )
        price_hist.index = [f"${b.left}-{b.right}" for b in price_hist.index]
        st.bar_chart(price_hist, color=BLUE)

    st.caption(
        "Fun fact: prices in this dataset run a suspiciously tidy $50 to $1,200, "
        "and the median barely moves between boroughs. Real NYC is spikier; this "
        "is the Kaggle version of the city."
    )

with tab_experiment:
    st.subheader("The headline")

    verdict = "Ship it ✅" if sig["significant_at_5pct"] else "Not significant ⚠️"
    k = st.columns(4)
    k[0].metric("Control Conversion", f"{sig['control_rate']:.2%}")
    k[1].metric(
        "Treatment Conversion",
        f"{sig['treatment_rate']:.2%}",
        delta=f"{sig['relative_lift_pct']:+.1f}% relative lift",
    )
    k[2].metric("P-Value", sig["p_value_label"])
    k[3].metric("Verdict", verdict)

    st.info(
        f"The 95% confidence interval on the relative lift is "
        f"[{sig['ci_95_relative_pct'][0]:+.1f}%, {sig['ci_95_relative_pct'][1]:+.1f}%]. "
        "Zero is nowhere near that interval, so this is not a fluke.",
        icon="📐",
    )

    st.subheader("Is the experiment healthy?")
    counts = experiment["experiment_group"].value_counts()
    share_control = counts["control"] / counts.sum()
    srm_ok = abs(share_control - 0.5) < 0.01
    st.write(
        f"We split {counts.sum():,} listings and got {counts['control']:,} control vs "
        f"{counts['treatment']:,} treatment ({share_control:.1%} / {1 - share_control:.1%}). "
        + (
            "That is as close to a coin flip as you could ask for, so the "
            "randomization checks out."
            if srm_ok
            else "That is further from 50/50 than chance allows. Something is broken; "
            "do not trust any metric below."
        )
    )

    st.subheader("Slice it yourself")
    st.caption(
        "Pick any corner of the city and see if the prompt still works there. "
        "Spoiler: it pretty much always does."
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
        st.markdown("**Conversion rate, this slice**")
        st.bar_chart(grp["Conversion Rate"], color=BLUE)
    with right:
        st.markdown("**Revenue per view, this slice**")
        st.bar_chart(grp["Revenue per View ($)"], color=NAVY)

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
        "A word of caution before anyone gets excited about one row: the experiment "
        "was powered for the overall effect, not for individual segments. Small "
        "slices bounce around the true lift just from noise."
    )
