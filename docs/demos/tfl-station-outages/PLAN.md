# Demo plan: Tube lift and escalator outages, from a business problem to a Foundry app

Part of #203. This is the flagship demo: one end-to-end run instead of the
five feature demos (#204 to #208).

## The idea

Claude Code gets a business problem and links to TfL's open data. Without a
person looking up RIDs or clicking through Foundry, it:

1. fetches the data;
2. lands it in Foundry;
3. builds a pipeline;
4. builds an OSDK web app on the result;
5. hosts it on Foundry.

A person steps in once, to create the object type and action in Ontology
Manager. The public API can't create them, so pltr can't either.

The arc follows an AI FDE demo about escalators being down at Tube stations.
AI FDE works inside Foundry. This demo shows a coding agent working from the
outside, with only a token and pltr. Say that plainly in the post, and give
AI FDE and Palantir MCP credit for what they do that pltr can't, such as
creating ontology types.

## The business problem

At any moment, lifts and escalators across the Tube are out of service.
Broken escalators at busy stations cause crowding. Broken lifts strand
people who need step-free access. There are only so many engineers. A duty
manager needs today's outages ranked by impact, and a way to assign an
engineer and track progress.

## The data

All of it is public and small. The numbers below are from 2026-11-26. To
check them again, run `uv run docs/demos/tfl-station-outages/check_data.py`.

| Data | Source | Size | Notes |
|---|---|---|---|
| Disruptions at Tube stations | `https://api.tfl.gov.uk/StopPoint/Mode/tube/Disruption` | about 35 KB of JSON | 57 items: 15 that mention an escalator, 14 a lift and 28 neither. Free text, such as "PIMLICO STATION: ... no down escalator. Please use the stairs." Has `fromDate` and `toDate` as ISO timestamps, such as `2026-11-26T02:27:00Z`. |
| Lift outages | `https://api.tfl.gov.uk/Disruptions/Lifts/v2/` | about 7 KB of JSON | 23 items, at stations on every mode, not only the Tube. Each has a `stationUniqueId`, lift IDs and a message such as "Tower Hill: No Step Free Access - ...". |
| Daily station traffic | `https://crowding.data.tfl.gov.uk/Network%20Demand/StationFootfall_2025_2026%20.csv` | about 12 MB of CSV | `TravelDate, DayOfWeek, Station, EntryTapCount, ExitTapCount`, up to 21 Nov 2026. `TravelDate` is a number such as `20261121`, not a date. Note the space before `.csv` in the file name. |

No API key is needed. TfL's API rate-limits anonymous calls, and this demo
makes only a handful.

**The join needs care.** The disruption names (`Pimlico Underground
Station`) match the footfall names (`Pimlico`) once ` Underground Station`
is removed. That matches 54 of the 57 disruptions. The other three names
have punctuation that the footfall file drops: `King's Cross St. Pancras`
is `Kings Cross St Pancras` there. Dropping apostrophes and full stops
matches all 57. King's Cross is the busiest station in the footfall data,
so a join that misses it drops the outage that should rank first.

The lift feed is mostly redundant. Only 5 of its 23 `stationUniqueId`
values equal a disruption's `stationAtcoCode`, because it uses hub and rail
codes. But 13 of its messages appear word for word in the disruption feed,
and the other 10 are at stations off the Tube. 23 disruptions say "step
free" themselves, so the disruption text alone can set `step_free_lost`.

## What gets built

| Step | Who | Commands | Result |
|---|---|---|---|
| 1. Fetch | agent | `curl` | three files on disk |
| 2. Land | agent | `pltr dataset create`, `pltr dataset files upload`, `pltr dataset schema apply`, `pltr context dataset` | three raw datasets in `/<space>/pltr demos/station-outages/raw` |
| 3. Pipeline | agent | writes a Python transform, `git push`, `pltr resource wait`, `pltr orchestration builds create --dataset ... --wait`, `pltr assert dataset ...` | `station_outages`: one row per lift or escalator outage |
| 4. Ontology | **person**, from the agent's spec | Ontology Manager, then Developer Console | `StationOutage` object type and `assign-engineer` action |
| 5. Check | agent | `pltr context ontology --types StationOutage`, `pltr assert objects ...` | the objects exist |
| 6. App | agent, then person | `pltr osdk generate`, the React recipe, `npm run typecheck`, `pltr ontology action-validate`, `npm run dev` | the person signs in and assigns an engineer |
| 7. Verify | agent | `pltr ontology object-get` | the edit landed |
| 8. Ship | agent | `npm run build`, `pltr site deploy --auto-version package-json --yes` | the hosted URL answers 200 |

**The transform (left to the agent; this is the expected shape):**
- keep escalator and lift disruptions, sorting the free text into
  `escalator`, `lift` or `other`;
- give each outage a stable `outage_id`, for example a hash of the station,
  the description and the start date;
- add each station's average weekday entries plus exits over the last four
  weeks of footfall, matching names without apostrophes or full stops;
- set `step_free_lost` from the lift feed or the text ("No Step Free
  Access");
- compute `impact_score` from traffic, with extra weight when step-free
  access is lost;
- add empty `assignee`, `status` (default `Open`) and `note` columns, so the
  action has properties to edit.

**The object type and action (the agent writes the exact spec; this is the
expected shape):**
- `StationOutage`, with primary key `outage_id`, backed by `station_outages`;
- `assign-engineer`, which modifies a `StationOutage`. Its parameters are
  `outage`, `assignee`, `status` (one of `Open`, `Assigned`, `In progress`
  and `Fixed`) and an optional `note`.

**The app:**
- one page listing outages by `impact_score`, with station, type,
  description, footfall, a step-free flag, assignee and status;
- an Assign control on each row;
- a footer saying "Powered by TfL Open Data".

## Constraints

- **Released features only.** Use pltr 0.20.0 from PyPI, which includes
  #231 and #232. Note any gap the rehearsal finds and record with what's
  released. Fix and release before recording only if a gap blocks the demo.
- **Public data only.** Hide the hostname, the space name, the RIDs, the
  OAuth client ID and the application subdomain in the video.
- **Snapshot data.** The outages are as fetched at recording time. Say so on
  screen. Scheduled refresh is a possible follow-up.
- **No TfL branding** beyond the attribution. The app must not look like an
  official TfL product. Check TfL's open data terms for the exact
  attribution text before posting.

## Decisions made

- **No Data Connection.** A trial on 2026-11-11 created S3 and REST
  connections with pltr, and the API accepted them. But a file import from
  TfL's public bucket failed with and without egress policies, and the API
  gives no failure reason. Egress policies also need the UI, and a REST
  connection used from a transform needs the repo set up in the UI. So the
  agent fetches the data itself and uploads it. The trial resources are in
  `/<space>/pltr demos/connectivity-trial`.
- **One UI step, on camera.** The object type and action. Everything else in
  the UI is done beforehand (see [SETUP.md](SETUP.md)).
- **Captions, not voice-over** (see [SCRIPT.md](SCRIPT.md)).

## Risks to settle in the rehearsal

| Risk | Fallback |
|---|---|
| The new object type takes minutes to index, and `pltr assert objects` has no `--wait`. | The agent re-runs the assert. File an issue for `--wait` if it hurts. |
| The OAuth client can't read the new types until they're added to the Developer Console application. | Add them during the on-camera UI step (it's in the agent's spec). |
| The hosted site's domain isn't on the ingress allowlist, so the site answers 403. | It's in SETUP.md. |
| The station-name join drops the stations with apostrophes or full stops in their names, King's Cross among them. | Compare the output's row count with the escalator and lift disruptions. If rows are missing, tell the agent the count is short, as you would a colleague. |
| The agent struggles to classify the free-text disruptions. | The prompt is fine as is; let it try. If it flails, add "escalator and lift outages" to the prompt. |
| Applying the action asks for confirmation (0.20.0), and the agent doesn't show the user the command first. | SKILL.md tells it to. If it doesn't, that's a skill fix. |
| A TfL endpoint is down on the day. | Re-check the three URLs before recording. |

## Order of work

1. Write the plan, prompt, setup checklist and script (this folder).
2. The person does the setup in [SETUP.md](SETUP.md).
3. An unrecorded rehearsal in a fresh Claude Code session, using
   [PROMPT.md](PROMPT.md). Note every stumble. File pltr gaps as issues.
4. Record, following [SCRIPT.md](SCRIPT.md).
5. Write `README.md` here from the transcript: the prompt, the commands the
   agent ran, the turns, tokens and time, what didn't work and the limits it
   hit. Add the agent's app and transform code.
6. Post to the community forum's Show & Tell. Reply in
   [/t/6623](https://community.palantir.com/t/6623) with a link.
