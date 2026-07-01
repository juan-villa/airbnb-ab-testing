"""Clean the raw Kaggle Airbnb CSV and load it into SQLite."""

import sqlite3
import zipfile
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
RAW_ZIP = REPO_ROOT / "data" / "Airbnb_Open_Data.csv.zip"
RAW_CSV = REPO_ROOT / "data" / "Airbnb_Open_Data.csv"
DB_PATH = REPO_ROOT / "outputs" / "airbnb.db"

KEEP_COLUMNS = [
    "id",
    "host_identity_verified",
    "neighbourhood_group",
    "neighbourhood",
    "instant_bookable",
    "cancellation_policy",
    "room_type",
    "price",
    "service_fee",
    "minimum_nights",
    "number_of_reviews",
    "reviews_per_month",
    "review_rate_number",
    "availability_365",
]


def load_raw() -> pd.DataFrame:
    if not RAW_CSV.exists():
        with zipfile.ZipFile(RAW_ZIP) as zf:
            zf.extractall(RAW_CSV.parent)
    return pd.read_csv(RAW_CSV, low_memory=False)


def clean(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = (
        df.columns.str.strip().str.lower().str.replace(" ", "_", regex=False)
    )
    df = df[KEEP_COLUMNS].copy()

    for col in ["price", "service_fee"]:
        df[col] = pd.to_numeric(
            df[col].astype(str).str.replace(r"[$,\s]", "", regex=True),
            errors="coerce",
        )

    # The raw dataset contains misspelled borough names
    df["neighbourhood_group"] = df["neighbourhood_group"].replace(
        {"brookln": "Brooklyn", "manhatan": "Manhattan"}
    )

    before = len(df)
    df = df.dropna(subset=["price", "neighbourhood_group", "room_type"])
    df = df.drop_duplicates(subset="id", keep="first")
    print(f"Dropped {before - len(df):,} unusable/duplicate rows "
          f"({len(df):,} listings remain).")

    df["reviews_per_month"] = df["reviews_per_month"].fillna(0)
    df["number_of_reviews"] = df["number_of_reviews"].fillna(0)
    df["review_rate_number"] = df["review_rate_number"].fillna(
        df["review_rate_number"].median()
    )
    df = df[(df["price"] > 0) & (df["minimum_nights"].fillna(1) >= 0)]

    return df.reset_index(drop=True)


def main() -> None:
    raw = load_raw()
    print(f"Raw file: {len(raw):,} rows.")

    cleaned = clean(raw)

    DB_PATH.parent.mkdir(exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        cleaned.to_sql("listings", conn, if_exists="replace", index=False)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_listings_id ON listings(id)")
    print(f"Wrote {len(cleaned):,} cleaned listings to {DB_PATH} (table: listings).")


if __name__ == "__main__":
    main()
