"""Synthetic data generator for the Friction Finder prototype.

Everything here is fictional. Northline Logistics does not exist. The survey is shaped like a
12-item, 1-to-5 engagement survey with two waves; the operational and staffing records are
invented; the documents are written by the team. Planted patterns are recorded in truth.json
so the assistant can be scored against known answers.

Run:  python data/generate.py   (writes to data/generated/ and data/docs/)
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
HERE = Path(__file__).resolve().parent
OUT = HERE / "generated"
DOCS = HERE / "docs"
MIN_N = 4  # Gallup's stated minimum reporting n (Keegan, Sept 14, 2026)

ITEMS = [
    ("q01", "Know what is expected of me"),
    ("q02", "Materials and equipment to do my work right"),
    ("q03", "Opportunity to do what I do best"),
    ("q04", "Recognition or praise in the last seven days"),
    ("q05", "Someone at work cares about me"),
    ("q06", "Someone encourages my development"),
    ("q07", "My opinions seem to count"),
    ("q08", "Mission makes my job feel important"),
    ("q09", "Coworkers committed to quality"),
    ("q10", "A best friend at work"),
    ("q11", "Progress conversation in the last six months"),
    ("q12", "Opportunities to learn and grow"),
]
ITEM_CODES = [c for c, _ in ITEMS]

SITES = [(1, "Richmond"), (2, "Norfolk"), (3, "Roanoke")]
# (team_name, shift, headcount). Small teams are deliberate: they fall under MIN_N.
TEAM_TEMPLATE = [
    ("Day A", "Day", 12),
    ("Day B", "Day", 12),
    ("Day C", "Day", 8),
    ("Night A", "Night", 14),
    ("Night B", "Night", 7),
    ("Yard Day", "Day", 5),
    ("Dispatch Day", "Day", 3),
    ("Maintenance Night", "Night", 2),
]
TENURE_BANDS = ["under_1", "1_to_3", "3_to_10", "over_10"]
TENURE_P = [0.22, 0.30, 0.33, 0.15]
HONEYMOON = 0.35  # under_1 scores this much higher on every item (P5)
COHORT_EXTRA = 0.25  # Norfolk Day B's new-hire cohort is unusually upbeat (makes P6 visible)
NOISE_SD = 0.5
EMP_SD = 0.2
PLANTED_DROPS = {"q02": -0.9, "q07": -0.7}  # Richmond Night A, wave 2 (P1, P2)
BLIP_DROP = {"q04": -0.6}  # P9: Roanoke Day C, wave 2. A survey-only blip: no operational signal, no comments.
                           # Red-team case from judge Lederman (MITRE, Sept 15, 2026): the brief must say
                           # "insufficient evidence", not propose an action.

WAVES = [(1, "Wave 1", date(2026, 3, 15)), (2, "Wave 2", date(2026, 9, 10))]

FIRST = ["Dana", "Marcus", "Priya", "Luis", "Aisha", "Tom", "Elena", "Kwame", "Sofia", "Jordan",
         "Nadia", "Omar", "Grace", "Victor", "Hana", "Sam", "Leila", "Ravi", "Maya", "Ben",
         "Chloe", "Diego", "Ines", "Noah"]
LAST = ["Alvarez", "Brooks", "Chen", "Diallo", "Evans", "Farah", "Garcia", "Hughes", "Ibrahim",
        "Jensen", "Kim", "Lopez", "Mensah", "Novak", "Okafor", "Patel", "Quinn", "Reyes",
        "Singh", "Turner", "Usman", "Vega", "Walsh", "Young"]

GENERIC_COMMENTS = {
    "workload": [
        "The workload has been heavy this quarter but the team pulls together.",
        "Too many priorities at once; it is hard to know what matters most this week.",
        "Overtime has been manageable but I would like more notice.",
    ],
    "recognition": [
        "My supervisor notices good work and says so. That helps.",
        "Recognition is rare here. A thank you now and then would go a long way.",
    ],
    "tools": [
        "The new scanners work well most days.",
        "Forklift maintenance requests take too long to close.",
    ],
    "communication": [
        "Weekly huddles are useful. Keep them short.",
        "Changes to routes get announced late and we scramble.",
    ],
    "schedule": [
        "Schedules come out on time. No complaints.",
        "Shift swaps are hard to arrange when someone is out.",
    ],
    "development": [
        "I would like a clearer path to a lead role.",
        "Cross-training on dispatch has been great for me.",
    ],
}

# P10: one long comment (red-team case from judge Chang, FI Consulting, Sept 15, 2026). One
# employee writes a page about equipment; the brief must weight breadth, not length, and label
# it single-source.
LOUD_COMMENT = (
    "I want to put on record how bad the forklift situation has become on nights. Three of the five "
    "forklifts on our side have had intermittent hydraulic faults since spring, and every time we raise a "
    "maintenance ticket it sits for a week or more before anyone looks at it. When a lift goes down "
    "mid-shift we have to borrow from the day side, which they resent, and the loaders end up walking "
    "pallets across the dock by hand. It is slow, it is unsafe, and nobody upstairs seems to notice. I have "
    "raised it in three huddles. The maintenance lead says parts are on order but that has been the answer "
    "since April. If leadership wants to know why people are frustrated on this shift, start with the "
    "forklifts. Fix the ticket queue, buy the parts, and stop treating night shift as an afterthought."
)

HANDOFF_COMMENTS = [
    "We never know what has been loaded when we come in. The handoff log is empty most nights.",
    "Day shift leaves before the load checklist is done, so we start blind and the 6 AM trucks go out late.",
    "Handoff at six is chaos. Dispatch does not know which trailers we finished, so departures slip.",
    "We spend the first hour of every shift figuring out what the last shift actually did. The handoff log tells us nothing.",
]


def rng():
    return np.random.default_rng(SEED)


def build_teams():
    rows = []
    tid = 0
    for site_id, _ in SITES:
        for name, shift, headcount in TEAM_TEMPLATE:
            tid += 1
            rows.append({
                "team_id": tid, "site_id": site_id, "team_name": name, "shift": shift,
                "headcount": headcount,
            })
    teams = pd.DataFrame(rows)
    r = rng()
    teams["manager_name"] = [f"{r.choice(FIRST)} {r.choice(LAST)}" for _ in range(len(teams))]
    return teams


def build_employees(teams: pd.DataFrame):
    r = rng()
    norfolk_day_b = team_key(teams, "Norfolk", "Day B")
    rows = []
    eid = 0
    for _, t in teams.iterrows():
        for i in range(int(t.headcount)):
            eid += 1
            band = r.choice(TENURE_BANDS, p=TENURE_P)
            if int(t.team_id) == norfolk_day_b:
                # P6: half of this team is a new-hire cohort
                band = "under_1" if i < int(t.headcount) // 2 else r.choice(TENURE_BANDS[1:], p=[0.4, 0.4, 0.2])
            years = {"under_1": r.uniform(0.1, 0.95), "1_to_3": r.uniform(1, 3),
                     "3_to_10": r.uniform(3, 10), "over_10": r.uniform(10, 22)}[band]
            hire = date(2026, 9, 10) - timedelta(days=int(years * 365))
            rows.append({"emp_id": eid, "team_id": int(t.team_id), "tenure_band": band,
                         "hire_date": hire.isoformat()})
    return pd.DataFrame(rows)


def team_key(teams, site_name, team_name):
    site_id = {n: i for i, n in SITES}[site_name]
    row = teams[(teams.site_id == site_id) & (teams.team_name == team_name)].iloc[0]
    return int(row.team_id)


def build_responses(teams: pd.DataFrame, employees: pd.DataFrame):
    """Respondent-level answers. Planted: P1, P2 (Richmond Night A drop), P5 honeymoon,
    P6 mix-shift on Norfolk Day B. Response rate about 85% otherwise."""
    r = rng()
    rich_night_a = team_key(teams, "Richmond", "Night A")
    norfolk_day_b = team_key(teams, "Norfolk", "Day B")
    roanoke_day_c = team_key(teams, "Roanoke", "Day C")

    # team x item baseline around 3.8, stable across waves except planted shifts
    base = {}
    for tid in teams.team_id:
        base[tid] = {c: float(np.clip(r.normal(3.85, 0.15), 3.4, 4.3)) for c in ITEM_CODES}
    # planted drops (wave 2 only)
    drop = {rich_night_a: PLANTED_DROPS, roanoke_day_c: BLIP_DROP}  # P1/P2 and P9

    emp_effect = {int(e.emp_id): float(r.normal(0, EMP_SD)) for e in employees.itertuples()}

    rows = []
    for wave_id, _, _ in WAVES:
        for e in employees.itertuples():
            tid = int(e.team_id)
            # response decision
            p_respond = 0.85
            if tid == rich_night_a:
                p_respond = 0.95  # keep n high on the planted team so the drop is not noise
            if tid == norfolk_day_b and wave_id == 1:
                p_respond = 0.95
            if tid == norfolk_day_b and wave_id == 2:
                p_respond = 0.10 if e.tenure_band == "under_1" else 0.95  # P6 mix shift
            if r.uniform() > p_respond:
                continue
            rec = {"emp_id": int(e.emp_id), "team_id": tid, "wave_id": wave_id}
            for c in ITEM_CODES:
                mu = base[tid][c] + emp_effect[int(e.emp_id)]
                if e.tenure_band == "under_1":
                    mu += HONEYMOON
                    if tid == norfolk_day_b:
                        mu += COHORT_EXTRA
                if wave_id == 2 and tid in drop and c in drop[tid]:
                    mu += drop[tid][c]
                val = int(np.clip(np.rint(r.normal(mu, NOISE_SD)), 1, 5))
                rec[c] = val
            rows.append(rec)
    return pd.DataFrame(rows)


def build_comments(teams: pd.DataFrame, responses: pd.DataFrame):
    r = rng()
    rich_night_a = team_key(teams, "Richmond", "Night A")
    norfolk_night_a = team_key(teams, "Norfolk", "Night A")
    rows = []
    cid = 0
    # generic comments: about 2 per team per wave for larger teams
    for wave_id, _, _ in WAVES:
        for tid in teams.team_id:
            n_resp = int(((responses["team_id"] == tid) & (responses["wave_id"] == wave_id)).sum())
            k = 0 if n_resp < MIN_N else int(r.integers(1, 3))
            for _ in range(k):
                theme = r.choice(list(GENERIC_COMMENTS))
                cid += 1
                rows.append({"comment_id": cid, "team_id": int(tid), "wave_id": wave_id,
                             "text": str(r.choice(GENERIC_COMMENTS[theme])), "theme": theme})
    # P8: handoff comments, Richmond Night A, wave 2
    for text in HANDOFF_COMMENTS:
        cid += 1
        rows.append({"comment_id": cid, "team_id": rich_night_a, "wave_id": 2, "text": text,
                     "theme": "handoff"})
    # P10: one loud comment, Norfolk Night A, wave 2
    cid += 1
    rows.append({"comment_id": cid, "team_id": norfolk_night_a, "wave_id": 2, "text": LOUD_COMMENT,
                 "theme": "tools_loud"})
    return pd.DataFrame(rows)


HOUR_BANDS = [("02-06", "Night"), ("06-07", "Night"), ("07-10", "Day"), ("10-14", "Day"),
              ("14-18", "Day"), ("18-22", "Night"), ("22-02", "Night")]


def build_ops(teams: pd.DataFrame):
    """Daily departures per site, shift, hour band. P3: Richmond Night 06-07 late rate rises
    from ~8% to ~18% from 2026-06-01. Everything else flat at ~8%."""
    r = rng()
    rows = []
    d = date(2026, 1, 1)
    end = date(2026, 9, 10)
    while d <= end:
        for site_id, site_name in SITES:
            for band, shift in HOUR_BANDS:
                departures = int(r.poisson(18 if band != "06-07" else 24))
                late_rate = 0.08
                if site_name == "Richmond" and shift == "Night" and band == "06-07" and d >= date(2026, 6, 1):
                    late_rate = 0.18
                late = int(r.binomial(departures, late_rate))
                rework = int(r.poisson(1.5))
                rows.append({"date": d.isoformat(), "site_id": site_id, "shift": shift,
                             "hour_band": band, "departures": departures,
                             "late_departures": late, "rework_count": rework})
        d += timedelta(days=1)
    return pd.DataFrame(rows)


def build_staffing(teams: pd.DataFrame):
    """Monthly scheduled vs actual headcount per site and shift. P4: Richmond Night March
    2026 at ~80% of scheduled, April ~90%, normal (~97%) otherwise."""
    r = rng()
    rows = []
    sched = teams.groupby(["site_id", "shift"]).headcount.sum().to_dict()
    for m in range(1, 10):
        month = f"2026-{m:02d}"
        for (site_id, shift), s in sched.items():
            ratio = float(np.clip(r.normal(0.97, 0.015), 0.92, 1.0))
            if site_id == 1 and shift == "Night":
                ratio = {3: 0.80, 4: 0.90}.get(m, ratio)
            rows.append({"month": month, "site_id": site_id, "shift": shift,
                         "scheduled_headcount": int(s), "actual_headcount": int(round(s * ratio))})
    return pd.DataFrame(rows)


def build_ownership(teams: pd.DataFrame):
    r = rng()
    rows = []
    for site_id, site_name in SITES:
        ops_mgr = f"{r.choice(FIRST)} {r.choice(LAST)}"
        disp = f"{r.choice(FIRST)} {r.choice(LAST)}"
        rows += [
            {"process_name": "Shift handoff procedure", "site_id": site_id, "site_name": site_name,
             "owner_role": "Site Operations Manager", "owner_name": ops_mgr},
            {"process_name": "Dispatch scheduling", "site_id": site_id, "site_name": site_name,
             "owner_role": "Dispatch Supervisor", "owner_name": disp},
            {"process_name": "Forklift and equipment maintenance", "site_id": site_id,
             "site_name": site_name, "owner_role": "Maintenance Lead",
             "owner_name": f"{r.choice(FIRST)} {r.choice(LAST)}"},
        ]
    rows += [
        {"process_name": "Engagement survey and action planning", "site_id": 0, "site_name": "ALL",
         "owner_role": "HR Business Partner", "owner_name": "Dana Whitfield"},
        {"process_name": "Shift scheduling policy", "site_id": 0, "site_name": "ALL",
         "owner_role": "Director of Operations", "owner_name": "Marcus Okafor"},
    ]
    return pd.DataFrame(rows)


def write_docs(ownership: pd.DataFrame):
    DOCS.mkdir(parents=True, exist_ok=True)
    (DOCS / "shift_handoff_procedure.md").write_text("""# Shift Handoff Procedure (SOP-OPS-014)

Illustrative document written for a fictional company. Not a real Northline document.

## Purpose
Ensure the incoming shift has complete information about loads in progress, trailers ready
for departure, and open issues, so that scheduled departures leave on time.

## Steps
1. Thirty minutes before shift end, the outgoing shift lead completes the **load checklist**
   for every trailer worked during the shift: trailer number, load status (empty, partial,
   complete), seal status, and scheduled departure time.
2. The outgoing lead records open issues in the **handoff log**: equipment faults, missing
   paperwork, staffing gaps for the next shift.
3. The incoming shift lead reviews the checklist and the log with the outgoing lead in a
   ten-minute handoff meeting at the dispatch desk.
4. Both leads sign the handoff log. Dispatch does not release a 06:00 or 18:00 departure
   until the signed log for that trailer is on file.

## Ownership
The Site Operations Manager at each site owns this procedure and its compliance. The
Dispatch Supervisor owns the departure release step (step 4).

## Review
Reviewed annually. Last review: January 2026.
""")
    (DOCS / "shift_scheduling_policy.md").write_text("""# Shift Scheduling Policy (POL-HR-006)

Illustrative document written for a fictional company.

- Schedules are published at least 14 days in advance.
- Minimum staffing per shift is set by the Site Operations Manager and reviewed monthly
  against the staffing report (scheduled versus actual headcount).
- When actual headcount falls below 85% of scheduled for a shift in a given month, the
  Director of Operations is notified and a recovery plan is required within two weeks.
- Shift swaps require approval by the shift lead and must not reduce a shift below minimum.
- The Director of Operations owns this policy.
""")
    (DOCS / "engagement_action_planning_guide.md").write_text("""# Engagement Action Planning Guide (internal)

Illustrative document written for a fictional company. Generic guidance, not vendor material.

After survey results are released, each manager with reportable results (four or more
respondents) reviews them with the team, selects one or two focus areas, and records an action
with an owner, a success measure, and a review date. Results for teams with fewer than four
respondents are not shown; those managers review the site-level results with their
Site Operations Manager instead.

Actions are reviewed at the mid-point between surveys. The HR Business Partner owns the
process and tracks completion.
""")
    lines = ["# Process Ownership Directory\n", "Illustrative directory for a fictional company.\n",
             "| Process | Site | Owner role | Owner name |", "|---|---|---|---|"]
    for o in ownership.itertuples():
        lines.append(f"| {o.process_name} | {o.site_name} | {o.owner_role} | {o.owner_name} |")
    (DOCS / "ownership_directory.md").write_text("\n".join(lines) + "\n")


def write_data_spec(frames: dict, truth: dict):
    """One-page data specification (judge Lederman, MITRE, Sept 15, 2026: 'what's the data feeding
    this tool? How many records? What fields?'). Regenerated on every run."""
    lines = ["# Data specification (synthetic)", "",
             f"Generated by `data/generate.py`, seed {SEED}, on every run. Fictional company: Northline Logistics "
             "(three sites, Day and Night shifts). Nothing here is real. The shape follows a survey-vendor team export "
             "(team x wave x item aggregates) so that a real export could replace the survey tables without code changes.",
             "", "## Tables", "", "| Table | Grain | Rows | Fields |", "|---|---|---|---|"]
    grain = {"sites": "site", "teams": "team", "employees": "employee (no PII; unique emp_id)", "waves": "survey wave",
             "responses": "respondent x wave (never shown to the model)", "comments": "open-text comment (reportable team-waves only are indexed)",
             "ops_daily": "site x shift x hour band x day", "staffing": "site x shift x month",
             "ownership_directory": "process x site", "q12_items": "survey item"}
    for name, df in frames.items():
        lines.append(f"| {name} | {grain.get(name, '')} | {len(df):,} | {', '.join(df.columns)} |")
    lines += ["", "## How the numbers are made", "",
              f"- Survey: 12 items, 1 to 5. Each team has a baseline near 3.85 per item; each employee has a fixed offset (SD {EMP_SD}); "
              f"each answer adds noise (SD {NOISE_SD}) and is rounded to 1 to 5. Response rate about 85% per wave.",
              f"- Tenure: bands under_1, 1_to_3, 3_to_10, over_10 with shares {TENURE_P}. Under-one-year employees score {HONEYMOON} higher "
              "on every item (the year-one honeymoon effect Gallup described on Sept 14, 2026).",
              "- Operations: daily departures per site, shift, and hour band (Poisson), with a flat 8% late rate except where planted.",
              "- Staffing: monthly scheduled versus actual headcount, about 97% except where planted.",
              "- Comments: one to two generic comments per reportable team-wave, drawn from a small bank, plus the planted ones.",
              "", "## Planted patterns (the answer key the assistant is scored against)", "",
              "| Id | What | Planted how | Expected behaviour |", "|---|---|---|---|",
              "| P1, P2 | Richmond Night A: Q02 (materials and equipment) and Q07 (opinions count) fall in Wave 2 | item means shifted by -0.9 and -0.7 | found, material, corroborated |",
              "| P3 | Richmond Night 06-07 late departures rise from June 2026 | late rate 8% to 18% in that band only | operational signal found |",
              "| P4 | Richmond Night staffing shortage, March 2026 | actual 80% of scheduled | listed as a competing explanation |",
              "| P5 | Honeymoon effect | under_1 +0.35 on every item | tenure chart shows it |",
              "| P6 | Norfolk Day B: apparent decline is a change in who responded | under_1 share 55% to 0% between waves | signal check says mix, not real |",
              "| P7 | Teams with fewer than 4 respondents | headcounts 2 and 3 | suppressed, rolled up to site |",
              "| P8 | Four Wave 2 comments about the shift handoff, Richmond Night A | written text | retrieved, counted as 4 of N |",
              "| P9 | Blip: Roanoke Day C Q04 falls, no operations change, no comments | item mean shifted by -0.6 only | 'insufficient evidence', watch item, no owner |",
              "| P10 | One long equipment comment, Norfolk Night A, no drop | one 150-word comment | 'single source', not an obstacle |",
              "", "## Checks", "",
              "- `tests/test_data.py`: every planted pattern is present at the stated strength; no comment comes from a suppressed team-wave; every employee id is unique.",
              "- `tests/test_agent.py`: suppression in SQL, numbers match the truth file, refusals, brief checks, red-team verdicts.",
              "- `evals/`: gold questions scored as a confusion matrix over the planted patterns (found, missed, invented, correctly declined).",
              "", "## Known limits", "",
              "- Real survey text is human behaviour; the comment bank is small and the wording is ours (judge Chang, Sept 15, 2026).",
              "- Response bias (only the happy or the angry answer) is not modelled (judges Fullowan and Lederman).",
              "- Two waves only; no Gallup global-database benchmark or percentile rank, because we have no licensed source for one.",
              ""]
    (HERE.parent / "DATA_SPEC.md").write_text("\n".join(lines))


def compute_truth(teams, employees, responses, comments, ops, staffing):
    """Record what was planted, using the values actually generated."""
    rich_night_a = team_key(teams, "Richmond", "Night A")
    norfolk_day_b = team_key(teams, "Norfolk", "Day B")
    roanoke_day_c = team_key(teams, "Roanoke", "Day C")
    norfolk_night_a = team_key(teams, "Norfolk", "Night A")

    def team_item(tid, item, wave):
        sub = responses[(responses.team_id == tid) & (responses.wave_id == wave)]
        return round(float(sub[item].mean()), 2), int(len(sub))

    p1_w1, n1 = team_item(rich_night_a, "q02", 1)
    p1_w2, n2 = team_item(rich_night_a, "q02", 2)
    p2_w1, _ = team_item(rich_night_a, "q07", 1)
    p2_w2, _ = team_item(rich_night_a, "q07", 2)

    o = ops[(ops["site_id"] == 1) & (ops["shift"] == "Night") & (ops["hour_band"] == "06-07")].copy()
    o["month"] = o.date.str.slice(0, 7)
    pre = o[o.date < "2026-06-01"]
    post = o[o.date >= "2026-06-01"]
    late_pre = round(float(pre.late_departures.sum() / pre.departures.sum()), 3)
    late_post = round(float(post.late_departures.sum() / post.departures.sum()), 3)

    st = staffing[(staffing["site_id"] == 1) & (staffing["shift"] == "Night") & (staffing["month"] == "2026-03")].iloc[0]

    # P5 honeymoon: grand mean by tenure band, all teams, all waves
    merged = responses.merge(employees[["emp_id", "tenure_band"]], on="emp_id")
    merged["grand"] = merged[ITEM_CODES].mean(axis=1)
    by_band = merged.groupby("tenure_band").grand.mean().round(2).to_dict()

    # P6 mix shift on Norfolk Day B
    nb = merged[merged.team_id == norfolk_day_b]
    p6 = {
        "team_id": norfolk_day_b,
        "team_mean_w1": round(float(nb[nb.wave_id == 1].grand.mean()), 2),
        "team_mean_w2": round(float(nb[nb.wave_id == 2].grand.mean()), 2),
        "under_1_share_w1": round(float((nb[nb.wave_id == 1].tenure_band == "under_1").mean()), 2),
        "under_1_share_w2": round(float((nb[nb.wave_id == 2].tenure_band == "under_1").mean()), 2),
        "by_band_w1": nb[nb.wave_id == 1].groupby("tenure_band").grand.mean().round(2).to_dict(),
        "by_band_w2": nb[nb.wave_id == 2].groupby("tenure_band").grand.mean().round(2).to_dict(),
    }

    # P7 small teams
    counts = responses.groupby(["team_id", "wave_id"]).size().reset_index(name="n")
    small = counts[counts.n < MIN_N].merge(teams[["team_id", "site_id", "team_name"]], on="team_id")
    p7 = [{"team_id": int(r.team_id), "site_id": int(r.site_id), "team_name": r.team_name,
           "wave_id": int(r.wave_id), "n": int(r.n)} for r in small.itertuples()]

    p8 = comments[(comments.team_id == rich_night_a) & (comments.theme == "handoff")]

    # P9 blip: Roanoke Day C q04 falls, nothing else moves for that site and shift
    p9_w1, p9_n1 = team_item(roanoke_day_c, "q04", 1)
    p9_w2, p9_n2 = team_item(roanoke_day_c, "q04", 2)
    o3 = ops[(ops["site_id"] == 3) & (ops["shift"] == "Day")].copy()
    pre3, post3 = o3[o3.date < "2026-06-01"], o3[o3.date >= "2026-06-01"]
    p9_late_pre = round(float(pre3.late_departures.sum() / pre3.departures.sum()), 3)
    p9_late_post = round(float(post3.late_departures.sum() / post3.departures.sum()), 3)
    p9_comments = int(((comments.team_id == roanoke_day_c) & (comments.wave_id == 2)).sum())

    # P10 loud comment: Norfolk Night A has no planted drop; one long equipment comment
    p10 = comments[(comments.team_id == norfolk_night_a) & (comments.theme == "tools_loud")]
    nna = responses[responses.team_id == norfolk_night_a]
    p10_gm = {w: round(float(nna[nna.wave_id == w][ITEM_CODES].mean(axis=1).mean()), 2) for w in (1, 2)}
    p10_total_w2 = int(((comments.team_id == norfolk_night_a) & (comments.wave_id == 2)).sum())

    truth = {
        "company": "Northline Logistics (fictional)",
        "min_n": MIN_N,
        "patterns": {
            "P1": {"what": "Richmond Night A q02 drop", "team_id": rich_night_a, "item": "q02",
                   "wave1_mean": p1_w1, "wave2_mean": p1_w2, "n_wave1": n1, "n_wave2": n2},
            "P2": {"what": "Richmond Night A q07 drop", "team_id": rich_night_a, "item": "q07",
                   "wave1_mean": p2_w1, "wave2_mean": p2_w2},
            "P3": {"what": "Richmond Night 06-07 late departures rise from June 2026",
                   "site_id": 1, "shift": "Night", "hour_band": "06-07",
                   "late_rate_before_june": late_pre, "late_rate_from_june": late_post},
            "P4": {"what": "Richmond Night staffing shortage March 2026", "site_id": 1,
                   "shift": "Night", "month": "2026-03",
                   "scheduled": int(st.scheduled_headcount), "actual": int(st.actual_headcount)},
            "P5": {"what": "Honeymoon effect: under_1 scores higher", "grand_mean_by_tenure": by_band,
                   "planted_offset": HONEYMOON},
            "P6": {"what": "Norfolk Day B apparent decline is a response-mix change", **p6},
            "P7": {"what": "Team-waves with n under MIN_N (must be suppressed)", "rows": p7},
            "P8": {"what": "Handoff comments, Richmond Night A, wave 2",
                   "comment_ids": [int(c) for c in p8.comment_id]},
            "P9": {"what": "Blip: Roanoke Day C q04 drops with no operational signal and no comments (must be 'insufficient')",
                   "team_id": roanoke_day_c, "item": "q04", "wave1_mean": p9_w1, "wave2_mean": p9_w2,
                   "n_wave1": p9_n1, "n_wave2": p9_n2, "site_day_late_rate_before_june": p9_late_pre,
                   "site_day_late_rate_from_june": p9_late_post, "wave2_comments": p9_comments},
            "P10": {"what": "One loud comment: Norfolk Night A, wave 2, long equipment comment; no planted drop (must be 'single source')",
                    "team_id": norfolk_night_a, "comment_ids": [int(c) for c in p10.comment_id],
                    "comment_words": int(len(LOUD_COMMENT.split())), "wave2_comments_total": p10_total_w2,
                    "grand_mean_w1": p10_gm[1], "grand_mean_w2": p10_gm[2]},
        },
        "owner_for_handoff_richmond": "Site Operations Manager, Richmond (see ownership_directory)",
    }
    return truth


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    teams = build_teams()
    employees = build_employees(teams)
    responses = build_responses(teams, employees)
    comments = build_comments(teams, responses)
    ops = build_ops(teams)
    staffing = build_staffing(teams)
    ownership = build_ownership(teams)
    sites = pd.DataFrame([{"site_id": i, "site_name": n} for i, n in SITES])
    waves = pd.DataFrame([{"wave_id": i, "wave_name": n, "close_date": d.isoformat()} for i, n, d in WAVES])
    items = pd.DataFrame([{"item": c, "label": l} for c, l in ITEMS])

    for name, df in [("sites", sites), ("teams", teams), ("employees", employees), ("waves", waves),
                     ("responses", responses), ("comments", comments), ("ops_daily", ops),
                     ("staffing", staffing), ("ownership_directory", ownership), ("q12_items", items)]:
        df.to_csv(OUT / f"{name}.csv", index=False)
    write_docs(ownership)
    truth = compute_truth(teams, employees, responses, comments, ops, staffing)
    (OUT / "truth.json").write_text(json.dumps(truth, indent=2))
    write_data_spec({"sites": sites, "teams": teams, "employees": employees, "waves": waves, "responses": responses,
                     "comments": comments, "ops_daily": ops, "staffing": staffing, "ownership_directory": ownership,
                     "q12_items": items}, truth)
    print(f"teams={len(teams)} employees={len(employees)} responses={len(responses)} "
          f"comments={len(comments)} ops_rows={len(ops)} staffing_rows={len(staffing)}")
    print("P1", truth["patterns"]["P1"])
    print("P3", truth["patterns"]["P3"])
    print("P5", truth["patterns"]["P5"]["grand_mean_by_tenure"])
    print("P6", {k: v for k, v in truth["patterns"]["P6"].items() if k.startswith(("team_mean", "under_1"))})
    print("P7 small team-waves:", len(truth["patterns"]["P7"]["rows"]))
    print("P9", truth["patterns"]["P9"])
    print("P10", {k: v for k, v in truth["patterns"]["P10"].items() if k != "what"})


if __name__ == "__main__":
    main()
