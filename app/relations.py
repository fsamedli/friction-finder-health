"""Relations the investigation needs to resolve a manager's words into entities (v0.8). Plain lookups over the
tables, no graph database: site -> teams, team -> shift and comparable teams, KPI <-> survey items (from the
cross-team association matrix), process -> owner (the ownership directory), plan -> team -> KPI.

resolve() turns phrases like "it", "this team", "the other night shifts", "Norfolk Night A", "no, I meant
Night B" into a context update. It never guesses: an ambiguous referent comes back as a clarification."""
from __future__ import annotations

import re

import pandas as pd

from app import config
from app import impact as I


def teams() -> pd.DataFrame:
    t = I._data()[1].merge(I._data()[2], on="site_id")
    return t


def site_name(site_id: int) -> str:
    return str(I._data()[2].set_index("site_id").loc[int(site_id), "site_name"])


def team_info(team_id: int) -> dict:
    t = teams()
    r = t[t.team_id == team_id].iloc[0]
    return {"team_id": int(r.team_id), "team": str(r.team_name), "site_id": int(r.site_id), "site": str(r.site_name),
            "shift": str(r["shift"]), "headcount": int(r.headcount), "label": f"{r.site_name} {r.team_name}",
            "reportable": bool(int(r.headcount) >= config.MIN_N)}


def site_teams(site_id: int) -> list[dict]:
    return [team_info(int(x)) for x in teams().query("site_id == @site_id").team_id]


def comparable_teams(team_id: int) -> tuple[list[dict], list[dict]]:
    """(comparable, excluded) exactly as app/impact.py selects them: same shift, every site, 4+ people, not itself.
    Excluded = same-shift teams left out because they have fewer than 4 people (named, never numbered)."""
    t = I._team(team_id)
    comp = [team_info(int(x)) for x in I._comparables(t).team_id]
    all_t = teams()
    small = all_t[(all_t["shift"] == t["shift"]) & (all_t.team_id != team_id) & (all_t.headcount < config.MIN_N)]
    return comp, [team_info(int(x)) for x in small.team_id]


def kpi_items(kpi: str) -> list[dict]:
    """Survey items whose cross-team association with this KPI excludes zero (the Insights matrix)."""
    out = [a for a in I.link_matrix() if a["kpi"] == kpi and a["verdict"] == "association" and a["item"] != "grand"]
    return sorted(out, key=lambda a: a["p"] if a["p"] is not None else 1)


def item_kpis(item: str) -> list[dict]:
    return [a for a in I.link_matrix() if a["item"] == item and a["verdict"] == "association"]


def owner(process: str, site: str | None) -> dict | None:
    d = pd.read_csv(config.DATA_DIR / "ownership_directory.csv")
    rows = d[(d.process_name == process) & ((d.site_name == site) | (d.site_name == "ALL"))] if site else d[d.process_name == process]
    if not len(rows):
        return None
    r = rows.sort_values("site_name", key=lambda s: s == "ALL").iloc[0]
    return {"process": r.process_name, "site": r.site_name, "role": r.owner_role, "name": r.owner_name}


def plans_for_team(team_id: int, as_of: str | None = None) -> list[dict]:
    """Approved plans for a team as they exist on the demo clock (the seeded plan is a fallback, as in the web app)."""
    ps = [p for p in I.load_plans() if int(p["team_id"]) == team_id and p.get("status") == "approved"]
    live = [p for p in ps if p["id"] != "plan-richmond-night-a"]
    if live:
        return live
    return [p for p in ps if as_of is None or as_of >= p["start"]]


# ---------------------------------------------------------------------------------------------- resolve
_IT = re.compile(r"\b(it|this|that|this team|that team|the team|they|them|their|its)\b", re.I)


def find_teams(text: str, site_hint: str | None = None) -> list[dict]:
    """Every team the text names. 'Night A' alone resolves at the site in context; with no site it is ambiguous."""
    t = teams()
    tl = text.lower()
    named_sites = [s for s in t.site_name.unique() if s.lower() in tl]
    hits = []
    for name in sorted(t.team_name.unique(), key=len, reverse=True):
        if re.search(rf"\b{re.escape(name.lower())}\b", tl):
            rows = t[t.team_name == name]
            sites = named_sites or ([site_hint] if site_hint else [])
            if sites:
                rows = rows[rows.site_name.isin(sites)]
            hits += [team_info(int(x)) for x in rows.team_id]
            tl = tl.replace(name.lower(), " ")
    return hits


def resolve(question: str, ctx: dict) -> dict:
    """Returns {"team_id", "site_id", "changed": [what changed], "clarify": str|None, "peers": str|None}.
    ctx carries the current team_id / site_id (may be None)."""
    q = question.strip()
    ql = q.lower()
    t = teams()
    out = {"team_id": ctx.get("team_id"), "site_id": ctx.get("site_id"), "changed": [], "clarify": None, "peers": None}
    cur_site = site_name(ctx["site_id"]) if ctx.get("site_id") else None
    named_sites = [s for s in t.site_name.unique() if s.lower() in ql]
    hits = find_teams(q, site_hint=named_sites[0] if len(named_sites) == 1 else cur_site)
    # peers, not a new subject: "compare it with the other night shifts / comparable teams / Norfolk Night A"
    if re.search(r"\b(other|the rest of the)\b.*\b(night|day)\s+shifts?\b|\bcomparable teams?\b|\bteams like (ours|this|it)\b", ql):
        out["peers"] = "comparable"
    compare = bool(re.search(r"\bcompare|versus|\bvs\.?\b|against\b", ql))
    if hits:
        uniq = {h["team_id"]: h for h in hits}
        if compare and out["team_id"] and len(uniq) == 1 and next(iter(uniq)) != out["team_id"]:
            out["peers"] = f"team:{next(iter(uniq))}"     # "compare it with Norfolk Night A": the subject stays
        elif len(uniq) == 1 or (compare and out["team_id"] in uniq):
            new = next(iter(uniq.values())) if len(uniq) == 1 else uniq[out["team_id"]]
            if new["team_id"] != out["team_id"]:
                out["changed"].append(f"team: {team_info(out['team_id'])['label'] if out['team_id'] else 'none'} -> {new['label']}")
            out["team_id"], out["site_id"] = new["team_id"], new["site_id"]
        else:
            labels = sorted(h["label"] for h in uniq.values())
            out["clarify"] = f"Which team do you mean: {', '.join(labels)}?"
            return out
    elif named_sites and len(named_sites) == 1:
        sid = int(t[t.site_name == named_sites[0]].site_id.iloc[0])
        if sid != out["site_id"]:
            out["changed"].append(f"site: {cur_site or 'none'} -> {named_sites[0]}")
            out["site_id"] = sid
            # a site switch drops the team unless the same-named team exists there ("switch to Norfolk")
            if out["team_id"]:
                old = team_info(out["team_id"])
                same = t[(t.site_name == named_sites[0]) & (t.team_name == old["team"])]
                out["team_id"] = int(same.team_id.iloc[0]) if len(same) else None
                if out["team_id"]:
                    out["changed"].append(f"team: {old['label']} -> {named_sites[0]} {old['team']}")
    if out["team_id"] is None and _IT.search(ql) and not named_sites:
        out["clarify"] = "Which team do you mean? Open a team on Investigate, or name it (for example 'Richmond Night A')."
    return out
