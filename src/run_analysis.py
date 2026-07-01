"""Run the SQL readout, significance testing, and presentation charts."""

import json
import sqlite3
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy import stats

REPO_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = REPO_ROOT / "outputs" / "airbnb.db"
SQL_DIR = REPO_ROOT / "sql"
OUT_DIR = REPO_ROOT / "outputs"

sns.set_theme(style="whitegrid", context="notebook")
plt.rcParams.update({
    "font.family": "serif",
    "mathtext.fontset": "cm",
    "axes.titlesize": 15,
    "axes.titleweight": "bold",
    "axes.titlepad": 12,
    "axes.labelsize": 12,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "legend.fontsize": 10,
    "axes.edgecolor": "#333333",
    "axes.linewidth": 0.8,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "grid.color": "#b0b0b0",
    "grid.linewidth": 0.5,
    "grid.alpha": 0.35,
    "figure.dpi": 120,
    "savefig.dpi": 200,
    "savefig.bbox": "tight",
})

ACCENT = "#1b3b6f"       # deep navy for the treatment series
NEUTRAL = "#999999"      # grey for the control baseline
POSITIVE = "#1a7f37"     # green / red for signed lift values
NEGATIVE = "#c1121f"

COLORS = {"control": NEUTRAL, "treatment": ACCENT}


def run_sql_files(conn: sqlite3.Connection) -> dict[str, pd.DataFrame]:
    """Execute every query in sql/ and save each result to outputs/ as CSV."""
    results = {}
    for sql_file in sorted(SQL_DIR.glob("*.sql")):
        df = pd.read_sql(sql_file.read_text(), conn)
        df.to_csv(OUT_DIR / f"{sql_file.stem}.csv", index=False)
        results[sql_file.stem] = df
        print(f"\n=== {sql_file.stem} ===")
        print(df.to_string(index=False))
    return results


def significance_test(conn: sqlite3.Connection) -> dict:
    """Two-proportion z-test and 95% CI on the conversion lift."""
    grp = pd.read_sql(
        """
        SELECT experiment_group,
               SUM(views)    AS views,
               SUM(bookings) AS bookings
        FROM ab_test_results
        GROUP BY experiment_group
        """,
        conn,
    ).set_index("experiment_group")

    n_c, x_c = grp.loc["control", ["views", "bookings"]]
    n_t, x_t = grp.loc["treatment", ["views", "bookings"]]
    p_c, p_t = x_c / n_c, x_t / n_t

    p_pool = (x_c + x_t) / (n_c + n_t)
    se_pool = np.sqrt(p_pool * (1 - p_pool) * (1 / n_c + 1 / n_t))
    z = (p_t - p_c) / se_pool
    p_value = 2 * stats.norm.sf(abs(z))

    se_diff = np.sqrt(p_c * (1 - p_c) / n_c + p_t * (1 - p_t) / n_t)
    ci_low, ci_high = (p_t - p_c) + np.array([-1.96, 1.96]) * se_diff

    summary = {
        "control_rate": round(p_c, 5),
        "treatment_rate": round(p_t, 5),
        "absolute_lift": round(p_t - p_c, 5),
        "relative_lift_pct": round(100 * (p_t - p_c) / p_c, 2),
        "z_statistic": round(z, 2),
        "p_value": float(f"{p_value:.2e}"),
        "p_value_label": "< 1e-300" if p_value == 0 else f"{p_value:.1e}",
        "ci_95_absolute": [round(ci_low, 5), round(ci_high, 5)],
        "ci_95_relative_pct": [
            round(100 * ci_low / p_c, 2),
            round(100 * ci_high / p_c, 2),
        ],
        "significant_at_5pct": bool(p_value < 0.05),
    }

    (OUT_DIR / "significance.json").write_text(json.dumps(summary, indent=2))
    print("\n=== significance test (two-proportion z-test) ===")
    print(json.dumps(summary, indent=2))
    return summary


def chart_conversion(sig: dict) -> None:
    fig, ax = plt.subplots(figsize=(7, 4.5))
    rates = [sig["control_rate"], sig["treatment_rate"]]
    bars = ax.bar(["Control", "Treatment"], rates,
                  color=[COLORS["control"], COLORS["treatment"]], width=0.55)
    for bar, rate in zip(bars, rates):
        ax.text(bar.get_x() + bar.get_width() / 2, rate, f"{rate:.2%}",
                ha="center", va="bottom", fontsize=12, fontweight="bold")
    ax.set_ylabel("Booking conversion rate")
    ax.set_title(
        f"Instant-book prompt lifted conversion "
        f"{sig['relative_lift_pct']:+.1f}% (p {sig['p_value_label']})",
        fontsize=12,
    )
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:.1%}")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "chart_conversion_by_group.png", facecolor="white")
    plt.close(fig)


def chart_segment_lift(segments: pd.DataFrame) -> None:
    df = segments.sort_values("relative_lift_pct")
    labels = df["borough"] + " - " + df["room_type"]
    fig, ax = plt.subplots(figsize=(8, 0.45 * len(df) + 1.5))
    colors = [POSITIVE if v > 0 else NEGATIVE for v in df["relative_lift_pct"]]
    ax.barh(labels, df["relative_lift_pct"], color=colors)
    ax.axvline(0, color="#333333", linewidth=0.8)
    ax.set_xlabel("Relative lift in conversion (%)")
    ax.set_title("Lift is broad-based across boroughs and room types")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "chart_segment_lift.png", facecolor="white")
    plt.close(fig)


def chart_revenue(group_summary: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(7, 4.5))
    df = group_summary.set_index("experiment_group")
    vals = [df.loc["control", "revenue_per_view"],
            df.loc["treatment", "revenue_per_view"]]
    bars = ax.bar(["Control", "Treatment"], vals,
                  color=[COLORS["control"], COLORS["treatment"]], width=0.55)
    for bar, v in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width() / 2, v, f"${v:.2f}",
                ha="center", va="bottom", fontsize=12, fontweight="bold")
    ax.set_ylabel("Booking revenue per page view ($)")
    ax.set_title("Secondary metric: revenue per view moved with conversion")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "chart_revenue_per_view.png", facecolor="white")
    plt.close(fig)


def main() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        sql_results = run_sql_files(conn)
        sig = significance_test(conn)

    chart_conversion(sig)
    chart_segment_lift(sql_results["03_segment_breakdown"])
    chart_revenue(sql_results["01_group_summary"])
    print(f"\nSaved readout CSVs, significance.json and 3 charts to {OUT_DIR}/")


if __name__ == "__main__":
    main()
