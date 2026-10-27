"""Synthetic data generator for the Friction Finder prototype (healthcare variant).

Everything here is fictional. Lanford Health does not exist. The survey is shaped like a
12-item, 1-to-5 engagement survey with two waves; the operating and staffing records are
invented; the documents are written by the team. No patient-level data of any kind: every
operating metric is a count at unit, shift, or site level. Planted patterns are recorded in
truth.json so the assistant can be scored against known answers.

Run:  python data/generate.py   (writes to data/generated/ and data/docs/)
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from . import generate_impact
except ImportError:  # run as a script: python data/generate.py
    import generate_impact

SEED = 42
HERE = Path(__file__).resolve().parent
OUT = HERE / "generated"
DOCS = HERE / "docs"
MIN_N = 4  # Gallup's stated minimum reporting n (Keegan, Sept 14, 2026)
COMPANY = "Lanford Health (fictional)"
KEEP_DOCS = {"gallup_item_discussion_questions.md"}  # written by hand, not by this script; every other .md here is regenerated

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

# Short names; the long forms are Lanford Medical Center, Westbrook Community Hospital, Pine Hollow Hospital.
SITES = [(1, "Lanford"), (2, "Westbrook"), (3, "Pine Hollow")]
# (team_name, shift, headcount). Same order, shifts and headcounts as v0.8, so team ids are unchanged (1 to 24).
# Small teams are deliberate: they fall under MIN_N.
TEAM_TEMPLATE = [
    ("Med-Surg Day", "Day", 12),
    ("Telemetry Day", "Day", 12),
    ("ED Day", "Day", 8),
    ("Med-Surg Night", "Night", 14),
    ("ICU Night", "Night", 7),
    ("Resp Therapy Day", "Day", 5),
    ("Pharmacy Day", "Day", 3),
    ("EVS Night", "Night", 2),
]
PLANTED_TEAM = ("Lanford", "Med-Surg Night")        # P1, P2, P3, P8, P11 (team_id 4)
COHORT_TEAM = ("Westbrook", "Telemetry Day")        # P6 (team_id 10)
BLIP_TEAM = ("Pine Hollow", "ED Day")               # P9 (team_id 19)
LOUD_TEAM = ("Westbrook", "Med-Surg Night")         # P10 (team_id 12)
TENURE_BANDS = ["under_1", "1_to_3", "3_to_10", "over_10"]
TENURE_P = [0.22, 0.30, 0.33, 0.15]
HONEYMOON = 0.35  # under_1 scores this much higher on every item (P5)
COHORT_EXTRA = 0.25  # Westbrook Telemetry Day's new-graduate residency cohort is unusually upbeat (makes P6 visible)
NOISE_SD = 0.5
EMP_SD = 0.2
PLANTED_DROPS = {"q02": -0.9, "q07": -0.7}  # Lanford Med-Surg Night, wave 2 (P1, P2)
BLIP_DROP = {"q04": -0.6}  # P9: Pine Hollow ED Day, wave 2. A survey-only blip: no operating signal, no comments.
                           # Red-team case from judge Lederman (MITRE, Sept 15, 2026): the brief must say
                           # "insufficient evidence", not propose an action.

WAVES = [(1, "Wave 1", date(2026, 3, 15)), (2, "Wave 2", date(2026, 9, 10))]

FIRST = ["Dana", "Marcus", "Priya", "Luis", "Aisha", "Tom", "Elena", "Kwame", "Sofia", "Jordan",
         "Nadia", "Omar", "Grace", "Victor", "Hana", "Sam", "Leila", "Ravi", "Maya", "Ben",
         "Chloe", "Diego", "Ines", "Noah"]
LAST = ["Alvarez", "Brooks", "Chen", "Diallo", "Evans", "Farah", "Garcia", "Hughes", "Ibrahim",
        "Jensen", "Kim", "Lopez", "Mensah", "Novak", "Okafor", "Patel", "Quinn", "Reyes",
        "Singh", "Turner", "Usman", "Vega", "Walsh", "Young"]

# Oct 27, 2026: build_ownership() restarts the same seeded stream build_teams() uses, so the nine site owners were the first
# nine unit managers' names (Priya Singh was the Lanford pharmacy owner AND a unit manager; Ravi Singh appeared four times;
# the demo persona Priya Singh assigned a task to Priya Singh and signed as Priya Quinn). These fixed renames are applied
# AFTER the draws, so every RNG call and every other file stay byte-identical. The Lanford pharmacy owner keeps her name:
# the eval results and the seeded plan cite "Priya Singh, Pharmacy Operations Manager".
TEAM_RENAMES = {1: "Sofia Alvarez", 4: "Hana Mensah", 8: "Omar Lopez", 17: "Mei Tanaka"}   # team_id -> manager_name (17: a second Priya in the revised-plan story)
OWNER_RENAMES = {                                                                   # (site_id, owner_role) -> owner_name
    (1, "Nurse Manager, Med-Surg"): "Tom Evans", (1, "Clinical Engineering Lead"): "Kwame Hughes",
    (2, "Pharmacy Operations Manager"): "Ben Jensen", (2, "Nurse Manager, Med-Surg"): "Ines Reyes", (2, "Clinical Engineering Lead"): "Noah Garcia",
    (3, "Pharmacy Operations Manager"): "Rosa Delgado", (3, "Nurse Manager, Med-Surg"): "Felix Adeyemi", (3, "Clinical Engineering Lead"): "Mira Kowalski",
}


def check_unique_names(teams: pd.DataFrame, ownership: pd.DataFrame) -> None:
    """No two people in the unit list and the ownership directory share a full name (Oct 27 fix)."""
    names = list(teams.manager_name) + list(ownership.owner_name)
    dupes = sorted({n for n in names if names.count(n) > 1})
    if dupes:
        raise SystemExit(f"duplicate synthetic names, extend TEAM_RENAMES / OWNER_RENAMES: {dupes}")

# Same number of themes and of lines per theme as v0.8, so the comment RNG stream is unchanged.
GENERIC_COMMENTS = {
    "workload": [
        "The workload has been heavy this quarter but the team pulls together.",
        "Too many priorities at once; it is hard to know what matters most on a busy shift.",
        "Patient assignments are fair most days, but I would like more notice when we are short.",
    ],
    "recognition": [
        "My nurse manager notices good work and says so. That helps.",
        "Recognition is rare here. A thank you now and then would go a long way.",
    ],
    "tools": [
        "The new computers on wheels work well most days.",
        "Supplies run out on the unit and it takes too long to get them replaced.",
    ],
    "communication": [
        "Daily huddles are useful. Keep them short.",
        "Policy changes get announced late and we scramble to catch up.",
    ],
    "schedule": [
        "Self-scheduling works well. No complaints.",
        "Shift swaps are hard to arrange when someone calls in sick.",
    ],
    "development": [
        "I would like a clearer path to a charge nurse role.",
        "Preceptor training and certification support have been great for me.",
    ],
}

# P10: one long comment (red-team case from judge Chang, FI Consulting, Sept 15, 2026). One
# nurse writes a page about IV pumps; the brief must weight breadth, not length, and label
# it single-source.
LOUD_COMMENT = (
    "I want to put on record how bad the IV pump situation has become on nights. Half of the pumps "
    "on our unit have been tagged out for service since spring, and every time we open a biomed ticket "
    "it sits for weeks before anyone looks at it. When a pump fails mid-shift we borrow from the unit "
    "next door, who resent it, and nurses end up running secondary lines by gravity and counting drops. "
    "It is slow, it is unsafe, and nobody upstairs seems to notice. I have raised it in three huddles. "
    "Clinical engineering says replacement parts are on order but that has been the answer since April. "
    "If leadership wants to know why people are frustrated on this shift, start with the pumps. Fix the "
    "ticket queue, buy the parts, and stop treating night shift as an afterthought."
)

# P8: four wave-2 comments from the planted team about the automated dispensing cabinet (ADC).
RESTOCK_COMMENTS = [
    "Pharmacy restocks our cabinet at seven now, after the six o'clock pass. We open the bins and half of what we need is not there.",
    "Since spring the cabinet is empty at 06:00. We call pharmacy or borrow from the unit next door, and the pass runs late either way.",
    "We raised the restock time in three huddles and nothing changed. The 06:00 pass is late most mornings because the bins are not filled until 07:00.",
    "Waiting on pharmacy at six in the morning is the worst part of the shift. The cabinet restock used to be done before we started the pass.",
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
    teams["manager_name"] = [TEAM_RENAMES.get(int(t), n) for t, n in zip(teams.team_id, teams.manager_name)]  # after the draws
    return teams


def build_employees(teams: pd.DataFrame):
    r = rng()
    cohort_team = team_key(teams, *COHORT_TEAM)
    rows = []
    eid = 0
    for _, t in teams.iterrows():
        for i in range(int(t.headcount)):
            eid += 1
            band = r.choice(TENURE_BANDS, p=TENURE_P)
            if int(t.team_id) == cohort_team:
                # P6: half of this team is a new-graduate nurse residency cohort
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
    """Respondent-level answers. Planted: P1, P2 (Lanford Med-Surg Night drop), P5 honeymoon,
    P6 mix-shift on Westbrook Telemetry Day. Response rate about 85% otherwise."""
    r = rng()
    planted = team_key(teams, *PLANTED_TEAM)
    cohort_team = team_key(teams, *COHORT_TEAM)
    blip_team = team_key(teams, *BLIP_TEAM)

    # team x item baseline around 3.8, stable across waves except planted shifts
    base = {}
    for tid in teams.team_id:
        base[tid] = {c: float(np.clip(r.normal(3.85, 0.15), 3.4, 4.3)) for c in ITEM_CODES}
    # planted drops (wave 2 only)
    drop = {planted: PLANTED_DROPS, blip_team: BLIP_DROP}  # P1/P2 and P9

    emp_effect = {int(e.emp_id): float(r.normal(0, EMP_SD)) for e in employees.itertuples()}

    rows = []
    for wave_id, _, _ in WAVES:
        for e in employees.itertuples():
            tid = int(e.team_id)
            # response decision
            p_respond = 0.85
            if tid == planted:
                p_respond = 0.95  # keep n high on the planted team so the drop is not noise
            if tid == cohort_team and wave_id == 1:
                p_respond = 0.95
            if tid == cohort_team and wave_id == 2:
                p_respond = 0.10 if e.tenure_band == "under_1" else 0.95  # P6 mix shift
            if r.uniform() > p_respond:
                continue
            rec = {"emp_id": int(e.emp_id), "team_id": tid, "wave_id": wave_id}
            for c in ITEM_CODES:
                mu = base[tid][c] + emp_effect[int(e.emp_id)]
                if e.tenure_band == "under_1":
                    mu += HONEYMOON
                    if tid == cohort_team:
                        mu += COHORT_EXTRA
                if wave_id == 2 and tid in drop and c in drop[tid]:
                    mu += drop[tid][c]
                val = int(np.clip(np.rint(r.normal(mu, NOISE_SD)), 1, 5))
                rec[c] = val
            rows.append(rec)
    return pd.DataFrame(rows)


def build_comments(teams: pd.DataFrame, responses: pd.DataFrame):
    r = rng()
    planted = team_key(teams, *PLANTED_TEAM)
    loud_team = team_key(teams, *LOUD_TEAM)
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
    # P8: restock comments, Lanford Med-Surg Night, wave 2
    for text in RESTOCK_COMMENTS:
        cid += 1
        rows.append({"comment_id": cid, "team_id": planted, "wave_id": 2, "text": text,
                     "theme": "restock"})
    # P10: one loud comment, Westbrook Med-Surg Night, wave 2
    cid += 1
    rows.append({"comment_id": cid, "team_id": loud_team, "wave_id": 2, "text": LOUD_COMMENT,
                 "theme": "tools_loud"})
    return pd.DataFrame(rows)


# Medication-pass hour bands. The 06-07 band is the 06:00 medication pass before the 07:00 shift change.
HOUR_BANDS = [("02-06", "Night"), ("06-07", "Night"), ("07-10", "Day"), ("10-14", "Day"),
              ("14-18", "Day"), ("18-22", "Night"), ("22-02", "Night")]
DOSE_MEAN = {"default": 144, "06-07": 192}   # about 8x the v0.8 means (18 and 24) so counts look like a hospital unit group


def build_ops(teams: pd.DataFrame):
    """Daily scheduled medication doses per site, shift, hour band (eMAR counts; nothing patient-level).
    P3: Lanford Night 06-07 late-dose rate rises from ~8% to ~18% from 2026-06-01. Everything else flat at ~8%."""
    r = rng()
    rows = []
    d = date(2026, 1, 1)
    end = date(2026, 9, 10)
    while d <= end:
        for site_id, site_name in SITES:
            for band, shift in HOUR_BANDS:
                scheduled = int(r.poisson(DOSE_MEAN.get(band, DOSE_MEAN["default"])))
                late_rate = 0.08
                if site_name == PLANTED_TEAM[0] and shift == "Night" and band == "06-07" and d >= date(2026, 6, 1):
                    late_rate = 0.18
                late = int(r.binomial(scheduled, late_rate))
                missed = int(r.poisson(1.5))
                rows.append({"date": d.isoformat(), "site_id": site_id, "shift": shift,
                             "hour_band": band, "scheduled_doses": scheduled,
                             "late_doses": late, "missed_doses": missed})
        d += timedelta(days=1)
    return pd.DataFrame(rows)


def build_staffing(teams: pd.DataFrame):
    """Monthly scheduled vs actual RN headcount per site and shift. P4: Lanford Night March
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


RESTOCK_PROCESS = "Medication cabinet restocking schedule"
RESTOCK_OWNER_ROLE = "Pharmacy Operations Manager"


def build_ownership(teams: pd.DataFrame):
    r = rng()  # same draw order as v0.8, so the owner names are unchanged
    rows = []
    for site_id, site_name in SITES:
        pharm = f"{r.choice(FIRST)} {r.choice(LAST)}"
        nurse_mgr = f"{r.choice(FIRST)} {r.choice(LAST)}"
        rows += [
            {"process_name": RESTOCK_PROCESS, "site_id": site_id, "site_name": site_name,
             "owner_role": RESTOCK_OWNER_ROLE, "owner_name": pharm},
            {"process_name": "Unit staffing and bedside shift report", "site_id": site_id, "site_name": site_name,
             "owner_role": "Nurse Manager, Med-Surg", "owner_name": nurse_mgr},
            {"process_name": "IV pump and equipment maintenance", "site_id": site_id,
             "site_name": site_name, "owner_role": "Clinical Engineering Lead",
             "owner_name": f"{r.choice(FIRST)} {r.choice(LAST)}"},
        ]
    rows += [
        {"process_name": "Engagement survey and action planning", "site_id": 0, "site_name": "ALL",
         "owner_role": "HR Business Partner", "owner_name": "Dana Whitfield"},
        {"process_name": "Nurse staffing and float policy", "site_id": 0, "site_name": "ALL",
         "owner_role": "Chief Nursing Officer", "owner_name": "Marcus Okafor"},
    ]
    for row in rows:  # after the draws, see OWNER_RENAMES
        row["owner_name"] = OWNER_RENAMES.get((int(row["site_id"]), row["owner_role"]), row["owner_name"])
    return pd.DataFrame(rows)


def write_docs(ownership: pd.DataFrame):
    DOCS.mkdir(parents=True, exist_ok=True)
    for stale in DOCS.glob("*.md"):  # the v0.8 documents are replaced, not kept beside the new ones
        if stale.name not in KEEP_DOCS:
            stale.unlink()
    (DOCS / "medication_cabinet_restock_procedure.md").write_text("""# Medication Cabinet Restock Procedure (SOP-PHARM-021)

Illustrative document written for a fictional hospital system. Not a real Lanford Health document.

## Purpose
Ensure each unit's automated dispensing cabinet (ADC) is restocked so that stock is on hand for
every scheduled medication pass, including the 06:00 pass that runs before the 07:00 shift change.

## Steps
1. Pharmacy technicians restock each unit cabinet **by 05:00 daily**, working from the overnight
   restock report.
2. The **restock report** lists every item below its par level. The technician signs the report
   when the cabinet is filled; the signed report is kept at the pharmacy desk.
3. The charge nurse reviews the restock report at the start of the 06:00 pass and confirms that
   the items below par have been filled.
4. A stock-out during a pass is logged in the **stock-out log** (item, time, unit). Pharmacy brings
   the item to the unit within 30 minutes of the log entry.

## Ownership
The Pharmacy Operations Manager at each site owns the restock schedule and its compliance
(steps 1 and 2). The Nurse Manager owns the stock-out log (step 4).

## Review
Reviewed annually. Last review: January 2026.
""")
    (DOCS / "nurse_staffing_policy.md").write_text("""# Nurse Staffing Policy (POL-NURS-006)

Illustrative document written for a fictional hospital system.

- Unit schedules are published at least 4 weeks in advance.
- Minimum RN staffing per shift is set by the Nurse Manager and reviewed monthly against the
  staffing report (scheduled versus actual RN headcount).
- When actual RN headcount falls below 85% of scheduled for a shift in a given month, the
  Chief Nursing Officer is notified and a recovery plan is required within two weeks.
- Float pool nurses are assigned by the house supervisor. Agency nurses are used only after the
  float pool is exhausted and require Chief Nursing Officer approval.
- Shift swaps are approved by the charge nurse and must not reduce a shift below minimum staffing.
- The Chief Nursing Officer owns this policy.
""")
    (DOCS / "engagement_action_planning_guide.md").write_text("""# Engagement Action Planning Guide (internal)

Illustrative document written for a fictional hospital system. Generic guidance, not vendor material.

After survey results are released, each nurse manager with reportable results (four or more
respondents) reviews them with the unit, selects one or two focus areas, and records an action
with an owner, a success measure, and a review date. Results for units with fewer than four
respondents are not shown; those managers review the site-level results with their
Director of Nursing instead.

Actions are reviewed at the mid-point between surveys. The HR Business Partner owns the
process and tracks completion.
""")
    lines = ["# Process Ownership Directory\n", "Illustrative directory for a fictional hospital system.\n",
             "| Process | Site | Owner role | Owner name |", "|---|---|---|---|"]
    for o in ownership.itertuples():
        lines.append(f"| {o.process_name} | {o.site_name} | {o.owner_role} | {o.owner_name} |")
    (DOCS / "ownership_directory.md").write_text("\n".join(lines) + "\n")


def write_data_spec(frames: dict, truth: dict):
    """One-page data specification (judge Lederman, MITRE, Sept 15, 2026: 'what's the data feeding
    this tool? How many records? What fields?'). Regenerated on every run."""
    lines = ["# Data specification (synthetic)", "",
             f"Generated by `data/generate.py`, seed {SEED}, on every run. Fictional company: {COMPANY}, a regional hospital "
             "system (three hospitals, Day and Night shifts). Nothing here is real, and nothing is patient-level: every operating "
             "metric is a count at unit, shift, or site level. The shape follows a survey-vendor team export "
             "(team x wave x item aggregates) so that a real export could replace the survey tables without code changes.",
             "", "## Tables", "", "| Table | Grain | Rows | Fields |", "|---|---|---|---|"]
    grain = {"sites": "hospital site", "teams": "nursing unit team", "employees": "employee (no PII; unique emp_id)", "waves": "survey wave",
             "responses": "respondent x wave (never shown to the model)", "comments": "open-text comment (reportable team-waves only are indexed)",
             "ops_daily": "site x shift x hour band x day (eMAR dose counts)", "staffing": "site x shift x month (RN headcount)",
             "ownership_directory": "process x site", "q12_items": "survey item"}
    for name, df in frames.items():
        lines.append(f"| {name} | {grain.get(name, '')} | {len(df):,} | {', '.join(df.columns)} |")
    lines += ["", "## How the numbers are made", "",
              f"- Survey: 12 items, 1 to 5. Each team has a baseline near 3.85 per item; each employee has a fixed offset (SD {EMP_SD}); "
              f"each answer adds noise (SD {NOISE_SD}) and is rounded to 1 to 5. Response rate about 85% per wave.",
              f"- Tenure: bands under_1, 1_to_3, 3_to_10, over_10 with shares {TENURE_P}. Under-one-year employees score {HONEYMOON} higher "
              "on every item (the year-one honeymoon effect Gallup described on Sept 14, 2026).",
              "- Medication passes: daily scheduled doses per site, shift, and hour band (Poisson), with a flat 8% late-dose rate "
              "(given more than 60 minutes after the scheduled time) except where planted; missed doses Poisson(1.5).",
              "- Staffing: monthly scheduled versus actual RN headcount, about 97% except where planted.",
              "- Comments: one to two generic comments per reportable team-wave, drawn from a small bank, plus the planted ones.",
              "- Team-month operating records (`team_ops_monthly`): absence days, late doses, quits, overtime shifts and injuries per team "
              "and month, Poisson around a per-head base rate that moves with the team's engagement (P12), plus the P11 multipliers.",
              "", "## Planted patterns (the answer key the assistant is scored against)", "",
              "| Id | What | Planted how | Expected behaviour |", "|---|---|---|---|",
              "| P1, P2 | Lanford Med-Surg Night: Q02 (materials and equipment) and Q07 (opinions count) fall in Wave 2 | item means shifted by -0.9 and -0.7 | found, material, corroborated |",
              "| P3 | Lanford Night 06-07 late doses rise from June 2026 | late-dose rate 8% to 18% in that band only | operating signal found |",
              "| P4 | Lanford Night RN staffing shortage, March 2026 | actual 80% of scheduled | listed as a competing explanation |",
              "| P5 | Honeymoon effect | under_1 +0.35 on every item | tenure chart shows it |",
              "| P6 | Westbrook Telemetry Day: apparent decline is a change in who responded | under_1 share 55% to 0% between waves | signal check says mix, not real |",
              "| P7 | Teams with fewer than 4 respondents | headcounts 2 and 3 | suppressed, rolled up to site |",
              "| P8 | Four Wave 2 comments about the dispensing-cabinet restock, Lanford Med-Surg Night | written text | retrieved, counted as 4 of N |",
              "| P9 | Blip: Pine Hollow ED Day Q04 falls, no operating change, no comments | item mean shifted by -0.6 only | 'insufficient evidence', watch item, no owner |",
              "| P10 | One long IV-pump comment, Westbrook Med-Surg Night, no drop | one 150-word comment | 'single source', not an obstacle |",
              "| P11 | Lanford Med-Surg Night: late doses, absences, quits elevated Jun-Sep 2026, recover Oct-Nov | multipliers 2.0, 1.35, 1.6 | flagged at detect, 'worked' at review |",
              "| P12 | Lower Q02 goes with more late doses and overtime shifts; lower grand mean with more absences and quits | log-rate elasticities | association found |",
              "| P13 | Injuries independent of engagement | constant base rate | 'no association detected' |",
              "| P14 | Pine Hollow Med-Surg Day: unplanned overtime about 3.5x Feb-Aug 2026; plan 1 (June 21, float RN) misses the obstacle, plan 2 (Sept 1, IV pump par level) is followed by the base rate | excess drawn from a second generator and added, so no other team-month changes | plan 1 'inconclusive' at Aug 31, plan 2 'worked' at Nov 30; shown as the revised-plan case |",
              "", "## Checks", "",
              "- `tests/test_data.py`: every planted pattern is present at the stated strength; no comment comes from a suppressed team-wave; every employee id is unique.",
              "- `tests/test_agent.py`: suppression in SQL, numbers match the truth file, refusals, brief checks, red-team verdicts.",
              "- `evals/`: gold questions scored as a confusion matrix over the planted patterns (found, missed, invented, correctly declined).",
              "", "## Known limits", "",
              "- Real survey text is human behaviour; the comment bank is small and the wording is ours (judge Chang, Sept 15, 2026).",
              "- Response bias (only the happy or the angry answer) is not modelled (judges Fullowan and Lederman).",
              "- Two waves only; no Gallup global-database benchmark or percentile rank, because we have no licensed source for one.",
              "- Dose counts are unit-level eMAR aggregates; no patient identifiers, diagnoses or patient-experience responses exist anywhere in the data.",
              ""]
    (HERE.parent / "DATA_SPEC.md").write_text("\n".join(lines))


def compute_truth(teams, employees, responses, comments, ops, staffing):
    """Record what was planted, using the values actually generated."""
    planted = team_key(teams, *PLANTED_TEAM)
    cohort_team = team_key(teams, *COHORT_TEAM)
    blip_team = team_key(teams, *BLIP_TEAM)
    loud_team = team_key(teams, *LOUD_TEAM)
    planted_label = " ".join(PLANTED_TEAM)
    cohort_label = " ".join(COHORT_TEAM)
    blip_label = " ".join(BLIP_TEAM)
    loud_label = " ".join(LOUD_TEAM)

    def team_item(tid, item, wave):
        sub = responses[(responses.team_id == tid) & (responses.wave_id == wave)]
        return round(float(sub[item].mean()), 2), int(len(sub))

    p1_w1, n1 = team_item(planted, "q02", 1)
    p1_w2, n2 = team_item(planted, "q02", 2)
    p2_w1, _ = team_item(planted, "q07", 1)
    p2_w2, _ = team_item(planted, "q07", 2)

    o = ops[(ops["site_id"] == 1) & (ops["shift"] == "Night") & (ops["hour_band"] == "06-07")].copy()
    o["month"] = o.date.str.slice(0, 7)
    pre = o[o.date < "2026-06-01"]
    post = o[o.date >= "2026-06-01"]
    late_pre = round(float(pre.late_doses.sum() / pre.scheduled_doses.sum()), 3)
    late_post = round(float(post.late_doses.sum() / post.scheduled_doses.sum()), 3)

    st = staffing[(staffing["site_id"] == 1) & (staffing["shift"] == "Night") & (staffing["month"] == "2026-03")].iloc[0]

    # P5 honeymoon: grand mean by tenure band, all teams, all waves
    merged = responses.merge(employees[["emp_id", "tenure_band"]], on="emp_id")
    merged["grand"] = merged[ITEM_CODES].mean(axis=1)
    by_band = merged.groupby("tenure_band").grand.mean().round(2).to_dict()

    # P6 mix shift on Westbrook Telemetry Day
    nb = merged[merged.team_id == cohort_team]
    p6 = {
        "team_id": cohort_team,
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

    p8 = comments[(comments.team_id == planted) & (comments.theme == "restock")]

    # P9 blip: Pine Hollow ED Day q04 falls, nothing else moves for that site and shift
    p9_w1, p9_n1 = team_item(blip_team, "q04", 1)
    p9_w2, p9_n2 = team_item(blip_team, "q04", 2)
    o3 = ops[(ops["site_id"] == 3) & (ops["shift"] == "Day")].copy()
    pre3, post3 = o3[o3.date < "2026-06-01"], o3[o3.date >= "2026-06-01"]
    p9_late_pre = round(float(pre3.late_doses.sum() / pre3.scheduled_doses.sum()), 3)
    p9_late_post = round(float(post3.late_doses.sum() / post3.scheduled_doses.sum()), 3)
    p9_comments = int(((comments.team_id == blip_team) & (comments.wave_id == 2)).sum())

    # P10 loud comment: Westbrook Med-Surg Night has no planted drop; one long IV-pump comment
    p10 = comments[(comments.team_id == loud_team) & (comments.theme == "tools_loud")]
    nna = responses[responses.team_id == loud_team]
    p10_gm = {w: round(float(nna[nna.wave_id == w][ITEM_CODES].mean(axis=1).mean()), 2) for w in (1, 2)}
    p10_total_w2 = int(((comments.team_id == loud_team) & (comments.wave_id == 2)).sum())

    truth = {
        "company": COMPANY,
        "min_n": MIN_N,
        "patterns": {
            "P1": {"what": f"{planted_label} q02 drop", "team_id": planted, "item": "q02",
                   "wave1_mean": p1_w1, "wave2_mean": p1_w2, "n_wave1": n1, "n_wave2": n2},
            "P2": {"what": f"{planted_label} q07 drop", "team_id": planted, "item": "q07",
                   "wave1_mean": p2_w1, "wave2_mean": p2_w2},
            "P3": {"what": f"{PLANTED_TEAM[0]} Night 06-07 late doses rise from June 2026",
                   "site_id": 1, "shift": "Night", "hour_band": "06-07",
                   "late_rate_before_june": late_pre, "late_rate_from_june": late_post},
            "P4": {"what": f"{PLANTED_TEAM[0]} Night RN staffing shortage March 2026", "site_id": 1,
                   "shift": "Night", "month": "2026-03",
                   "scheduled": int(st.scheduled_headcount), "actual": int(st.actual_headcount)},
            "P5": {"what": "Honeymoon effect: under_1 scores higher", "grand_mean_by_tenure": by_band,
                   "planted_offset": HONEYMOON},
            "P6": {"what": f"{cohort_label} apparent decline is a response-mix change (new-graduate residency cohort answered wave 1 only)", **p6},
            "P7": {"what": "Team-waves with n under MIN_N (must be suppressed)", "rows": p7},
            "P8": {"what": f"Dispensing-cabinet restock comments, {planted_label}, wave 2",
                   "comment_ids": [int(c) for c in p8.comment_id]},
            "P9": {"what": f"Blip: {blip_label} q04 drops with no operating signal and no comments (must be 'insufficient')",
                   "team_id": blip_team, "item": "q04", "wave1_mean": p9_w1, "wave2_mean": p9_w2,
                   "n_wave1": p9_n1, "n_wave2": p9_n2, "site_day_late_rate_before_june": p9_late_pre,
                   "site_day_late_rate_from_june": p9_late_post, "wave2_comments": p9_comments},
            "P10": {"what": f"One loud comment: {loud_label}, wave 2, long IV-pump comment; no planted drop (must be 'single source')",
                    "team_id": loud_team, "comment_ids": [int(c) for c in p10.comment_id],
                    "comment_words": int(len(LOUD_COMMENT.split())), "wave2_comments_total": p10_total_w2,
                    "grand_mean_w1": p10_gm[1], "grand_mean_w2": p10_gm[2]},
        },
        "owner_for_restock_lanford": f"{RESTOCK_OWNER_ROLE}, {PLANTED_TEAM[0]} (see ownership_directory)",
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
    check_unique_names(teams, ownership)
    sites = pd.DataFrame([{"site_id": i, "site_name": n} for i, n in SITES])
    waves = pd.DataFrame([{"wave_id": i, "wave_name": n, "close_date": d.isoformat()} for i, n, d in WAVES])
    items = pd.DataFrame([{"item": c, "label": l} for c, l in ITEMS])

    for name, df in [("sites", sites), ("teams", teams), ("employees", employees), ("waves", waves),
                     ("responses", responses), ("comments", comments), ("ops_daily", ops),
                     ("staffing", staffing), ("ownership_directory", ownership), ("q12_items", items)]:
        df.to_csv(OUT / f"{name}.csv", index=False)
    write_docs(ownership)
    truth = compute_truth(teams, employees, responses, comments, ops, staffing)
    truth = generate_impact.run(teams, responses, truth, ownership)  # v0.6 tables; own RNG, survey files unchanged
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
    print("P11", {k: v for k, v in truth["patterns"]["P11"].items() if k.startswith("late_rate")})


if __name__ == "__main__":
    main()
