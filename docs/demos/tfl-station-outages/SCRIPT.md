# Demo script

A video of 2 to 3 minutes, cut from one real Claude Code session that takes
about 30 to 45 minutes. The waits are sped up and the speed is shown on
screen. There's no voice-over: captions carry the story, so the video works
muted on the forum.

**Rule for the edit:** everything shown happened in the recorded session, in
that order. Cut and speed up, but never re-stage or re-type anything.

## Shot list

| Time | On screen | Caption | Edit |
|---|---|---|---|
| 0:00–0:08 | **Cold open.** The finished, hosted app: outages ranked by impact, with Pimlico's "no down escalator" near the top. | "A Foundry app for Tube lift and escalator outages. Built by Claude Code from the terminal, from one prompt." | Real speed. A slow zoom on the top rows. |
| 0:08–0:20 | The prompt pasted into a fresh Claude Code session. | "The input: a business problem and three links to TfL open data." | Hold long enough to read the first paragraph, then scroll. |
| 0:20–0:40 | **Act 1, data in.** The agent `curl`s the three sources, then runs `pltr dataset create`, `pltr dataset files upload` and `pltr dataset schema apply`, then `pltr context dataset` on the footfall data. | "It fetches public TfL data and lands it in Foundry with pltr. No RIDs looked up by hand: pltr takes Compass paths." | 4x to 8x. Freeze on the `context dataset` output, showing columns and sample rows. |
| 0:40–1:10 | **Act 2, pipeline.** The agent writes the transform (show the join and the impact score), then `git push`, `pltr resource wait`, `pltr orchestration builds create --dataset ... --wait` and `pltr assert dataset ...` passing. | "It writes the pipeline, pushes it, builds it and checks the output. All from the terminal." Then, on the wait: "Waiting for Foundry's checks (sped up 20x)." | Skim the code at 8x. The wait at 20x or more. Hold one second on the passing assert. |
| 1:10–1:30 | **The UI step.** The agent stops and prints the spec for `StationOutage` and `assign-engineer`. Cut to Ontology Manager creating them, and to Developer Console adding them to the application. | "The one step pltr can't do: the Platform API can't create object types. The agent says exactly what to make." | Agent output at real speed for two seconds, then the UI at 8x. |
| 1:30–1:40 | `pltr context ontology --types StationOutage` and `pltr assert objects` passing. | "It checks the objects are there before writing any app code." | 4x. |
| 1:40–2:10 | **Act 3, the app.** `pltr osdk generate` prints the package. Skim the React code being written, then `npm run typecheck` passing and `pltr ontology action-validate` returning VALID. In the browser, sign in, see the ranked list and assign an engineer to the top outage. Back in the terminal, `pltr ontology object-get` shows the assignee. | "An OSDK package from the pltr profile, with no Developer Console download." Then: "Validate first. Then a person makes the change, and the agent checks it landed." | Code at 8x. The browser at real speed: it's the payoff. |
| 2:10–2:30 | **Act 4, ship.** The agent asks before deploying, and the person answers yes. Then `npm run build`, `pltr site deploy ... --yes` printing the URL, `curl` giving 200, and the hosted app opening. | "Deploys ask first. One command hosts it on Foundry." | 4x on the build. The deploy output and the opening of the app at real speed. |
| 2:30–2:45 | **End card.** The run's numbers: time, turns, tokens and pltr commands. `uv tool install pltr-cli`, then the repo link. "Powered by TfL Open Data." | "Outages are a snapshot from the recording." | Static. |

## Captions: rules

- One line each, readable in about two seconds.
- State what happened, without adjectives. Don't say "magic" or
  "seamless".
- Mention the honest limits where they happen (the UI step, the snapshot),
  not at the end.

## During the recording

- Don't type anything into Claude Code except the prompt and the answers to
  its questions. Each question and answer goes in the walkthrough.
- When the agent asks for the UI step, follow its spec exactly. If the spec
  is wrong or missing something, that's a finding: note it, and fix it in
  the UI the way you would if this weren't a demo.
- When it asks before applying an action or deploying, read the command it
  shows, then answer yes.
- In the notes file, write down the clock time at the start of each act, so
  the edit can find it.
- At the end, run `/cost` (or read the session stats) for turns, tokens and
  time.

## If something goes wrong

| What happens | What to do |
|---|---|
| The agent picks a different design than the plan's. | Let it, as long as it solves the problem. The plan's design is a guess, not the script. |
| A step fails and the agent recovers on its own. | Keep it in: a short "it hit X and fixed it" beat is good. |
| A step fails and the agent can't recover without help. | Help it the way you would a colleague, and keep that in the video too. Note it for the walkthrough's "what didn't work" section. |
| A pltr bug blocks the run. | Stop. File the issue, fix it, release, and record again. Don't record with an unreleased build. |
| TfL data changes between the rehearsal and the recording. | Fine: the cold open uses whatever the recorded run produced. |

## After recording

- Blur the hostname, RIDs, OAuth client ID and subdomain everywhere they
  appear, including the browser's address bar.
- Export at 1080p, under 100 MB, for the forum.
- Write `README.md` (the walkthrough) from the transcript, and
  commit the agent's transform and app code here, without `.env` files.
