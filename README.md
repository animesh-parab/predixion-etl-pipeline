# Predixion AI — Data Engineering Take-Home Assignment

End-to-end ETL pipeline that ingests raw, messy voice agent call logs, transforms them into a clean analytical layer, and answers business questions on top of it.

**Tech stack:** Python 3.10+ · Pandas · SQLite (`sqlite3`) · No cloud, no Spark.

> 📄 **See [WRITEUP.md](./WRITEUP.md) for the Business & Architecture Write-Up** — design decisions, trade-offs, and what this pipeline would look like at scale.

---

## Repository Structure

```
predixion-etl-pipeline/
├── generate.py           # Phase 1 — Generate 500 raw call records → raw_calls.json
├── pipeline.py           # Phase 2 — Ingest, validate, transform, load → predixion.db
├── queries.py            # Phase 3 — Analytics: 5 business questions → CSV outputs
├── raw_calls.json        # Generated raw data (created by generate.py)
├── predixion.db          # SQLite database (created by pipeline.py)
├── rejected_log.csv      # Rejected records with reasons (created by pipeline.py)
├── q1_connect_rate.csv
├── q2_callback_hours.csv
├── q3_long_duration.csv
├── q4_top_agents.csv
├── q5_volume_trend.csv
├── requirements.txt
├── README.md
└── WRITEUP.md            # Business & architecture write-up
```

---

## Setup Instructions

**1. Clone the repo and navigate to the project folder:**
```bash
git clone https://github.com/animesh-parab/predixion-etl-pipeline.git
cd predixion-etl-pipeline
```

**2. Create and activate a virtual environment:**
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

**3. Install dependencies:**
```bash
pip install -r requirements.txt
```

---

## Execution Steps

Run the three scripts in order:

### Step 1 — Generate raw data
```bash
python generate.py
```
Outputs `raw_calls.json` with exactly 500 records (injected with ~15% missing fields, ~5% duplicates, ~3% malformed timestamps).

### Step 2 — Run the ETL pipeline
```bash
python pipeline.py --input raw_calls.json --db-path predixion.db
```
- Validates and rejects bad records → `rejected_log.csv`
- Cleans, transforms, and loads 387 records → `predixion.db`
- Prints a terminal summary of accepted vs. rejected counts

The pipeline is **idempotent** — safe to re-run multiple times without duplicating data.

### Step 3 — Run analytics queries
```bash
python queries.py --db-path predixion.db
```
Prints answers to 5 business questions and saves one CSV per question.

---

## Query Outputs Summary

| File | Question |
|---|---|
| `q1_connect_rate.csv` | Connect rate by language |
| `q2_callback_hours.csv` | Hour with highest callback_requested rate |
| `q3_long_duration.csv` | % of long calls and avg amount_promised |
| `q4_top_agents.csv` | Top 3 agents by calls + outcome distribution |
| `q5_volume_trend.csv` | Call volume trend across dates |

---

## Key Findings

- **Hindi** has the highest connect rate (28.36%); **Marathi** the lowest (25%)
- **22:00** is the peak hour for callback requests (45.45% callback rate)
- **67%** of calls are 'long' (>300s), with avg amount promised ₹17,854
- **AGT016** leads with 27 calls and a 48.1% connect rate
- Data spans **Jan 1 → Mar 30, 2024** with consistent daily volume

---

## Database Schema

**`calls` table** (387 clean records):
| Column | Type | Notes |
|---|---|---|
| call_id | TEXT PK | Unique identifier |
| agent_id | TEXT | |
| customer_phone | TEXT | 10-digit string |
| start_time | TEXT | IST normalized |
| end_time | TEXT | IST normalized |
| call_outcome | TEXT | connected / no_answer / dropped / callback_requested |
| language | TEXT | Hindi / English / Marathi |
| disposition_code | TEXT | SALE / PROMISE_TO_PAY / NOT_INTERESTED / ESCALATED / HANGUP |
| amount_promised | REAL | 0 if imputed |
| retry_flag | INTEGER | 0 or 1 |
| call_duration_seconds | REAL | Computed |
| call_hour | INTEGER | 0–23 |
| call_date | TEXT | YYYY-MM-DD |
| is_weekend | INTEGER | 0 or 1 |
| duration_bucket | TEXT | short / medium / long |
| is_amount_imputed | INTEGER | 1 if null was imputed |

**`ingestion_log` table** (one row per pipeline run):
| Column | Notes |
|---|---|
| run_timestamp | IST datetime of run |
| records_processed | Total raw records read |
| records_rejected | Total rejected |
| records_loaded | Total loaded to calls table |

---

## Business & Architecture Write-Up

*[Placeholder — paste your write-up here]*

---

*Predixion AI — Data Engineering Internship Assignment*
