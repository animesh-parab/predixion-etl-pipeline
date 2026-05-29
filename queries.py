"""
queries.py — Phase 3: Analytics Layer
Answers 5 business questions using pure SQL via pd.read_sql()
Output: printed summaries + CSV per question
"""

import sqlite3
import pandas as pd
import argparse

def run_queries(db_path: str = "predixion.db"):
    conn = sqlite3.connect(db_path)

    print("=" * 60)
    print("  queries.py — Predixion AI Analytics")
    print("=" * 60)

    # ─────────────────────────────────────────────────────────
    # Q1: Connect rate by language
    # ─────────────────────────────────────────────────────────
    q1 = """
        SELECT
            language,
            COUNT(*)                                              AS total_calls,
            SUM(CASE WHEN call_outcome = 'connected' THEN 1 ELSE 0 END) AS connected_calls,
            ROUND(
                100.0 * SUM(CASE WHEN call_outcome = 'connected' THEN 1 ELSE 0 END)
                / COUNT(*), 2
            )                                                     AS connect_rate_pct
        FROM calls
        GROUP BY language
        ORDER BY connect_rate_pct DESC
    """
    df_q1 = pd.read_sql(q1, conn)
    df_q1.to_csv("q1_connect_rate.csv", index=False)

    print("\n--- Q1: Connect Rate by Language ---")
    print(df_q1.to_string(index=False))

    # ─────────────────────────────────────────────────────────
    # Q2: Hour with highest callback_requested rate
    # ─────────────────────────────────────────────────────────
    q2 = """
        SELECT
            call_hour,
            COUNT(*)                                                        AS total_calls,
            SUM(CASE WHEN call_outcome = 'callback_requested' THEN 1 ELSE 0 END) AS callback_calls,
            ROUND(
                100.0 * SUM(CASE WHEN call_outcome = 'callback_requested' THEN 1 ELSE 0 END)
                / COUNT(*), 2
            )                                                               AS callback_rate_pct
        FROM calls
        GROUP BY call_hour
        ORDER BY callback_rate_pct DESC
        LIMIT 5
    """
    df_q2 = pd.read_sql(q2, conn)
    df_q2.to_csv("q2_callback_hours.csv", index=False)

    print("\n--- Q2: Top 5 Hours by Callback Requested Rate ---")
    print(df_q2.to_string(index=False))
    top_hour = df_q2.iloc[0]
    print(f"\n  ➤ Peak callback hour: {int(top_hour['call_hour']):02d}:00  "
          f"({top_hour['callback_rate_pct']}% callback rate)")

    # ─────────────────────────────────────────────────────────
    # Q3: % of 'long' calls and their average amount_promised
    # ─────────────────────────────────────────────────────────
    q3 = """
        SELECT
            duration_bucket,
            COUNT(*)                                AS total_calls,
            ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct_of_total,
            ROUND(AVG(amount_promised), 2)          AS avg_amount_promised
        FROM calls
        GROUP BY duration_bucket
        ORDER BY
            CASE duration_bucket
                WHEN 'short'  THEN 1
                WHEN 'medium' THEN 2
                WHEN 'long'   THEN 3
            END
    """
    df_q3 = pd.read_sql(q3, conn)
    df_q3.to_csv("q3_long_duration.csv", index=False)

    print("\n--- Q3: Call Duration Buckets & Avg Amount Promised ---")
    print(df_q3.to_string(index=False))
    long_row = df_q3[df_q3["duration_bucket"] == "long"]
    if not long_row.empty:
        print(f"\n  ➤ Long calls: {long_row.iloc[0]['pct_of_total']}% of total  |  "
              f"Avg amount promised: ₹{long_row.iloc[0]['avg_amount_promised']}")

    # ─────────────────────────────────────────────────────────
    # Q4: Top 3 agents by total calls + outcome distribution
    # ─────────────────────────────────────────────────────────
    q4 = """
        SELECT
            agent_id,
            COUNT(*)                                                              AS total_calls,
            SUM(CASE WHEN call_outcome = 'connected'           THEN 1 ELSE 0 END) AS connected,
            SUM(CASE WHEN call_outcome = 'no_answer'           THEN 1 ELSE 0 END) AS no_answer,
            SUM(CASE WHEN call_outcome = 'dropped'             THEN 1 ELSE 0 END) AS dropped,
            SUM(CASE WHEN call_outcome = 'callback_requested'  THEN 1 ELSE 0 END) AS callback_requested,
            ROUND(100.0 * SUM(CASE WHEN call_outcome = 'connected' THEN 1 ELSE 0 END) / COUNT(*), 1)
                                                                                  AS connect_rate_pct
        FROM calls
        GROUP BY agent_id
        ORDER BY total_calls DESC
        LIMIT 3
    """
    df_q4 = pd.read_sql(q4, conn)
    df_q4.to_csv("q4_top_agents.csv", index=False)

    print("\n--- Q4: Top 3 Agents by Total Calls Handled ---")
    print(df_q4.to_string(index=False))

    # ─────────────────────────────────────────────────────────
    # Q5: Call volume trend across dates
    # ─────────────────────────────────────────────────────────
    q5 = """
        SELECT
            call_date,
            COUNT(*)                                                              AS total_calls,
            SUM(CASE WHEN call_outcome = 'connected'          THEN 1 ELSE 0 END) AS connected,
            SUM(CASE WHEN call_outcome = 'callback_requested' THEN 1 ELSE 0 END) AS callbacks,
            ROUND(100.0 * SUM(CASE WHEN call_outcome = 'connected' THEN 1 ELSE 0 END) / COUNT(*), 1)
                                                                                  AS daily_connect_rate_pct,
            CAST(is_weekend AS TEXT)                                              AS is_weekend
        FROM calls
        GROUP BY call_date
        ORDER BY call_date ASC
    """
    df_q5 = pd.read_sql(q5, conn)
    df_q5.to_csv("q5_volume_trend.csv", index=False)

    print("\n--- Q5: Call Volume Trend by Date ---")
    print(df_q5.to_string(index=False))
    print(f"\n  ➤ Date range: {df_q5['call_date'].min()} → {df_q5['call_date'].max()}")
    print(f"  ➤ Peak day  : {df_q5.loc[df_q5['total_calls'].idxmax(), 'call_date']} "
          f"({df_q5['total_calls'].max()} calls)")

    conn.close()

    print("\n" + "=" * 60)
    print("  CSVs saved: q1_connect_rate.csv, q2_callback_hours.csv,")
    print("              q3_long_duration.csv, q4_top_agents.csv,")
    print("              q5_volume_trend.csv")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Predixion AI Analytics Queries")
    parser.add_argument("--db-path", default="predixion.db", help="Path to SQLite database")
    args = parser.parse_args()
    run_queries(db_path=args.db_path)
