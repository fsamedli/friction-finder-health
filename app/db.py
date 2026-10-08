"""DuckDB layer. Loads the generated CSVs, builds suppressed views, and exposes a guarded
read-only query function. The suppression rule lives here, in SQL, not in prompts."""
from __future__ import annotations

import threading
from dataclasses import dataclass

import duckdb
import pandas as pd
import sqlglot
from sqlglot import exp

from app.config import DATA_DIR, MIN_N

TABLES = ["sites", "teams", "employees", "waves", "responses", "comments", "ops_daily",
          "staffing", "ownership_directory", "q12_items"]

# What the model (and the show-me panel) is allowed to query. Respondent rows are NOT here.
ALLOWED = {"sites", "teams", "waves", "q12_items", "ownership_directory", "staffing",
           "v_team_wave_item", "v_site_wave_item", "v_company_wave_item", "v_company_shift_wave_item", "v_tenure_wave_item", "v_team_wave_n",
           "v_team_tenure_mix", "v_ops_month", "v_ops_hour", "v_comments_reportable", "v_team_ops_month"}

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

-- Company-wide roll-ups (Tatenda Kagande, Sept 17, 2026): the same suppression rule, one row per item and wave.
CREATE OR REPLACE VIEW v_company_wave_item AS
WITH long AS (
  SELECT r.wave_id, i.item,
         CASE i.item
           WHEN 'q01' THEN q01 WHEN 'q02' THEN q02 WHEN 'q03' THEN q03 WHEN 'q04' THEN q04
           WHEN 'q05' THEN q05 WHEN 'q06' THEN q06 WHEN 'q07' THEN q07 WHEN 'q08' THEN q08
           WHEN 'q09' THEN q09 WHEN 'q10' THEN q10 WHEN 'q11' THEN q11 WHEN 'q12' THEN q12 END AS score
  FROM responses r CROSS JOIN q12_items i
)
SELECT l.wave_id, w.wave_name, l.item, q.label AS item_label,
       CASE WHEN COUNT(*) >= {MIN_N} THEN ROUND(AVG(score), 2) END AS mean_score,
       COUNT(*) AS n, COUNT(*) >= {MIN_N} AS reportable
FROM long l JOIN waves w ON w.wave_id = l.wave_id
JOIN q12_items q ON q.item = l.item
GROUP BY ALL;

CREATE OR REPLACE VIEW v_company_shift_wave_item AS
WITH long AS (
  SELECT r.wave_id, i.item, t.shift,
         CASE i.item
           WHEN 'q01' THEN q01 WHEN 'q02' THEN q02 WHEN 'q03' THEN q03 WHEN 'q04' THEN q04
           WHEN 'q05' THEN q05 WHEN 'q06' THEN q06 WHEN 'q07' THEN q07 WHEN 'q08' THEN q08
           WHEN 'q09' THEN q09 WHEN 'q10' THEN q10 WHEN 'q11' THEN q11 WHEN 'q12' THEN q12 END AS score
  FROM responses r JOIN teams t ON t.team_id = r.team_id CROSS JOIN q12_items i
)
SELECT l.wave_id, w.wave_name, l.item, q.label AS item_label, l.shift,
       CASE WHEN COUNT(*) >= {MIN_N} THEN ROUND(AVG(score), 2) END AS mean_score,
       COUNT(*) AS n, COUNT(*) >= {MIN_N} AS reportable
FROM long l JOIN waves w ON w.wave_id = l.wave_id
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


def _check_query(s: str) -> None:
    """Raise ValueError unless s is one read-only SELECT over allowlisted tables and views only."""
    try:
        statements = [x for x in sqlglot.parse(s, read="duckdb") if x is not None]
    except sqlglot.errors.ParseError as e:
        raise ValueError(f"Could not parse the query: {e}") from e
    if len(statements) != 1:
        raise ValueError("Only single SELECT statements are allowed.")
    tree = statements[0]
    if not isinstance(tree, exp.Query):
        raise ValueError("Query must be a SELECT (or WITH ... SELECT).")
    if any(isinstance(n, (exp.Insert, exp.Update, exp.Delete, exp.Create, exp.Drop, exp.Alter, exp.Command, exp.Copy)) for n in tree.walk()):
        raise ValueError("Only read-only SELECT statements are allowed.")
    ctes = {c.alias_or_name.lower() for c in tree.find_all(exp.CTE)}
    shadow = ctes & ({t.lower() for t in TABLES} | {"team_ops_monthly"})
    if shadow:  # WITH responses AS (SELECT * FROM responses) would read the real table under a CTE's name
        raise ValueError(f"CTE names may not reuse table names: {sorted(shadow)}")
    for t in tree.find_all(exp.Table):
        if not isinstance(t.this, exp.Identifier):  # read_csv(...), glob(...), any table function
            raise ValueError(f"Table functions are not allowed: {t.this.sql(dialect='duckdb')[:60]}")
        if t.args.get("db") or t.args.get("catalog"):
            raise ValueError(f"Schema-qualified names are not allowed: {t.sql(dialect='duckdb')}")
        name = t.name.lower()
        if name not in ALLOWED and name not in ctes:
            raise ValueError(f"Query touches non-allowed tables: ['{name}']. Respondent rows are never exposed.")
    for f in tree.find_all(exp.Func):
        fname = (f.sql_name() if not isinstance(f, exp.Anonymous) else str(f.this)).lower()
        if fname.startswith(("read_", "glob", "scan_", "sniff_")):
            raise ValueError(f"File-reading functions are not allowed: {fname}")


# Team-month operating records (the same rows the dashboards use, including an uploaded file) are loaded from
# app/impact.py's data, not from the CSV, so a question and a dashboard can never disagree. Teams with fewer than
# MIN_N people are left out of the view entirely: their counts identify people, and keeping them out of every
# site or shift total is what stops a suppressed team being recovered by subtracting visible teams from a total.
TEAM_OPS_VIEW = f"""
CREATE OR REPLACE VIEW v_team_ops_month AS
SELECT o.month, o.team_id, t.team_name, t.shift, t.site_id, s.site_name, o.headcount,
       o.late_departures, o.absence_days, o.quits, o.injuries, o.rework
FROM team_ops_monthly o
JOIN teams t ON t.team_id = o.team_id
JOIN sites s ON s.site_id = t.site_id
WHERE t.headcount >= {MIN_N}
"""


class DB:
    def __init__(self):
        # one connection shared by request threads and background investigations: every use goes through this lock
        self.lock = threading.RLock()
        self.con = duckdb.connect(database=":memory:")
        for t in TABLES:
            self.con.execute(f"CREATE TABLE {t} AS SELECT * FROM read_csv_auto('{DATA_DIR / (t + '.csv')}')")
        for stmt in VIEWS.split(";"):
            if stmt.strip():
                self.con.execute(stmt)
        self.uploaded_ops_rows = 0
        self._team_ops_src = None
        self.sync_team_ops()

    def sync_team_ops(self) -> str:
        """Make v_team_ops_month read exactly what app/impact.py reads (demo rows, or an uploaded file replacing
        them). Cheap when nothing changed. Returns the dataset version ('demo' or 'upload:<mtime>')."""
        from app import impact as I  # late import: impact does not import db
        df = I._data()[0]
        with self.lock:
            self._sync(df)
        up = I.upload_path()
        return f"upload:{int(up.stat().st_mtime)}" if up.exists() else "demo"

    def _sync(self, df) -> None:
        if self._team_ops_src is not df:
            cols = ["month", "team_id", "site_id", "shift", "headcount", "absence_days", "late_departures", "quits", "injuries", "rework"]
            self.con.register("team_ops_src", df[cols])
            self.con.execute("CREATE OR REPLACE TABLE team_ops_monthly AS SELECT * FROM team_ops_src")
            self.con.unregister("team_ops_src")
            self.con.execute(TEAM_OPS_VIEW)
            self._team_ops_src = df

    # ---- guarded query -------------------------------------------------
    # The query is parsed (sqlglot, DuckDB dialect), not pattern-matched: every table it references,
    # in any FROM, JOIN, comma join, subquery, CTE or UNION, must be an allowlisted view or table, and
    # table functions that read files (read_csv, read_parquet, glob, ...) are refused outright.
    # Replaces a regex that only checked the first name after FROM/JOIN (bypass found Sept 23, 2026).

    def run_sql(self, sql: str) -> QueryResult:
        s = sql.strip().rstrip(";").strip()
        _check_query(s)
        with self.lock:
            rows = self.con.execute(f"SELECT * FROM ({s}) LIMIT {ROW_CAP}").df()
        return QueryResult(sql=s, rows=rows)

    # ---- catalog helpers used by scope() ----------------------------------
    def sites(self) -> list[str]:
        with self.lock:
            return self.con.execute("SELECT site_name FROM sites ORDER BY 1").df().site_name.tolist()

    def teams(self) -> pd.DataFrame:
        with self.lock:
            return self.con.execute(
            "SELECT t.team_id, s.site_name, t.team_name, t.shift, t.manager_name FROM teams t JOIN sites s USING (site_id) ORDER BY 1").df()

    def items(self) -> pd.DataFrame:
        with self.lock:
            return self.con.execute("SELECT item, label FROM q12_items ORDER BY 1").df()

    def waves(self) -> pd.DataFrame:
        with self.lock:
            return self.con.execute("SELECT * FROM waves ORDER BY 1").df()

    # ---- upload path (Keegan's second question) -----------------------------
    def add_ops_upload(self, df: pd.DataFrame) -> int:
        required = {"date", "site_id", "shift", "hour_band", "departures", "late_departures", "rework_count"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"Upload is missing columns: {sorted(missing)}")
        df = df[sorted(required)].copy()
        df["date"] = df["date"].astype(str)
        with self.lock:
            self._insert_upload(df)
        self.uploaded_ops_rows += len(df)
        return len(df)

    def _insert_upload(self, df: pd.DataFrame) -> None:
        self.con.register("upload_df", df)
        self.con.execute("INSERT INTO ops_daily SELECT CAST(date AS DATE), CAST(site_id AS BIGINT), shift, hour_band, CAST(departures AS BIGINT), CAST(late_departures AS BIGINT), CAST(rework_count AS BIGINT) FROM upload_df")
        self.con.unregister("upload_df")

    def schema_for_prompt(self) -> str:
        """Compact description of the allowed views for the model."""
        return """Allowed views (SELECT only):
- v_team_wave_item(site_id, site_name, team_id, team_name, shift, wave_id, wave_name, item, item_label, mean_score, n, reportable): team x wave x item means; mean_score is NULL when n < 4.
- v_site_wave_item(site_id, site_name, wave_id, wave_name, item, item_label, mean_score, n, reportable): site roll-up.
- v_company_wave_item(wave_id, wave_name, item, item_label, mean_score, n, reportable): company roll-up.
- v_company_shift_wave_item(wave_id, wave_name, item, item_label, shift, mean_score, n, reportable): company roll-up by shift.
- v_tenure_wave_item(tenure_band, wave_id, item, mean_score, n, reportable): by tenure band (under_1, 1_to_3, 3_to_10, over_10).
- v_team_tenure_mix(team_id, wave_id, tenure_band, n, grand_mean): who responded, by tenure band.
- v_team_wave_n(team_id, wave_id, n): respondent counts.
- v_ops_month(site_id, site_name, shift, hour_band, month, departures, late_departures, late_rate, rework): operations by month.
- v_ops_hour(site_id, site_name, shift, hour_band, period, departures, late_departures, late_rate): operations by hour band, periods 'Jan-May 2026' and 'Jun-Sep 2026'.
- v_comments_reportable(comment_id, team_id, team_name, site_id, site_name, shift, wave_id, text): open-text comments from reportable team-waves only.
- v_team_ops_month(month, team_id, team_name, shift, site_id, site_name, headcount, late_departures, absence_days, quits, injuries, rework): team-month operating counts; teams under 4 people are not in this view.
- staffing(month, site_id, shift, scheduled_headcount, actual_headcount).
- ownership_directory(process_name, site_id, site_name, owner_role, owner_name).
- sites, teams, waves, q12_items."""
