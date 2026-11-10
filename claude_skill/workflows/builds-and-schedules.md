# Workflow: builds and schedules

Start builds, follow them, and manage the schedules that start them. Builds
and schedules are addressed by RID; `--format json` prints the API's shapes
(see SKILL.md).

## Start a build and follow it

`builds create --dataset` builds exactly the datasets you name, by RID or
Compass path (repeat it for several). For an upstream or connecting build,
give the build target as JSON in the API's shape instead; paths work in its
`targetRids`, `inputRids` and `ignoredRids` too:

```bash
# Build exactly these datasets on master, and wait for the result
pltr orchestration builds create --dataset "/My Space/My Project/sales" \
  --dataset ri.foundry.main.dataset.<id> --branch master --wait --format json

# Build a dataset and everything upstream of it
pltr orchestration builds create \
  '{"type": "upstream", "targetRids": ["/My Space/My Project/sales"], "ignoredRids": []}' \
  --branch master --format json

# Follow it: status, then its jobs
pltr orchestration builds get ri.foundry.main.build.<id> --format json
pltr orchestration builds jobs ri.foundry.main.build.<id> --format json --all
pltr orchestration jobs get ri.foundry.main.job.<id> --format json
```

Poll `builds get` until the status is final (`SUCCEEDED`, `FAILED` or
`CANCELED`); wait between calls instead of polling in a tight loop.

## Find builds

```bash
pltr orchestration builds search --status FAILED --branch master --format json
pltr orchestration builds search --started-after 2026-01-01T00:00:00Z --order-by STARTED_TIME:DESC --format json
```

`builds search` is beta. Its `--where` option takes the API's
`SearchBuildsFilter` JSON when the shortcut options aren't enough.

## Cancel a build (destructive)

```bash
pltr orchestration builds cancel ri.foundry.main.build.<id> --yes
```

Only cancel a build the user asked you to cancel.

## Schedules

```bash
pltr orchestration schedules get ri.scheduler.main.schedule.<id> --format json
pltr orchestration schedules runs ri.scheduler.main.schedule.<id> --format json
pltr orchestration schedules run ri.scheduler.main.schedule.<id> --format json     # run it now
pltr orchestration schedules pause ri.scheduler.main.schedule.<id>
pltr orchestration schedules unpause ri.scheduler.main.schedule.<id>
```

`schedules replace` and `schedules delete` are destructive: they ask first,
and need `--yes` without a terminal. Show the user the schedule
(`schedules get`) before you replace or delete it.

## Dataset-level views

```bash
pltr dataset jobs list ri.foundry.main.dataset.<id> --format json
pltr dataset schedules list ri.foundry.main.dataset.<id> --format json
pltr api datasets dataset get-schedules ri.foundry.main.dataset.<id> --format json
```
