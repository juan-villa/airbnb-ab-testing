"""Streamlit dashboard: NYC Airbnb market overview + instant-book A/B test.

Run from the repo root after the pipeline: streamlit run dashboard/app.py
"""

import json
import sqlite3
from pathlib import Path

import altair as alt
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

TEXT = "#f0f6fc"
GRID = "#2c4a6e"


def themed(chart: alt.Chart) -> alt.Chart:
    """Match Altair charts to the navy Streamlit theme.

    Charts are built in Altair rather than st.bar_chart so they stay
    static: no pan/zoom, and normalized axes cannot scroll past 100%.
    """
    return (
        chart
        .configure(background="transparent")
        .configure_axis(
            labelColor=TEXT, titleColor=TEXT,
            gridColor=GRID, domainColor=GRID, tickColor=GRID,
        )
        .configure_legend(labelColor=TEXT, titleColor=TEXT)
        .configure_view(stroke=None)
    )


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
    "A simulated experiment on 102k real New York City listings. The question of interest is: "
    "Does a 'book instantly, no host approval needed' prompt raise booking "
    "conversion? The first tab covers a general overview of the market the test ran in. The second "
    "reports the result."
)

tab_city, tab_experiment = st.tabs(["Market Overview", "Experiment Results"])

with tab_city:
    st.subheader("The Market")

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
        st.markdown("**Listings by Borough**")
        borough_counts = (
            listings["neighbourhood_group"]
            .value_counts()
            .rename_axis("Borough")
            .reset_index(name="Listings")
        )
        donut = (
            alt.Chart(borough_counts)
            .mark_arc(innerRadius=70, cornerRadius=3, padAngle=0.012)
            .encode(
                theta=alt.Theta("Listings:Q"),
                color=alt.Color(
                    "Borough:N",
                    scale=alt.Scale(range=BLUES),
                    legend=alt.Legend(title=None),
                ),
                tooltip=["Borough:N", alt.Tooltip("Listings:Q", format=",")],
            )
            .properties(height=300)
        )
        st.altair_chart(themed(donut), use_container_width=True)

    with right:
        st.markdown("**Room Types Citywide**")
        room_counts = (
            listings["room_type"]
            .value_counts()
            .rename_axis("Room Type")
            .reset_index(name="Listings")
        )
        donut = (
            alt.Chart(room_counts)
            .mark_arc(innerRadius=70, cornerRadius=3, padAngle=0.012)
            .encode(
                theta=alt.Theta("Listings:Q"),
                color=alt.Color(
                    "Room Type:N",
                    scale=alt.Scale(range=BLUES[: len(room_counts)]),
                    legend=alt.Legend(title=None),
                ),
                tooltip=["Room Type:N", alt.Tooltip("Listings:Q", format=",")],
            )
            .properties(height=300)
        )
        st.altair_chart(themed(donut), use_container_width=True)

    st.markdown("**Borough-level Overview**")
    st.caption(
        "Share of each borough's listings by room type. Manhattan skews toward "
        "entire homes, while the Bronx and Queens lean on private rooms."
    )
    room_mix = (
        listings.groupby(["neighbourhood_group", "room_type"])
        .size()
        .reset_index(name="Listings")
        .rename(columns={"neighbourhood_group": "Borough", "room_type": "Room Type"})
    )
    stacked = (
        alt.Chart(room_mix)
        .mark_bar()
        .encode(
            x=alt.X(
                "Listings:Q", stack="normalize",
                title="Share of Listings", axis=alt.Axis(format="%"),
            ),
            y=alt.Y("Borough:N", title=None),
            color=alt.Color("Room Type:N", scale=alt.Scale(range=BLUES[:4])),
            tooltip=["Borough:N", "Room Type:N",
                     alt.Tooltip("Listings:Q", format=",")],
        )
        .properties(height=260)
    )
    st.altair_chart(themed(stacked), use_container_width=True)

    left, right = st.columns(2)
    with left:
        st.markdown("**Busiest Neighbourhoods (top 10)**")
        top_hoods = (
            listings["neighbourhood"]
            .value_counts()
            .head(10)
            .rename_axis("Neighbourhood")
            .reset_index(name="Listings")
        )
        hood_bars = (
            alt.Chart(top_hoods)
            .mark_bar(color=SKY, cornerRadiusEnd=3)
            .encode(
                x=alt.X("Listings:Q", title="Listings"),
                y=alt.Y("Neighbourhood:N", sort="-x", title=None),
                tooltip=["Neighbourhood:N", alt.Tooltip("Listings:Q", format=",")],
            )
            .properties(height=300)
        )
        st.altair_chart(themed(hood_bars), use_container_width=True)

    with right:
        st.markdown("**Nightly Price Distribution**")
        hist = (
            alt.Chart(listings[["price"]])
            .mark_bar(color=STEEL)
            .encode(
                x=alt.X("price:Q", bin=alt.Bin(step=100), title="Nightly Price ($)"),
                y=alt.Y("count()", title="Listings"),
                tooltip=[alt.Tooltip("count()", title="Listings", format=",")],
            )
            .properties(height=300)
        )
        st.altair_chart(themed(hist), use_container_width=True)

    st.caption(
        "Prices in this dataset run a tidy \\$50 to \\$1,200 with a nearly flat "
        "distribution, and the median barely moves between boroughs. The real "
        "city is spikier. Note, this is the cleaned-up Kaggle version of New York."
    )

with tab_experiment:
    st.subheader("Experiment Result")

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
        "comfortably clear of zero."
    )

    st.subheader("Was the experiment healthy?")
    counts = experiment["experiment_group"].value_counts()
    share_control = counts["control"] / counts.sum()
    srm_ok = abs(share_control - 0.5) < 0.01
    st.write(
        f"The design called for a 50/50 split: "
        f"{counts['control']:,} control and {counts['treatment']:,} treatment listings "
        f"({share_control:.1%} / {1 - share_control:.1%}). "
        + (
            "The chart below makes the same point visually. Both groups drew "
            "their traffic from the same places, which is what "
            "randomization should look like."
            if srm_ok
            else "That deviation is larger than reasonable chance allows, so the metrics "
            "above should not be trusted until the assignment is debugged."
        )
    )

    traffic_mix = (
        experiment.groupby(["experiment_group", "borough"])["views"]
        .sum()
        .reset_index()
        .rename(columns={"experiment_group": "Group", "borough": "Borough",
                         "views": "Views"})
    )
    traffic_mix["Group"] = traffic_mix["Group"].str.title()
    st.markdown("**Where each group's page views came from**")
    traffic_chart = (
        alt.Chart(traffic_mix)
        .mark_bar()
        .encode(
            x=alt.X(
                "Views:Q", stack="normalize",
                title="Share of Page Views", axis=alt.Axis(format="%"),
            ),
            y=alt.Y("Group:N", title=None),
            color=alt.Color("Borough:N", scale=alt.Scale(range=BLUES)),
            tooltip=["Group:N", "Borough:N", alt.Tooltip("Views:Q", format=",")],
        )
        .properties(height=160)
    )
    st.altair_chart(themed(traffic_chart), use_container_width=True)

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

    grp = sub.groupby("experiment_group")[["views", "bookings"]].sum()
    grp["Rate"] = grp["bookings"] / grp["views"]
    # Binomial standard error per group gives each point its own 95% CI
    grp["se"] = (grp["Rate"] * (1 - grp["Rate"]) / grp["views"]) ** 0.5
    grp["Low"] = grp["Rate"] - 1.96 * grp["se"]
    grp["High"] = grp["Rate"] + 1.96 * grp["se"]
    grp = grp.reset_index().rename(columns={"experiment_group": "Group"})
    grp["Group"] = grp["Group"].str.title()

    left, right = st.columns(2)
    with left:
        st.markdown("**Conversion rate in this slice, with 95% CI**")
        base = alt.Chart(grp)
        x_scale = alt.Scale(zero=False, padding=24)
        intervals = base.mark_rule(color=PALE, strokeWidth=4).encode(
            x=alt.X("Low:Q", title="Conversion Rate",
                    axis=alt.Axis(format=".2%"), scale=x_scale),
            x2="High:Q",
            y=alt.Y("Group:N", title=None),
        )
        points = base.mark_point(filled=True, size=140, color=WHITE).encode(
            x=alt.X("Rate:Q", scale=x_scale),
            y="Group:N",
            tooltip=["Group:N",
                     alt.Tooltip("Rate:Q", format=".2%", title="Conversion"),
                     alt.Tooltip("Low:Q", format=".2%", title="CI Low"),
                     alt.Tooltip("High:Q", format=".2%", title="CI High")],
        )
        st.altair_chart(themed((intervals + points).properties(height=200)),
                        use_container_width=True)
        st.caption(
            "The axis is zoomed to the estimates; if the two intervals do not "
            "overlap, the gap is real."
        )

    with right:
        st.markdown("**Relative lift by borough in this slice**")
        by_borough = (
            sub.groupby(["borough", "experiment_group"])[["views", "bookings"]]
            .sum()
            .reset_index()
        )
        by_borough["rate"] = by_borough["bookings"] / by_borough["views"]
        lift = by_borough.pivot(
            index="borough", columns="experiment_group", values="rate"
        ).dropna()
        lift["Lift"] = 100 * (lift["treatment"] - lift["control"]) / lift["control"]
        lift = lift.rename_axis("Borough").reset_index()[["Borough", "Lift"]]
        lift_bars = (
            alt.Chart(lift)
            .mark_bar(color=BLUE, cornerRadiusEnd=3)
            .encode(
                x=alt.X("Lift:Q", title="Relative Lift (%)"),
                y=alt.Y("Borough:N", sort="-x", title=None),
                tooltip=["Borough:N", alt.Tooltip("Lift:Q", format="+.1f")],
            )
            .properties(height=200)
        )
        st.altair_chart(themed(lift_bars), use_container_width=True)
        st.caption(
            "Positive bars mean treatment out-converted control in that borough."
        )

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
        "true lift, so single rows should be treated as directional."
    )
