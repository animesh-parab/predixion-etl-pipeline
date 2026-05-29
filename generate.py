"""
generate.py — Phase 1: Raw call log data generation
Generates 500 raw JSON call records with injected noise.
Seed: 42 | Output: raw_calls.json
"""

import json
import random
import copy
from datetime import datetime, timedelta

random.seed(42)

# --- Constants ---
AGENTS        = [f"AGT{str(i).zfill(3)}" for i in range(1, 21)]   # 20 agents
OUTCOMES      = ["connected", "no_answer", "dropped", "callback_requested"]
LANGUAGES     = ["Hindi", "English", "Marathi"]
DISPOSITIONS  = ["SALE", "PROMISE_TO_PAY", "NOT_INTERESTED", "ESCALATED", "HANGUP"]
BASE_DATE     = datetime(2024, 1, 1, 0, 0, 0)

# Malformed timestamp variants
MALFORMED_TIMESTAMPS = [
    "2024-02-30T10:00:00",          # impossible date
    "30-13-2024 10:00:00",          # wrong format + invalid month
    "",                              # empty string
    "not-a-timestamp",              # garbage string
    "2024/01/15 25:61:00",          # invalid time
]


def random_phone() -> str:
    """Generate a standardized 10-digit phone number string."""
    return str(random.randint(6000000000, 9999999999))


def random_timestamps():
    """Generate valid start_time and end_time ensuring end > start."""
    offset_hours = random.randint(0, 23 * 60)
    start = BASE_DATE + timedelta(days=random.randint(0, 89), minutes=offset_hours)
    duration = random.randint(10, 900)  # 10s to 15min
    end = start + timedelta(seconds=duration)
    fmt = "%Y-%m-%dT%H:%M:%S"
    return start.strftime(fmt), end.strftime(fmt)


def generate_clean_record(call_id: int) -> dict:
    """Generate a single clean call record."""
    start, end = random_timestamps()
    amount = round(random.uniform(500, 50000), 2) if random.random() > 0.3 else None
    return {
        "call_id":        f"CALL{str(call_id).zfill(5)}",
        "agent_id":       random.choice(AGENTS),
        "customer_phone": random_phone(),
        "start_time":     start,
        "end_time":       end,
        "call_outcome":   random.choice(OUTCOMES),
        "language":       random.choice(LANGUAGES),
        "disposition_code": random.choice(DISPOSITIONS),
        "amount_promised": amount,
        "retry_flag":     random.choice([True, False]),
    }


def inject_missing_fields(records: list, count: int) -> list:
    """
    Inject missing fields into `count` records.
    Spreads across non-nullable fields to properly stress the validator.
    Skips amount_promised (intentionally nullable by design).
    """
    nullable_ok = {"amount_promised"}
    non_nullable = [k for k in records[0].keys() if k not in nullable_ok]

    indices = random.sample(range(len(records)), count)
    for idx in indices:
        field = random.choice(non_nullable)
        records[idx] = {k: v for k, v in records[idx].items() if k != field}
    return records


def inject_duplicates(records: list, count: int) -> list:
    """
    Inject `count` duplicate records by copying existing records exactly
    (same call_id). Appended at the end so dedup logic can detect them.
    """
    sources = random.sample(records, count)
    dupes = [copy.deepcopy(r) for r in sources]
    records.extend(dupes)
    return records


def inject_malformed_timestamps(records: list, count: int) -> list:
    """
    Inject malformed timestamps into `count` records.
    Mix of: impossible dates, empty strings, wrong formats, garbage.
    Targets start_time or end_time randomly.
    """
    indices = random.sample(range(len(records)), count)
    for idx in indices:
        bad_ts = random.choice(MALFORMED_TIMESTAMPS)
        field  = random.choice(["start_time", "end_time"])
        if field in records[idx]:
            records[idx][field] = bad_ts
    return records


def main():
    TOTAL_TARGET   = 500
    CLEAN_COUNT    = 450
    DUPLICATE_COUNT  = 25   # 5% of 500
    MISSING_COUNT    = 75   # 15% of 500 (applied to clean records)
    MALFORMED_COUNT  = 15   # 3% of 500 (applied after duplicates)

    print("=" * 50)
    print("  generate.py — Predixion AI ETL Assignment")
    print("=" * 50)

    # Step 1: Generate 450 clean records
    records = [generate_clean_record(i + 1) for i in range(CLEAN_COUNT)]
    print(f"[1] Generated {CLEAN_COUNT} clean base records.")

    # Step 2: Inject missing fields (~15%)
    records = inject_missing_fields(records, MISSING_COUNT)
    print(f"[2] Injected missing fields into {MISSING_COUNT} records.")

    # Step 3: Inject duplicates (~5%) — appended, brings total to 475
    records = inject_duplicates(records, DUPLICATE_COUNT)
    print(f"[3] Injected {DUPLICATE_COUNT} duplicate records. Total: {len(records)}")

    # Step 4: Inject malformed timestamps (~3%) — applied across full set
    records = inject_malformed_timestamps(records, MALFORMED_COUNT)
    print(f"[4] Injected malformed timestamps into {MALFORMED_COUNT} records.")

    # Step 5: Pad to exactly 500 with extra clean records if needed
    while len(records) < TOTAL_TARGET:
        records.append(generate_clean_record(CLEAN_COUNT + len(records)))
    records = records[:TOTAL_TARGET]

    # Step 6: Shuffle to mix noise throughout
    random.shuffle(records)
    print(f"[5] Final record count: {len(records)}")

    # Step 7: Save to raw_calls.json
    output_path = "raw_calls.json"
    with open(output_path, "w") as f:
        json.dump(records, f, indent=2, default=str)

    print(f"\n✅ Saved to {output_path}")
    print("\n--- Injection Summary ---")
    print(f"  Total records      : {len(records)}")
    print(f"  Clean base records : {CLEAN_COUNT}")
    print(f"  Missing fields     : ~{MISSING_COUNT} records ({MISSING_COUNT/TOTAL_TARGET*100:.0f}%)")
    print(f"  Duplicates         : ~{DUPLICATE_COUNT} records ({DUPLICATE_COUNT/TOTAL_TARGET*100:.0f}%)")
    print(f"  Malformed timestamps: ~{MALFORMED_COUNT} records ({MALFORMED_COUNT/TOTAL_TARGET*100:.0f}%)")
    print("=" * 50)


if __name__ == "__main__":
    main()
