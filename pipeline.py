"""
pipeline.py — Phase 2: Ingestion, Transformation & Load
Reads raw_calls.json, validates, cleans, transforms, loads to predixion.db
"""

import json
import sqlite3
import pandas as pd
from datetime import datetime, timezone, timedelta
import argparse
import sys

# --- Config ---
REQUIRED_FIELDS   = ["call_id", "agent_id", "customer_phone", "start_time",
                      "end_time", "call_outcome", "language", "disposition_code",
                      "retry_flag"]
# amount_promised is intentionally nullable — NOT in required fields

VALID_OUTCOMES     = {"connected", "no_answer", "dropped", "callback_requested"}
VALID_LANGUAGES    = {"Hindi", "English", "Marathi"}
VALID_DISPOSITIONS = {"SALE", "PROMISE_TO_PAY", "NOT_INTERESTED", "ESCALATED", "HANGUP"}
IST                = timezone(timedelta(hours=5, minutes=30))


# ─────────────────────────────────────────────
# STEP 1: Load raw JSON
# ─────────────────────────────────────────────
def load_raw(path: str) -> list[dict]:
    with open(path, "r") as f:
        return json.load(f)


# ─────────────────────────────────────────────
# STEP 2: Validate records
# ─────────────────────────────────────────────
def validate(records: list[dict]) -> tuple[pd.DataFrame, pd.DataFrame]:
    accepted = []
    rejected = []
    seen_call_ids = {}  # call_id -> index in accepted list (for duplicate detection)

    for i, rec in enumerate(records):
        reason = None

        # Check missing required fields
        missing = [f for f in REQUIRED_FIELDS if f not in rec]
        if missing:
            reason = f"missing_field: {', '.join(missing)}"
            rejected.append({**rec, "rejection_reason": reason})
            continue

        # Check field types
        if not isinstance(rec.get("retry_flag"), bool):
            reason = "bad_type: retry_flag must be boolean"
            rejected.append({**rec, "rejection_reason": reason})
            continue

        if rec.get("call_outcome") not in VALID_OUTCOMES:
            reason = f"bad_type: invalid call_outcome '{rec.get('call_outcome')}'"
            rejected.append({**rec, "rejection_reason": reason})
            continue

        if rec.get("language") not in VALID_LANGUAGES:
            reason = f"bad_type: invalid language '{rec.get('language')}'"
            rejected.append({**rec, "rejection_reason": reason})
            continue

        if rec.get("disposition_code") not in VALID_DISPOSITIONS:
            reason = f"bad_type: invalid disposition_code '{rec.get('disposition_code')}'"
            rejected.append({**rec, "rejection_reason": reason})
            continue

        # Check for duplicate call_id — keep latest by start_time (handled in transform)
        # Flag exact duplicates (same call_id seen before) for the rejected log
        cid = rec.get("call_id")
        if cid in seen_call_ids:
            reason = f"duplicate: call_id {cid} already seen"
            rejected.append({**rec, "rejection_reason": reason})
            continue

        seen_call_ids[cid] = len(accepted)
        accepted.append(rec)

    df_accepted = pd.DataFrame(accepted) if accepted else pd.DataFrame()
    df_rejected = pd.DataFrame(rejected) if rejected else pd.DataFrame()
    return df_accepted, df_rejected


# ─────────────────────────────────────────────
# STEP 3: Transform
# ─────────────────────────────────────────────
def transform(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    additional_rejected = []

    # Parse timestamps — coerce malformed to NaT
    df["start_time"] = pd.to_datetime(df["start_time"], errors="coerce", utc=False)
    df["end_time"]   = pd.to_datetime(df["end_time"],   errors="coerce", utc=False)

    # Reject records with unparseable timestamps
    bad_ts_mask = df["start_time"].isna() | df["end_time"].isna()
    bad_ts = df[bad_ts_mask].copy()
    bad_ts["rejection_reason"] = "malformed_timestamp"
    additional_rejected.append(bad_ts)
    df = df[~bad_ts_mask].copy()

    # Compute duration — reject negative durations
    df["call_duration_seconds"] = (df["end_time"] - df["start_time"]).dt.total_seconds()
    neg_dur_mask = df["call_duration_seconds"] < 0
    neg_dur = df[neg_dur_mask].copy()
    neg_dur["rejection_reason"] = "negative_duration"
    additional_rejected.append(neg_dur)
    df = df[~neg_dur_mask].copy()

    # Normalize timestamps to IST
    df["start_time"] = df["start_time"].dt.tz_localize("UTC").dt.tz_convert(IST)
    df["end_time"]   = df["end_time"].dt.tz_localize("UTC").dt.tz_convert(IST)

    # Derive fields
    df["call_hour"]  = df["start_time"].dt.hour
    df["call_date"]  = df["start_time"].dt.date.astype(str)
    df["is_weekend"] = df["start_time"].dt.dayofweek >= 5  # 5=Sat, 6=Sun

    # Duration bucket
    def bucket(s):
        if s < 60:   return "short"
        if s <= 300: return "medium"
        return "long"
    df["duration_bucket"] = df["call_duration_seconds"].apply(bucket)

    # Impute amount_promised
    df["is_amount_imputed"] = df["amount_promised"].isna()
    df["amount_promised"]   = df["amount_promised"].fillna(0)

    # Stringify timestamps for SQLite storage
    df["start_time"] = df["start_time"].astype(str)
    df["end_time"]   = df["end_time"].astype(str)

    # Combine additional rejected records
    df_extra_rejected = pd.concat(additional_rejected, ignore_index=True) if additional_rejected else pd.DataFrame()

    return df, df_extra_rejected


# ─────────────────────────────────────────────
# STEP 4: Load to SQLite (idempotent)
# ─────────────────────────────────────────────
def load_to_db(df_clean: pd.DataFrame, rejected_count: int, db_path: str):
    conn = sqlite3.connect(db_path)
    cur  = conn.cursor()

    # Create calls table with call_id as PRIMARY KEY
    cur.execute("""
        CREATE TABLE IF NOT EXISTS calls (
            call_id              TEXT PRIMARY KEY,
            agent_id             TEXT,
            customer_phone       TEXT,
            start_time           TEXT,
            end_time             TEXT,
            call_outcome         TEXT,
            language             TEXT,
            disposition_code     TEXT,
            amount_promised      REAL,
            retry_flag           INTEGER,
            call_duration_seconds REAL,
            call_hour            INTEGER,
            call_date            TEXT,
            is_weekend           INTEGER,
            duration_bucket      TEXT,
            is_amount_imputed    INTEGER
        )
    """)

    # Create ingestion_log table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS ingestion_log (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            run_timestamp     TEXT,
            records_processed INTEGER,
            records_rejected  INTEGER,
            records_loaded    INTEGER
        )
    """)
    conn.commit()

    # INSERT OR REPLACE for idempotency
    for _, row in df_clean.iterrows():
        cur.execute("""
            INSERT OR REPLACE INTO calls VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
        """, (
            row["call_id"], row["agent_id"], row["customer_phone"],
            row["start_time"], row["end_time"], row["call_outcome"],
            row["language"], row["disposition_code"], row["amount_promised"],
            int(row["retry_flag"]), row["call_duration_seconds"],
            int(row["call_hour"]), row["call_date"], int(row["is_weekend"]),
            row["duration_bucket"], int(row["is_amount_imputed"])
        ))

    # Log this run
    cur.execute("""
        INSERT INTO ingestion_log (run_timestamp, records_processed, records_rejected, records_loaded)
        VALUES (?, ?, ?, ?)
    """, (
        datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S %Z"),
        len(df_clean) + rejected_count,
        rejected_count,
        len(df_clean)
    ))

    conn.commit()
    conn.close()


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main(input_path: str = "raw_calls.json", db_path: str = "predixion.db"):
    print("=" * 55)
    print("  pipeline.py — Predixion AI ETL Pipeline")
    print("=" * 55)

    # Load
    raw = load_raw(input_path)
    print(f"\n[1] Loaded {len(raw)} raw records from {input_path}")

    # Validate
    df_accepted, df_rejected_v = validate(raw)
    print(f"[2] Validation complete.")

    # Transform
    df_clean, df_rejected_t = transform(df_accepted)
    print(f"[3] Transformation complete.")

    # Combine all rejected
    df_all_rejected = pd.concat([df_rejected_v, df_rejected_t], ignore_index=True)
    total_rejected  = len(df_all_rejected)
    total_loaded    = len(df_clean)

    # Save rejected log
    if not df_all_rejected.empty:
        df_all_rejected.to_csv("rejected_log.csv", index=False)
        print(f"[4] Rejected log saved to rejected_log.csv")

    # Load to DB
    load_to_db(df_clean, total_rejected, db_path)
    print(f"[5] Loaded to {db_path}")

    # Summary
    print("\n" + "=" * 55)
    print("  PIPELINE SUMMARY")
    print("=" * 55)
    print(f"  Total raw records     : {len(raw)}")
    print(f"  Total loaded (clean)  : {total_loaded}")
    print(f"  Total rejected        : {total_rejected}")

    if not df_all_rejected.empty and "rejection_reason" in df_all_rejected.columns:
        print("\n  Rejection Breakdown:")
        breakdown = df_all_rejected["rejection_reason"].str.split(":").str[0].value_counts()
        for reason, count in breakdown.items():
            print(f"    {reason:<25} : {count}")
    print("=" * 55)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Predixion AI ETL Pipeline")
    parser.add_argument("--input",   default="raw_calls.json", help="Path to raw JSON input")
    parser.add_argument("--db-path", default="predixion.db",   help="Path to SQLite database")
    args = parser.parse_args()
    main(input_path=args.input, db_path=args.db_path)
