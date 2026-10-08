"""Rebuild before_after.html from screens/before (v0.7) and screens/after (v0.8). Run from docs/overnight/v0.8/.
Screens come from web/scripts/screens.mjs (same routes list for both sets, see WORKLOG)."""
import html
import os

PAIRS = [("Today", "/", "home", "/", "home"),
         ("Investigate (team list)", "/teams", "teams", "/investigate", "investigate"),
         ("Investigate Night A", "/teams/4", "teams_4", "/investigate/4", "investigate_4"),
         ("Explain (drivers)", "/teams/4?tab=drivers", "teams_4_tab_drivers", "/investigate/4?tab=drivers", "investigate_4_tab_drivers"),
         ("Evidence", "/teams/4?tab=evidence", "teams_4_tab_evidence", "/investigate/4?tab=evidence", "investigate_4_tab_evidence"),
         ("Act (plan)", "/teams/4?tab=plan", "teams_4_tab_plan", "/investigate/4?tab=plan", "investigate_4_tab_plan"),
         ("Action plans", "/plans", "plans", "/plans", "plans"),
         ("Review", "/impact/plan-richmond-night-a", "impact_plan-richmond-night-a", "/review/plan-richmond-night-a", "review_plan-richmond-night-a"),
         ("Ask / investigation panel", "/ask", "ask", "/ask", "ask"),
         ("Insights", "/insights", "insights", "/insights", "insights"),
         ("Data sources", "/data", "data", "/data", "data"),
         ("Business case", "/value", "value", "/value", "value"),
         ("Trust & method", "/trust", "trust", "/trust", "trust")]
DEMO = []
NEW_ONLY = []


def main() -> None:
    rows, missing = [], 0
    for title, vr, vs, nr, ns in PAIRS:
        for w in (1440, 390):
            for d, dl in (("09-15", "Sept 15"), ("11-30", "Nov 30")):
                b, a = f"screens/before/{w}_{d}_{vs}.jpg", f"screens/after/{w}_{d}_{ns}.jpg"
                ok = os.path.exists(b) and os.path.exists(a)
                missing += not ok
                rows.append(f'<section class="pair" data-w="{w}"><h2>{html.escape(title)} <span>{w}px · as of {dl}</span></h2><div class="cols">'
                            f'<figure><figcaption>Before · v0.7 <code>{html.escape(vr)}</code></figcaption><a href="{b}"><img loading="lazy" src="{b}" alt="before {title} {w} {dl}"></a></figure>'
                            f'<figure><figcaption>After · v0.8 <code>{html.escape(nr)}</code></figcaption><a href="{a}"><img loading="lazy" src="{a}" alt="after {title} {w} {dl}"></a></figure></div>'
                            f'{"" if ok else "<p class=miss>missing screenshot</p>"}</section>')
    demo = "".join(f'<figure><figcaption>{c}</figcaption><a href="screens/after/{f}"><img loading="lazy" src="screens/after/{f}" alt="{c}"></a></figure>' for f, c in DEMO)
    extra = "".join(f'<figure><figcaption>{t} (new in v0.7)</figcaption><a href="screens/after/1440_09-15_{s}.jpg"><img loading="lazy" src="screens/after/1440_09-15_{s}.jpg" alt="{t}"></a></figure>' for t, s in NEW_ONLY)
    doc = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Before and after</title>
<style>
:root{{--bg:#F5F6F8;--fg:#101828;--mute:#525E70;--line:#E4E7EC;--card:#fff;--teal:#0B6E65}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--bg:#0B1B2B;--fg:#E6EDF3;--mute:#A8B3C1;--line:#1E3348;--card:#13283D;--teal:#12A594}}}}
:root[data-theme="dark"]{{--bg:#0B1B2B;--fg:#E6EDF3;--mute:#A8B3C1;--line:#1E3348;--card:#13283D;--teal:#12A594}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--fg);font:14px/1.45 system-ui,-apple-system,Segoe UI,sans-serif}}
header{{position:sticky;top:0;background:var(--bg);border-bottom:1px solid var(--line);padding:14px 16px;z-index:2;display:flex;gap:10px;align-items:center;flex-wrap:wrap}}
h1{{font-size:18px;margin:0}} header p{{margin:0;color:var(--mute);flex:1 1 300px}}
button{{font:inherit;border:1px solid var(--line);background:var(--card);color:var(--fg);border-radius:8px;padding:6px 10px;cursor:pointer}} button[aria-pressed=true]{{border-color:var(--teal);color:var(--teal)}}
main{{max-width:1500px;margin:0 auto;padding:16px}} .pair{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px;margin:0 0 16px}}
h2{{font-size:15px;margin:0 0 10px}} h2 span{{color:var(--mute);font-weight:400}} .cols{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}
figure{{margin:0;min-width:0}} figcaption{{font-size:12px;color:var(--mute);margin-bottom:6px}} img{{width:100%;height:auto;border:1px solid var(--line);border-radius:8px;display:block}}
.pair[data-w="390"] img{{max-width:390px}} .grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:12px}} .miss{{color:#D92D20}}
@media (max-width:700px){{.cols{{grid-template-columns:1fr}}}}
</style></head><body>
<header><h1>Friction Finder · before (v0.7) and after (v0.8)</h1><p>Headless Chrome, full-page, 1440 px and 390 px, both demo-clock dates. Click any image for full size.</p>
<button data-f="all" aria-pressed="true">All</button><button data-f="1440" aria-pressed="false">1440 px</button><button data-f="390" aria-pressed="false">390 px</button></header>
<main>{"".join(rows)}</main>
<script>document.querySelectorAll('header button').forEach(b=>b.onclick=()=>{{document.querySelectorAll('header button').forEach(x=>x.setAttribute('aria-pressed',x===b));document.querySelectorAll('.pair[data-w]').forEach(p=>p.style.display=(b.dataset.f==='all'||p.dataset.w===b.dataset.f)?'':'none')}})</script>
</body></html>'''
    open("before_after.html", "w").write(doc)
    print(f"pairs {len(rows)}, missing {missing}")


if __name__ == "__main__":
    main()
