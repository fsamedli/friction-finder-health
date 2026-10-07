# Gallup Access overlap check for Friction Finder (Oct 8, 2026)

Status: final, 03:45 (Oct 8, 2026).

Research subagent, public sources only. Every URL was accessed on Oct 8, 2026. "Not found publicly"
never means "absent". Gallup and vendor wording is paraphrased; open the URL for exact text (one short
quote is kept where the exact words carry the claim). Sponsor statements from Sept 18 are testimony from
that date, not proof of where the product's boundaries are today.

Evidence labels: **documented** = a Gallup Help Center how-to or product-update article describes the
feature; **marketing claim** = only a gallup.com product page says it; **unverified** = not confirmed by a
page read today; **no** = no public evidence found (absence of evidence only).

Help Center URLs below are shortened to `HC/<article id>`, meaning
`https://support.gallup.com/hc/en-us/articles/<article id>`.

## (a) Overlap table

| # | Capability | Access has it | Source (accessed Oct 8, 2026) | Friction Finder |
|---|---|---|---|---|
| 1 | Survey design and delivery (Q12, pulse, life-cycle, 350+ items, 55+ languages) | marketing claim | gallup.com/access/home.aspx; gallup.com/access/239201/employee-surveys.aspx | drop |
| 2 | Team results at item level: mean, top box, respondents, highest and lowest items, engagement index (engaged % needs 30+ responses) | documented | HC/48486590302227 (Questions Tab); HC/48485168113043 (Overview Tab) | bridge: import the export; show only the items tied to the flag |
| 3 | Heat map across teams and reporting groups (up to 100 teams, 5 reporting groups, direct or rollup), colored by benchmark quartile | documented | HC/48556128097811 (Heatmap Tab) | drop |
| 4 | Database benchmarks and percentile ranks: a primary comparison database plus up to four more; default is the Gallup Overall database; color bands at the 25th, 50th, 75th and 90th percentiles; database mean at a chosen percentile | documented | HC/48966732424211 (Database Comparisons); HC/48556100947603 (Customize Metrics) | bridge: read the client's percentile ranks from the export, or label any external norm as an assumption; never compute a Gallup benchmark |
| 5 | Trends: last mean, change, trended mean over up to four prior administrations, recast values | documented | HC/48556100947603; HC/48485168113043 | bridge |
| 6 | Gallup's rule for a meaningful change in an item mean (about 0.2 for surveys under 1,000 respondents, 0.1 for larger) | documented | HC/48556100947603 | bridge: the signal check should use and cite this rule for item changes, then add our response-mix test on top |
| 7 | Small-n suppression: no item or group report under 4 responses by default; admins can raise it; higher thresholds for advanced metrics | documented | HC/40875599055507 | bridge: apply the same default of 4 to every joined view |
| 8 | Comment analytics: sentiment (50+ comments), topics (250+), Gen AI comment summaries, translation, PII and toxicity flagging, comment CSV download | documented | HC/48556138134163 (Text Analytics Tab); HC/51743781735699 (AI, ML and Gen AI) | bridge: cite specific comments as evidence; do not build a sentiment or topic engine |
| 9 | AI insights and next steps on a team's engagement results: Survey Reporting Insights, Survey Reporting Next Steps, Key Insights (summary, strengths, opportunities, prioritized recommendations; web, and mobile from Sept 4, 2026), Item Next Steps | documented | HC/51743781735699; HC/55108815356819; HC/48486590302227 | drop: no recommendations computed from engagement alone |
| 10 | Gallup AI chat: RAG over Gallup research, aware of the user's CliftonStrengths, explains engagement results, recommends Gallup learning content | documented | HC/48408264183827; HC/51743728239123; gallup.com/access/697103/gallup-ai.aspx | drop: no generic coaching chat |
| 11 | Gallup AI "Q12 Action Planning" guided prompt: short discovery flow, then goals, next steps, coaching ideas, success indicators and follow-up actions | documented (article updated May 15, 2026) | HC/51743728239123 | bridge: do not compete on plan drafting; Friction Finder's plan differs only by a measured operating metric checked at the review date |
| 12 | Gallup AI uses the client's own data | Help Center: no. It says Gallup AI answers without using or training on client-specific data, and that Gen AI is "augmented exclusively with Gallup-owned content". Marketing page says managers can ask about their survey data. | HC/51743728239123; HC/51743781735699; gallup.com/access/239201 | conflict: whether the guided prompt pulls a team's results or the manager types them in is unverified (section d, question 1) |
| 13 | Action plan form: plan type, up to 3 related survey items, topics, goal (what success looks like, free text), description (owners and deadlines suggested in free text), due date, tasks, resources; quick plan from a report item | documented | HC/48615058500499; HC/48556179640851; HC/40874249418515 | bridge: keep the thinnest plan (owner, action, operating measure, review date, success criterion) and export it in fields that map to Access |
| 14 | Plan states and follow-through: Draft, Active, Complete, Overdue; days active; history and notes; transfer; PDF and list export | documented | HC/48614936020627 (Plans Tab) | bridge: status and review date only |
| 15 | Monitoring across teams: Compare Teams (plan counts, items and topics for up to 10 teams), Team Monitoring, Escalated Issues (team-raised issues with category, active or resolved, export) | documented | HC/48615135855251; HC/48615102423571 | drop; Escalated Issues is the natural hand-off for obstacles outside the manager's control |
| 16 | Learning content: item learning modules, plan topics, microlearning | documented (item modules); marketing claim (microlearning) | HC/48486590302227; gallup.com/access/home.aspx | drop (link out) |
| 17 | State of the Team conversation method | documented only by a Help Center search snippet (reporting-groups article) and by Gallup outlines reposted on university sites (2015 to 2021); not read on gallup.com today | support.gallup.com search "state of the team"; engage.unm.edu outline (search snippet only) | drop as content; bridge as a hand-off |
| 18 | Exports: Advanced Data Tool to Excel or CSV with heat-map colors; comment CSV; plan PDF and plan list | documented | HC/48893741653907; HC/48556138134163; HC/48614936020627 | bridge: these exports are Friction Finder's input |
| 19 | HRIS sync and team hierarchy (teams editable by CSV) | marketing claim (HRIS); documented by article titles only (team CSV) | gallup.com/access/home.aspx; Help Center search listing | bridge: a team-to-site mapping table |
| 20 | Mobile app: reports, Key Insights, action planning | documented | HC/51743278176915; HC/55108815356819 | drop |
| 21 | Takes in client operating data (late departures, absence, quits, injuries, rework) | no public evidence | No Access page or Help Center article read today mentions it. Sponsor meeting, Sept 18: "What we don't have is all of those comparisons to their business operations." | new |
| 22 | Links a client's engagement to that client's own outcomes (Business Impact Analysis) | not in Access, per sponsor testimony; not found publicly under that name | Sponsor meeting, Sept 18, on BIA: "it's like a presentation. It's not something that they see in Gallup Access." Public method only: the Q12 meta-analysis relates work-unit engagement to outcomes the organizations supplied (gallup.com/workplace/321725/q12-meta-analysis-report.aspx); the Q12 page says Gallup helps clients connect engagement to outcomes like productivity (gallup.com/q12/, marketing claim) | extend: site level, team-month, associations only |
| 23 | Flags a team whose operating KPI runs above comparable teams while its engagement fell | no | none found | new |
| 24 | Bounded investigation over client data with SQL provenance ("could staffing explain this?") | no | Gallup AI grounding is Gallup-owned content (HC/51743781735699) | new |
| 25 | Retrieval with citations over the client's own process documents | no | same | new |
| 26 | Checks an operating metric at a review date against comparable teams | no | Access records plan status, days active and completion (HC/48614936020627); Gallup's action-planning claim is measured in engagement growth (gallup.com/access/239231/action-planning.aspx) | new |
| 27 | AI governance: Gen AI outputs traceable to Gallup content; evaluated against NIST AI RMF and OWASP Top 10 for LLM applications; PII removed before AI processing | documented | HC/51743781735699; HC/51743728239123 | bridge: use the same frameworks in our TEVV section; it is shared language with the sponsor |

Side note from row 27's source: the Help Center says Gallup evaluates and configures Anthropic Claude
model variants for its AI. This does not change our build rule (the prototype runs on the GW-approved
OpenAI API), but a judge may ask about model choice.

### Competitor check (question 6) against the Sept 23 table

| Vendor | Manager-facing AI today (public) | Reads site operating data? | Checks an operating metric at a review date? | Sept 23 claim: confirm or correct |
|---|---|---|---|---|
| Culture Amp | AI Coach in Engage: themes across survey questions, drafts action plans and communications; draws on engagement surveys, performance reviews and other people data on the platform (cultureamp.com/platform/ai-coach) | not found publicly | not found publicly | Confirmed. The scope of "other people data" is unverified. |
| Microsoft Viva Glint | Copilot Highlights (scores, trends, team differences, benchmark comparisons) and comment summarization. Microsoft states Copilot does not reach data outside the Glint dashboard (learn.microsoft.com/en-us/viva/glint/setup/copilot-managers, updated Aug 18, 2026) | no, per Microsoft docs | not found publicly | Confirmed. Correction: it summarizes; it is not a coach. Action happens in a team conversation. |
| Perceptyx | Activate: an AI action plan per leader from listening data, nudges (Teams, Slack, email, frontline mobile tools), a coaching agent; tracks nudge engagement, plan follow-through and later survey item movement; claims a closed-loop ROI without stating a method (go.perceptyx.com/platform/activate) | not found publicly | no: survey re-measure and completion | Confirmed. |
| Qualtrics | Qualtrics Assist for EX (release Oct 30, 2024): Q&A on team data, suggested actions, comment summaries (qualtrics.com news release) | not in the release | not found publicly | Confirmed for the product. "Qualtrics through EY consulting" was not re-checked today: unverified. |
| Workday Peakon | Gen AI themes and summaries, action plans and training for leaders (workday.com employee-voice overview) | not on the page | not found publicly | Confirmed. "Workday Prism" was not re-checked today: unverified. |
| Visier | Viva Glint connector: pulls raw survey responses into Visier's workforce data model; the release says this connects sentiment with performance, productivity and retention; aimed at HR leaders (docs.visier.com connector page labels it beta; techrseries.com repost dated Sept 3, 2026) | people and workforce data; site operating logs unverified | no; analyst-facing | Correct the date to "early Sept 2026 (Sept 2 to 4 across sources)" and add "beta, HR and analyst-facing". |

**Answer to question 6:** none of the manager-facing tools checked today documents reading site operating
data or checking an operating metric at a review date. Visier is closest on the data join, but it is an
HR analytics tool, not a manager workflow. This is absence of evidence; confirm in a vendor demo before
saying it on stage. One Model, Medallia, UKG, WorkJam and Beekeeper were not re-checked today.

### Corrections to the Sept 23 note (My Notes/2026-09-23_Product_Edge_Research.md)

1. The "Q12 Action Planning guided prompt" is no longer unverified: it is documented (HC/51743728239123) and its outputs include success indicators and follow-up actions. AI plan drafting is Gallup's ground, more firmly than the Sept 23 note said.
2. Gallup AI and client data: the Help Center says Gallup AI does not use client-specific data at all, which goes further than the Sept 23 line about operating data. The marketing page implies the reverse for survey data. Treat this as an open question, not a fact.
3. Section 1 of the Sept 23 note omits Access's report-level AI: Key Insights, Survey Reporting Insights and Next Steps, Gen AI comment summaries, and PII and toxicity flagging (HC/51743781735699).
4. Access already documents a meaningful-change rule for item means (row 6) and an n-of-4 suppression default (row 7). The signal check should cite both instead of presenting them as our invention.
5. Glint Copilot quote confirmed (page updated Aug 18, 2026). Visier date and beta status corrected above.

## (b) Do-not-build list

1. Survey design, distribution and response tracking.
2. Item-level team dashboards, overview pages, engagement index splits.
3. Heat maps across teams or reporting groups, percentile color bands.
4. Our own Gallup benchmarks or percentile ranks. We do not have the database; read the export or label the assumption.
5. Comment sentiment, topic modeling, comment summaries, translation, PII redaction for survey comments.
6. Generic AI coaching or research Q&A chat; strengths content.
7. AI key insights or next steps computed from engagement results alone, and a general AI action-plan generator (Gallup's guided prompt already does this).
8. A plan-management system: task lists, transfer, plan states beyond what the review needs, cross-team plan monitoring, issue escalation.
9. Learning modules, item content, State of the Team discussion guides. No Q12 item wording anywhere.
10. Mobile app, HRIS sync, team hierarchy management.

## (c) What Gallup could use this for, risks, opportunities, frame

**What Gallup could use it for.** Gallup's public research method relates work-unit engagement to
performance outcomes that client organizations supply (Q12 meta-analysis,
gallup.com/workplace/321725/q12-meta-analysis-report.aspx), and its Q12 page markets helping clients connect
engagement to outcomes like productivity (gallup.com/q12/, marketing claim). Yet no Access page or Help Center
article read today documents taking in client operating data, and the Help Center says Gallup AI is grounded
in Gallup-owned content and does not use client-specific data (HC/51743728239123, HC/51743781735699). The
sponsor named the same gap on Sept 18 ("What we don't have is all of those comparisons to their business
operations.") and described Business Impact Analysis as a presentation outside Access. Friction Finder could
therefore show Gallup what that linkage looks like done monthly, per site, in a manager's hands: it would
sit downstream of Access exports, respect Access's own suppression and change rules, and hand an approved
plan back in Access-compatible fields. Whether Gallup wants that, or sees it as cannibalizing Business Impact
Analysis, is unknown (section d, question 2).

**Three overlap risks**
1. **Gallup AI scope.** Gallup's marketing already says managers can ask about their survey data (gallup.com/access/239201), and the guided prompt tailors plans to a team. If Gallup lets its AI read client data, our bounded investigation looks like a feature Gallup is about to ship.
2. **Action planning.** Access documents AI next steps, Key Insights recommendations, an AI action-planning prompt that writes success indicators, a plan form with a success goal and due date, an Overdue state and cross-team monitoring (rows 9, 11, 13 to 15). If the demo spends time on plan drafting, judges see a clone. The operating measure and the review-date check have to be the visible difference.
3. **Impersonating Gallup or BIA.** A team-level engagement-to-operations link sits close to what the sponsor described as a Gallup consulting deliverable. The class warned about this ("I would be concerned if your story was too sprawling, or you're kind of impersonating Gallup."; class session, Oct 8, 2026, speaker unconfirmed).

**Three opportunities, each with counter-evidence**
1. **Operating data at site level, monthly (rows 21 to 23).** Counter: Visier's Glint connector (beta, early Sept 2026) already joins survey responses with workforce data, and Qualtrics says its platform predicts business outcomes (Oct 30, 2024 release), so the gap may be narrow and closing. Client friction is real too: operations, not HR, owns the logs.
2. **Review-date check on the operating metric (row 26).** Counter: with about two dozen teams, difference-in-differences is noisy and only directional. Perceptyx already claims a closed loop (method undefined). Gallup's own action-planning evidence is measured in engagement, not operations, so Gallup may not value an operations scorecard, and the sponsor raised trust concerns about tying scores to pay (team notes, Sept 23).
3. **Fit into Access's loop (rows 6, 7, 13, 18).** Same n-of-4 default, same change rule, plan fields that map to Access, Access exports as input. Counter: the Help Center documents export paths only; no public import or API for plans was found, so the hand-back may be manual. Gallup also already runs its own AI under NIST AI RMF and OWASP and could build this in-house.

**Frame: a startup's product sold to the client.** The class offered two frames ("we're consultants,
here's the solution that we're presenting; or we're a startup, here's the product that we're trying to sell
to you"; class session, Oct 8, 2026, speaker unconfirmed). The consultant frame puts us directly on top of
Business Impact Analysis, which the sponsor described as a presentation, and it weakens the revenue model
Jamshidi asked for. The product frame matches the existing go-to-market hypothesis (customer = a Gallup client
with operations-heavy work, user = site manager, buyer = HR or people analytics) and keeps Gallup as sponsor
and data source, not something we imitate ("You don't want to be Gallup."; class session, Oct 8, 2026). The
counter-argument partly holds: a product invites "why won't Gallup, Visier or UKG build this?" Answer it
with the complement position: it reads Access exports and never re-displays them.

**UI voice.** The app talks to the site manager like a product would, in operations language about their own
site ("Night shift B: late departures above comparable teams since July"). Each screen states its limits
("directional, not causal", n shown) and never uses Gallup branding, layouts, engagement-report headlines or
Q12 item wording.

## (d) Five questions only Gallup can answer (Nov 4 to 17 judge window)

1. Does the Q12 Action Planning guided prompt or Key Insights read a team's actual results, or does the manager type them in? Is client-supplied operating data on the roadmap? (Public pages conflict: row 12.)
2. How is Business Impact Analysis delivered: at what level (company, quartile, team), how often, to whom? Would a monthly site-level version feed it or cannibalize it?
3. Can an approved plan get back into Access by import or API, or is export the only route? Which export would a client's HR team realistically hand over (item-level team results with n, percentile ranks)?
4. Which comparison databases (industry, frontline or hourly roles) can a client choose as primary? May a client-side tool show the client's own percentile ranks taken from an export?
5. For operations-heavy clients, do Gallup advisers already join engagement with safety, absence or turnover by team-month? What minimum n would Gallup require on a joined view (the Access default is 4)?

## (e) Fetch log (all Oct 8, 2026)

| URL | Result | Method |
|---|---|---|
| https://www.gallup.com/access/home.aspx | fetched | WebFetch |
| https://www.gallup.com/access/697103/gallup-ai.aspx | fetched | WebFetch |
| https://www.gallup.com/access/239201/employee-surveys.aspx | fetched (twice) | WebFetch |
| https://support.gallup.com/hc/en-us/articles/48408264183827-Gallup-AI | 403 to WebFetch; fetched in browser | WebFetch, Chrome |
| https://support.gallup.com/hc/en-us/articles/51743781735699-AI-ML-and-Gen-AI-on-Gallup-Access | first browser attempt showed the previous page; fetched on the second (short URL) | Chrome |
| https://support.gallup.com/hc/en-us/articles/40874249418515-How-do-I-create-an-Action-Plan | fetched | Chrome |
| https://support.gallup.com/hc/en-us/sections/40530502112275-Action-planning-and-follow-up | fetched | Chrome |
| HC/48556128097811 (Heatmap Tab) | fetched | Chrome |
| support.gallup.com search pages: "state of the team", "action plan overdue", "guided prompt", "key insights" | fetched (result lists) | Chrome |
| support.gallup.com Help Center search API (/api/v2/help_center/articles/search.json) | fetched (titles only); the /en-us/ path variant returned 404; two later calls timed out | Chrome |
| HC/48966732424211 (Database Comparisons) | fetched | Chrome |
| HC/48485168113043 (Overview Tab) | fetched | Chrome |
| HC/51743278176915 (Survey Reporting, mobile) | fetched | Chrome |
| HC/48615058500499 (Creating an Action Plan) | fetched | Chrome |
| HC/48614936020627 (Plans Tab) | fetched | Chrome |
| HC/48556179640851 (Action Planning in reports) | fetched | Chrome |
| HC/48486590302227 (Questions Tab) | fetched | Chrome |
| HC/55108815356819 (Key Insights on mobile, Sept 4, 2026) | fetched | Chrome |
| HC/48615135855251 (Compare Teams Tab) | fetched | Chrome |
| HC/48556138134163 (Text Analytics Tab) | fetched | Chrome |
| HC/40875599055507 (suppression rules) | fetched | Chrome |
| HC/48893741653907 (Exporting Data) | fetched | Chrome |
| HC/48816350536467 (Cascade) | fetched | Chrome |
| HC/42425757202323 (subscriptions) | fetched | Chrome |
| HC/48556100947603 (Customize Metrics) | first attempt timed out (extension unresponsive); fetched on second | Chrome |
| HC/51743728239123-Gallup-AI (Gallup AI, Access tutorials) | first attempt showed the previous page; fetched on second | Chrome |
| HC/48615102423571 (Escalated Issues Tab) | fetched | Chrome |
| https://www.gallup.com/access/239198/survey-reporting.aspx | fetched | WebFetch |
| https://www.gallup.com/access/239231/action-planning.aspx | first attempt failed mid-response; fetched on second | WebFetch |
| https://www.gallup.com/q12/ | fetched | WebFetch |
| https://www.gallup.com/workplace/229424/employee-engagement.aspx | fetched | WebFetch |
| https://www.gallup.com/workplace/321725/q12-meta-analysis-report.aspx | fetched (first 100k of 128k characters) | WebFetch |
| https://www.gallup.com/workplace/467504/ | 404 | WebFetch |
| https://www.gallup.com/workplace/467504/administered-employee-engagement-survey.aspx | fetched | WebFetch |
| https://www.gallup.com/workplace/238001/employee-survey-results.aspx | fetched (serves the Aug 10, 2006 article) | WebFetch |
| https://www.gallup.com/workplace/287270/ways-help-managers-handle-heavy-workloads.aspx | fetched | WebFetch |
| https://www.gallup.com/workplace/349484/state-of-the-global-workplace.aspx | fetched | WebFetch |
| https://learn.microsoft.com/en-us/viva/glint/setup/copilot-managers | fetched | WebFetch |
| https://docs.visier.com/visier-people/Studio/data/data%20connectors/microsoft/microsoft-viva-glint-reqs.htm | fetched | WebFetch |
| https://techrseries.com/?p=185119 (Visier release repost) | fetched | WebFetch |
| https://dialoguesupport.perceptyx.com/support/solutions/articles/63000283291-ai-assisted-action-planning-intelligent-nudges-technical-overview | 404 | WebFetch |
| https://go.perceptyx.com/platform/activate | fetched | WebFetch |
| https://www.cultureamp.com/platform/ai-coach | fetched | WebFetch |
| https://www.qualtrics.com/news/new-ai-powered-qualtrics-solutions-empower-leaders-to-boost-employee-engagement-with-strategic-informed-action/ | fetched | WebFetch |
| https://www.workday.com/en-us/products/employee-voice/overview.html | fetched | WebFetch |
| Search snippets only, not read: engage.unm.edu and actx.edu State of the Team outlines; briefglance.com Visier item; secondary coverage of the 2026 State of the Global Workplace | not fetched | WebSearch |

No URL on the starting list ended blocked: the three support.gallup.com pages returned 403 to WebFetch but
opened in the browser.

## (f) Labels for the 12 candidate manager functions

1. **Why is this team flagged?** new. Access names the lowest items and gives AI next steps from engagement alone; nothing documented ranks operational hypotheses (process, staffing, response mix, seasonal, one loud comment). Rows 9, 21, 23; row 8 for the comment check.
2. **Could X explain this?** new. Gallup AI is grounded in Gallup content and does not use client data; Glint Copilot stays inside its dashboard. Neither tests a hypothesis against client operating data. Rows 10, 12, 24.
3. **Compare with comparable teams on the KPI and the items, with n.** extend. Access compares items across teams in the heat map but has no operating KPI. Keep items as secondary columns with n; the KPI comparison is ours. Rows 3, 21.
4. **Is this normal for teams like ours?** bridge. Access already gives percentile ranks against Gallup databases. Use the client's export or label an external norm as an assumption, and compute only the internal peer norm. Rows 4, 7.
5. **When did it start?** extend. Access trends items wave to wave; a monthly timeline of KPI, staffing and plan dates is new. Rows 5, 21.
6. **How widespread is it?** extend. Access slices by reporting group and rollup; hour-band, month and KPI cuts need operating data. Rows 3, 21.
7. **What is missing, and what would change the recommendation?** new. Access documents small-n suppression and issue escalation, but no list of data gaps with owners or a statement of what would flip the call. Rows 7, 15, 24.
8. **Where does this number come from?** new for client data. Gallup documents traceability to its own content; SQL-and-row provenance for client data has no Access equivalent. Rows 24, 27.
9. **Has this happened elsewhere, and what was tried?** extend. Compare Teams shows plan counts, items and topics by team, not whether the operating number moved afterwards. Rows 15, 26.
10. **Draft a plan I can review.** bridge. Access already has a plan form and an AI action-planning prompt that writes goals and success indicators. Keep the thinnest plan and add only the operating measure and the review date it will be checked on. Rows 11, 13, 14.
11. **Did it work?** new. Access records status and completion; competitors re-measure the survey or count completion. No one documents checking an operating metric at the review date. Rows 14, 26.
12. **Prepare the team conversation.** drop as specified; bridge as a hand-off. Quoting Gallup's discussion questions verbatim breaks the no-Q12-wording rule and Gallup's copyright on the outline. Give the manager the team's operating facts and point to the State of the Team guide in Access. Row 17.

## Appendix: short answers to questions 1 to 5

**Q1, what Access gives a manager.** Rows 2 to 20. On Gallup AI specifically: it reads Gallup research and
the user's CliftonStrengths profile, explains engagement results, recommends Gallup learning content, and
runs guided prompts including Q12 action planning (HC/51743728239123, HC/48408264183827). The Help Center
says it does not use client-specific data and is grounded only in Gallup content. Whether it sees a team's
actual scores automatically is unverified.

**Q2, Business Impact Analysis in Gallup's public words.** Not found publicly under that name (two targeted
searches on gallup.com). The closest public description is the meta-analysis method: work-unit level,
outcomes supplied by client organizations, top versus bottom quartile, with utility analysis
(gallup.com/workplace/321725/q12-meta-analysis-report.aspx). Level, frequency, delivery and audience for a
single client: unverified publicly. Sponsor testimony (Sept 18) describes it as a presentation outside
Access; team notes (Sept 23) record it as an extra-cost add-on.

**Q3, does Access take in client operating data, or does Gallup AI use it?** Gallup AI: no, per the Help
Center (HC/51743728239123, HC/51743781735699). Access intake of operating data: not found publicly
(unverified, not proven absent). Note that the Advanced Data Tool and bivariable reporting were seen only as
article titles, and appear to work on survey reporting groups, not outcomes; this is unverified.

**Q4, benchmarks.** Documented: each survey report has a primary comparison database for mean percentile rank
plus up to four more (HC/48966732424211); the default is the Gallup Overall database; values are colored by
quartile and 90th-percentile bands; Database Mean at a chosen percentile is available (HC/48556100947603).
Marketing claims: comparison against over a billion responses from the last five years (gallup.com/access/239201);
industry, competitor and top-quartile benchmarks (gallup.com/q12/); world-class is generally the 75th
percentile of the database (gallup.com/workplace/229424). Which industry or role databases exist: not found
publicly. The Oct 8 class session said assuming benchmark access is acceptable if stated as an assumption.

**Q5, what Gallup says managers struggle with after a survey (paraphrased).**
- Efron (Gallup, Jan 4, 2023): only 8% of employees strongly agree their organization acts on surveys; surveying without follow-up tends to lower engagement and raise turnover. gallup.com/workplace/467504/administered-employee-engagement-survey.aspx
- Earl, Lampe and Buksin (Gallup, Aug 10, 2006): employees distrust managers who ask for opinions and then do nothing; workgroups high on action planning gained about 10% in engagement while the lowest fell about 3%. gallup.com/workplace/238001/employee-survey-results.aspx
- Gallup employee engagement page (undated): a survey without a follow-up plan can do more harm than good; plan the response before sending. gallup.com/workplace/229424/employee-engagement.aspx
- O'Keefe (Gallup, Mar 5, 2020): managers are 50% more likely than individual contributors to strongly agree they have too much work. gallup.com/workplace/287270/ways-help-managers-handle-heavy-workloads.aspx
- State of the Global Workplace 2026: manager engagement fell from 27% to 22% between 2024 and 2025, nine points below 2022; global engagement was 20% in 2025. gallup.com/workplace/349484/state-of-the-global-workplace.aspx
