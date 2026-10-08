"""run_sql guard: every table and table function the query touches must be allowlisted.

The two bypasses found Sept 23, 2026 (regex only checked the first table after FROM/JOIN) are here as
regression tests, with the other routes the same flaw opened."""
import pytest

from app.db import DB


@pytest.fixture(scope="module")
def db():
    return DB()


BLOCKED = [
    "SELECT r.* FROM sites, responses r",                                          # comma join (found Sept 23)
    "SELECT x.* FROM sites, read_csv('data/generated/responses.csv') x",          # table function (found Sept 23)
    "SELECT * FROM responses",
    "SELECT * FROM read_csv_auto('data/generated/employees.csv')",
    "SELECT * FROM read_parquet('x.parquet')",
    "WITH r AS (SELECT * FROM responses) SELECT * FROM r",                         # hidden in a CTE
    "SELECT * FROM sites WHERE site_id IN (SELECT team_id FROM responses)",        # hidden in a subquery
    "SELECT * FROM main.responses",                                                # schema-qualified
    "SELECT * FROM sites UNION ALL SELECT emp_id, NULL FROM responses",           # hidden in a UNION
    "SELECT * FROM sites; DROP TABLE sites",                                        # two statements
    "DELETE FROM sites",
    "SELECT * FROM glob('*')",
    "WITH responses AS (SELECT * FROM responses) SELECT * FROM responses",        # CTE shadowing a real table
    "SELECT * FROM sites WHERE EXISTS (SELECT 1 FROM read_csv_auto('x.csv'))",     # file read in a predicate
    "SELECT * FROM team_ops_monthly",                                               # raw team-months incl. teams under 4 (v0.8)
    "WITH team_ops_monthly AS (SELECT * FROM team_ops_monthly) SELECT * FROM team_ops_monthly",  # v0.8 table shadowed by a CTE
]


@pytest.mark.parametrize("sql", BLOCKED)
def test_blocked(db, sql):
    with pytest.raises(ValueError):
        db.run_sql(sql)


ALLOWED_QUERIES = [
    "SELECT COUNT(*) AS c FROM teams",
    "SELECT t.team_name, v.item FROM teams t JOIN v_team_wave_item v USING (team_id) LIMIT 5",
    "WITH x AS (SELECT * FROM v_site_wave_item WHERE reportable) SELECT site_name, COUNT(*) FROM x GROUP BY 1",
    "SELECT * FROM staffing WHERE site_id = (SELECT site_id FROM sites WHERE site_name = 'Lanford')",
]


@pytest.mark.parametrize("sql", ALLOWED_QUERIES)
def test_allowed(db, sql):
    assert len(db.run_sql(sql).rows) >= 1
