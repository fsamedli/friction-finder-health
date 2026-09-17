"""DuckDB layer. Loads the generated CSVs, builds suppressed views, and exposes a guarded
read-only query function. The suppression rule lives here, in SQL, not in prompts."""
from __future__ import annotations

import re
from dataclasses import dataclass

import duckdb
import pandas as pd

from app.config import DATA_DIR, MIN_N

TABLES = ["sites", "teams", "employees", "waves", "responses", "comments", "ops_daily",
          "staffing", "ownership_directory", "q12_items"]

# What the model (and the show-me panel) is allowed to query. Respondent rows are NOT here.
ALLOWED = {"sites", "teams", "waves", "q12_items", "ownership_directory", "staffing",
           "v_team_wave_item", "v_site_wave_item", "v_tenure_wave_item", "v_team_wave_n",
           "v_team_tenure_mix", "v_ops_month", "v_ops_hour", "v_comments_reportable"}

ROW_CAP = 5000   # protects the show-me panel and the model from huge outputs; every view here is far smaller (v_team_wave_item is 576 rows)

VIEWS = f"""
CREATE OR REPLACE VIEW v_team_wave_n AS
SELECT team_id, wave_id, COUNT(*) AS n FROM responses GROUP BY 1, 2;

CREATE OR REPLACE VIEW v_team_wave_item AS
WITH long AS (
  SELECT r.team_id, r.wave_id, i.item,
         CASE i.item
           WHEN 'q01' THEN q01 WHEN 'q02' THEN q02 WHEN 'q03' THEN q03 WHEN 'q04' THEN q04
           WHEN 'q05' THEN q05 WHEN 'q06' THEN q06 WHEN 'q07' THEN q07 WHEN 'q08' THEN q08
           WHEN 'q09' THEN q09 WHEN 'q10' THEN q10 WHEN 'q11' THEN q11 WHEN 'q12' THEN q12 END AS score
  FROM responses r CROSS JOIN q12_items i
)
SELECT t.site_id, s.site_name, l.team_id, t.team_name, t.shift, l.wave_id, w.wave_name,
       l.item, q.label AS item_label,
       CASE WHEN COUNT(*) >= {MIN_N} THEN ROUND(AVG(score), 2) END AS mean_score,
       COUNT(*) AS n,
       COUNT(*) >= {MIN_N} AS reportable
FROM long l
JOIN teams t ON t.team_id = l.team_id
JOIN sites s ON s.site_id = t.site_id
JOIN waves w ON w.wave_id = l.wave_id
JOIN q12_items q ON q.item = l.item
GROUP BY ALL;

CREATE OR REPLACE VIEW v_site_wave_item AS
WITH long AS (
  SELECT t.site_id, r.wave_id, i.item,
         CASE i.item
           WHEN 'q01' THEN q01 WHEN 'q02' THEN q02 WHEN 'q03' THEN q03 WHEN 'q04' THEN q04
           WHEN 'q05' THEN q05 WHEN 'q06' THEN q06 WHEN 'q07' THEN q07 WHEN 'q08' THEN q08
           WHEN 'q09' THEN q09 WHEN 'q10' THEN q10 WHEN 'q11' THEN q11 WHEN 'q12' THEN q12 END AS score
  FROM responses r JOIN teams t ON t.team_id = r.team_id CROSS JOIN q12_items i
)
SELECT l.site_id, s.site_name, l.wave_id, w.wave_name, l.item, q.label AS item_label,
       CASE WHEN COUNT(*) >= {MIN_N} THEN ROUND(AVG(score), 2) END AS mean_score,
       COUNT(*) AS n, COUNT(*) >= {MIN_N} AS reportable
FROM long l JOIN sites s ON s.site_id = l.site_id JOIN waves w ON w.wave_id = l.wave_id
JOIN q12_items q ON q.item = l.item
GROUP BY ALL;

CREATE OR REPLACE VIEW v_tenure_wave_item AS
WITH long AS (
  SELECT e.tenure_band, r.wave_id, i.item,
         CASE i.item
           WHEN 'q01' THEN q01 WHEN 'q02' THEN q02 WHEN 'q03' THEN q03 WHEN 'q04' THEN q04
           WHEN 'q05' THEN q05 WHEN 'q06' THEN q06 WHEN 'q07' THEN q07 WHEN 'q08' THEN q08
           WHEN 'q09' THEN q09 WHEN 'q10' THEN q10 WHEN 'q11' THEN q11 WHEN 'q12' THEN q12 END AS score
  FROM responses r JOIN employees e ON e.emp_id = r.emp_id CROSS JOIN q12_items i
)
SELECT tenure_band, wave_id, item,
       CASE WHEN COUNT(*) >= {MIN_N} THEN ROUND(AVG(score), 2) END AS mean_score,
       COUNT(*) AS n, COUNT(*) >= {MIN_N} AS reportable
FROM long GROUP BY ALL;

CREATE OR REPLACE VIEW v_team_tenure_mix AS
SELECT r.team_id, r.wave_id, e.tenure_band, COUNT(*) AS n,
       CASE WHEN COUNT(*) >= {MIN_N}
            THEN ROUND(AVG((q01+q02+q03+q04+q05+q06+q07+q08+q09+q10+q11+q12)/12.0), 2) END AS grand_mean
FROM responses r JOIN employees e ON e.emp_id = r.emp_id
GROUP BY ALL;

CREATE OR REPLACE VIEW v_ops_month AS
SELECT o.site_id, s.site_name, o.shift, o.hour_band, strftime(o.date, '%Y-%m') AS month,
       SUM(departures) AS departures, SUM(late_departures) AS late_departures,
       ROUND(SUM(late_departures) * 1.0 / NULLIF(SUM(departures), 0), 3) AS late_rate,
       SUM(rework_count) AS rework
FROM ops_daily o JOIN sites s ON s.site_id = o.site_id
GROUP BY ALL;

CREATE OR REPLACE VIEW v_ops_hour AS
SELECT o.site_id, s.site_name, o.shift, o.hour_band,
       CASE WHEN o.date >= '2026-06-01' THEN 'Jun-Sep 2026' ELSE 'Jan-May 2026' END AS period,
       SUM(departures) AS departures, SUM(late_departures) AS late_departures,
       ROUND(SUM(late_departures) * 1.0 / NULLIF(SUM(departures), 0), 3) AS late_rate
FROM ops_daily o JOIN sites s ON s.site_id = o.site_id
GROUP BY ALL;

CREATE OR REPLACE VIEW v_comments_reportable AS
SELECT c.comment_id, c.team_id, t.team_name, t.site_id, s.site_name, t.shift, c.wave_id, c.text
FROM comments c
JOIN teams t ON t.team_id = c.team_id
JOIN sites s ON s.site_id = t.site_id
JOIN v_team_wave_n n ON n.team_id = c.team_id AND n.wave_id = c.wave_id
WHERE n.n >= {MIN_N};
"""


@dataclass
class QueryResult:
    sql: str
    rows: pd.DataFrame

    def to_records(self):
        return self.rows.to_dict(orient="records")


class DB:
    def __init__(self):
        self.con = duckdb.connect(database=":memory:")
        for t in TABLES:
            self.con.execute(f"CREATE TABLE {t} AS SELECT * FROM read_csv_auto('{DATA_DIR / (t + '.csv')}')")
        for stmt in VIEWS.split(";"):
            if stmt.strip():
                self.con.execute(stmt)
        self.uploaded_ops_rows = 0

    # ---- guarded query -------------------------------------------------
    _forbidden = re.compile(r"\b(insert|update|delete|drop|alter|create|copy|attach|pragma|export|import)\b", re.I)
    _from_pat = re.compile(r"\b(?:from|join)\s+([a-zA-Z_][a-zA-Z0-9_]*)", re.I)

    def run_sql(self, sql: str) -> QueryResult:
        s = sql.strip().rstrip(";")
        if self._forbidden.search(s) or ";" in s:
            raise ValueError("Only single SELECT statements are allowed.")
        refs = {m.lower() for m in self._from_pat.findall(s)}
        bad = refs - ALLOWED
        if bad:
            raise ValueError(f"Query touches non-allowed tables: {sorted(bad)}. Respondent rows are never exposed.")
        if not re.match(r"^\s*(select|with)\b", s, re.I):
            raise ValueError("Query must start with SELECT or WITH.")
        rows = self.con.execute(f"SELECT * FROM ({s}) LIMIT {ROW_CAP}").df()
        return QueryResult(sql=s, rows=rows)

    # ---- catalog helpers used by scope() ----------------------------------
    def sites(self) -> list[str]:
        return self.con.execute("SELECT site_name FROM sites ORDER BY 1").df().site_name.tolist()

    def teams(self) -> pd.DataFrame:
        return self.con.execute(
            "SELECT t.team_id, s.site_name, t.team_name, t.shift, t.manager_name FROM teams t JOIN sites s USING (site_id) ORDER BY 1").df()

    def items(self) -> pd.DataFrame:
        return self.con.execute("SELECT item, label FROM q12_items ORDER BY 1").df()

    def waves(self) -> pd.DataFrame:
        return self.con.execute("SELECT * FROM waves ORDER BY 1").df()

    # ---- upload path (Keegan's second question) -----------------------------
    def add_ops_upload(self, df: pd.DataFrame) -> int:
        required = {"date", "site_id", "shift", "hour_band", "departures", "late_departures", "rework_count"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"Upload is missing columns: {sorted(missing)}")
        df = df[sorted(required)].copy()
        df["date"] = df["date"].astype(str)
        self.con.register("upload_df", df)
        self.con.execute("INSERT INTO ops_daily SELECT CAST(date AS DATE), CAST(site_id AS BIGINT), shift, hour_band, CAST(departures AS BIGINT), CAST(late_departures AS BIGINT), CAST(rework_count AS BIGINT) FROM upload_df")
        self.con.unregister("upload_df")
        self.uploaded_ops_rows += len(df)
        return len(df)

    def schema_for_prompt(self) -> str:
        """Compact description of the allowed views for the model."""
        return """Allowed views (SELECT only):
- v_team_wave_item(site_id, site_name, team_id, team_name, shift, wave_id, wave_name, item, item_label, mean_score, n, reportable): team x wave x item means; mean_score is NULL when n < 4.
- v_site_wave_item(site_id, site_name, wave_id, wave_name, item, item_label, mean_score, n, reportable): site roll-up.
- v_tenure_wave_item(tenure_band, wave_id, item, mean_score, n, reportable): by tenure band (under_1, 1_to_3, 3_to_10, over_10).
- v_team_tenure_mix(team_id, wave_id, tenure_band, n, grand_mean): who responded, by tenure band.
- v_team_wave_n(team_id, wave_id, n): respondent counts.
- v_ops_month(site_id, site_name, shift, hour_band, month, departures, late_departures, late_rate, rework): operations by month.
- v_ops_hour(site_id, site_name, shift, hour_band, period, departures, late_departures, late_rate): operations by hour band, periods 'Jan-May 2026' and 'Jun-Sep 2026'.
- v_comments_reportable(comment_id, team_id, team_name, site_id, site_name, shift, wave_id, text): open-text comments from reportable team-waves only.
- staffing(month, site_id, shift, scheduled_headcount, actual_headcount).
- ownership_directory(process_name, site_id, site_name, owner_role, owner_name).
- sites, teams, waves, q12_items."""
