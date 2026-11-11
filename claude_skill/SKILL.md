---
name: pltr-cli
description: Work with Palantir Foundry through the pltr CLI, which covers every Foundry Platform API endpoint. Datasets and files, SQL, ontologies and objects, actions, builds and schedules, folders, projects, spaces, permissions and markings, users and groups, models, streams, media sets, AIP agents and more. Use it when the user mentions Foundry, pltr, a Foundry RID (ri.*), datasets, ontology objects, builds or schedules.
---

# pltr: Palantir Foundry from the command line

pltr wraps the official Foundry Platform SDK (`foundry-platform-sdk`). It has
two kinds of commands:

- **Curated commands** (`pltr dataset`, `pltr sql`, `pltr ontology`,
  `pltr orchestration`, `pltr folder`, `pltr admin`, ...) are the polished
  path for common tasks, with friendly arguments and tables.
- **Generated commands** (`pltr api <namespace> <resource> <method>`) mirror
  the SDK one to one: one command per SDK method (390). Use them for
  anything the curated commands don't cover, or when you want the API's
  exact request and response shapes.

This skill needs a pltr release that has `pltr commands`. Check with
`pltr commands --help`; older releases lack the JSON contract described here.

## 1. Find the command; don't guess

pltr has more than 600 commands, so don't guess names or flags:

```bash
pltr commands search list dataset branches        # ranked, best first
pltr commands search Dataset.Branch.list          # by SDK method
pltr commands show dataset branches list --format json
pltr commands list api datasets                   # everything under a path
```

`search` matches names, descriptions and SDK methods, and ranks curated
commands above generated ones that match as well. `show` prints one command's
manifest entry:

- `usage`, `arguments` and `options` (flags, type, required, choices, default;
  `acceptsPath: true` when it takes a Compass path as well as a RID);
- `beta`, `destructive` and `paged`;
- `outputFormats` (`binary` means raw bytes);
- `sdkMethods` (the SDK method it calls, relative to `FoundryClient`);
- `generated` (a `pltr api` command) and `local` (makes no Foundry call).

An entry without `beta`/`destructive` hasn't recorded its metadata yet;
read its `--help` before running it. `pltr commands list --format json`
prints the whole manifest.

The `reference/` folder holds the same information as Markdown, one file per
command group, generated from the manifest. Start at
[reference/index.md](reference/index.md) and load only the file you need.

## 2. Authenticate (headless works)

pltr uses the first of these that applies:

1. `--profile NAME` on the command line;
2. the `PLTR_PROFILE` environment variable (a profile name);
3. the default profile, set up with `pltr configure configure`;
4. environment variables, when no profile is selected:
   - `FOUNDRY_HOST` and `FOUNDRY_TOKEN`, or
   - `FOUNDRY_HOST`, `FOUNDRY_CLIENT_ID` and `FOUNDRY_CLIENT_SECRET`
     (OAuth2 client credentials).

With environment variables nothing needs to be set up: no configuration
file and no keyring. A stored profile always wins over the variables.
Check what pltr will use with:

```bash
pltr verify --format json
```

Never print, log or echo tokens or client secrets.

## 3. Run with JSON and read the result

Pass `--format json`, or set `PLTR_FORMAT=json` once for the session.

- **stdout carries exactly one JSON document**: the SDK's own serialization,
  with Foundry API field names (camelCase) and no null fields. Single objects
  print as themselves. Lists use the API's paged shape,
  `{"data": [...], "nextPageToken": "..."}`. A command with no result (a
  delete, a grant) prints `null`.
- **Paged commands print one page.** Pass `nextPageToken` back with
  `--page-token`, or use `--max-pages N` or `--all`.
- **stderr carries JSON Lines only**: warnings look like
  `{"type": "warning", "message": "..."}`. On failure the last stderr line is
  the error object:
  `{"type": "not_found", "message": "...", "exitCode": 5, "statusCode": 404, "errorName": "...", "parameters": {...}}`.
- **Binary commands** (file content, Arrow or Parquet results, images)
  write raw bytes to `--output FILE` or to a pipe, never to a terminal.

| Exit | Meaning | What to do |
|---|---|---|
| 0 | success | |
| 1 | unexpected error, or "no" at a prompt | read the message; `PLTR_DEBUG=1` shows a traceback |
| 2 | usage error, or `--yes` required; `wrong_resource_type`: a path to the wrong kind of resource; `missing_dependency`: Node.js or npm is missing or too old (`pltr osdk generate`) | fix the arguments (`pltr commands show ...`); for `missing_dependency`, tell the user what to install (see `hint`) |
| 3 | authentication | check credentials with `pltr verify` |
| 4 | permission denied (403) | the account lacks access; tell the user |
| 5 | not found (404); `path_not_found`: nothing at a path you gave | check the RID or path and that the account can see it |
| 6 | the API rejected the request (400, 422) | fix the input; see `errorName` and `parameters` |
| 7 | other API or network error (409, 429, 5xx, timeouts), or `invalid_response`: the API's response doesn't match the SDK's model or isn't JSON | retry later, or report it; for `invalid_response`, upgrade pltr: a retry won't help |
| 8 | the work failed (`work_failed`: a build, query or import you waited for, or `pltr osdk generate`'s generator) or a `pltr assert` check failed (`assertion_failed`) | read `parameters` (failed jobs, the generator's `errors`) or the assert result on stdout |
| 9 | `--wait` timed out (`wait_timeout`); the work keeps running. Or `resource wait` timed out: still nothing at the path | run `suggestedCommand` to wait again |

### Errors that say how to recover

When pltr knows how to recover, the error object has a `hint` and often a
`suggestedCommand`. Read them before retrying, and don't retry blindly:

- `ObjectTypeNotFound`, `PropertiesNotFound`, `ActionTypeNotFound`,
  `LinkTypeNotFound`: the hint lists the closest API names;
- `wrong_resource_type`: you passed a RID or path of the wrong kind; for a
  folder, `suggestedCommand` lists it;
- `OpenTransactionAlreadyExists` (`conflict`): the hint names the open
  transaction and `suggestedCommand` aborts it. Aborting discards its
  uploads: ask the user unless you opened it yourself;
- `ApiUsageDenied` (`permission_denied`): the OAuth scope that's missing;
  tell the user;
- `<Operation>PermissionDenied`: the operation and resource;
  `suggestedCommand` shows who has roles on it;
- `auth_error` after HTTP 401: the token expired or was revoked; ask the user
  for a new one (`suggestedCommand` shows where it goes);
- `path_not_found`: what a Compass path looks like.
- `BuildTargetsUpToDate` (`validation_error`, exit 6): nothing was built
  because the datasets are already up to date. That is usually fine;
  `suggestedCommand` repeats the command with `--force` if you must rebuild.

## 4. Safety rules

- **Destructive commands** (`destructive: true`: delete, remove, revoke,
  replace, reset, cancel, abort and similar, and every command that applies
  an ontology action) ask for confirmation. With `--format json`, or without
  a terminal, they never prompt: they fail with exit code 2 and change
  nothing unless you pass `--yes`.
- **Ontology actions:** check the parameters with
  `pltr ontology action-validate` (it never applies anything), show the user
  the action and its parameters, and only then run `pltr ontology
  action-apply ... --yes`.
- Pass `--yes` only for a change the user asked for, on resources they
  named. Show them the exact command first when you're unsure. Never loop a
  destructive command over a list you built yourself without confirming the
  list with the user.
- `--confirm` and `--force` (where they meant "skip the prompt") are
  deprecated aliases of `--yes`; use `--yes`.
- **Beta** commands start their help with `[beta]` and have `beta: true`.
  pltr passes `preview=true` for you, but beta endpoints can change or be
  turned off on a stack; say so when you rely on one.
- Prefer reading before writing: `get`/`list` the resource, then change it.

## 5. RIDs

Foundry's API addresses almost everything by RID (Resource Identifier), not by
name: `ri.<service>.<instance>.<type>.<id>`. For example:

- dataset: `ri.foundry.main.dataset.<uuid>`;
- space, project or folder: `ri.compass.main.folder.<uuid>`. The API can't
  list the root folder (`ri.compass.main.folder.0`); start from
  `pltr space list`.

**Paths work too.** Wherever a command takes the RID of a Compass resource
(dataset, folder, project, any resource, media set, connection, model, agent,
...), you can pass the resource's full path instead, starting with its space:
`pltr dataset get "/My Space/My Project/flights"`. pltr resolves it to the RID
before calling the API (one lookup for all the paths in a command) and fails
with `wrong_resource_type` if it's the wrong kind of resource. The API is still
RID-based: output shows RIDs, so save the RID for later calls. Spaces and the
root folder can't be looked up by path. Usage lines show such options as
`RID|PATH`, and the reference marks such arguments "(RID or path)".

Inside JSON arguments, paths work only in the RID fields a command's help
names: `targetRids`, `inputRids` and `ignoredRids` of a build target
(`builds create` TARGET, `schedules create`/`replace` ACTION), schedule
`--trigger` and `--scope-mode`, and a data-health check's subject. Other
JSON, including every `pltr api` JSON option, takes RIDs only.

Users and groups are identified by UUIDs, ontologies by RID or API name, and
object types by API name. Don't construct RIDs; get them from the user, from
a path, or from command output:

```bash
pltr resource get-by-path "/My Space/My Project/flights" --format json   # path -> RID
pltr resource search flights --folder-rid ri.compass.main.folder.<uuid> --format json
pltr space list --format json
pltr project list --format json
pltr folder list ri.compass.main.folder.<uuid> --format json               # a space, project or folder
pltr ontology list --format json
pltr admin user search jane --format json                                  # user IDs
```

## 6. Curated command or `pltr api`?

1. Search first. If a curated command does the job, use it: its arguments
   are friendlier and its help explains the domain.
2. Use `pltr api ...` when no curated command covers the endpoint, or when
   you need an option the curated command doesn't expose.
3. `pltr api` arguments are the endpoint's path parameters. Options taking
   JSON accept the Foundry API's own shape (camelCase), inline, as
   `@file.json` or as `@-` for stdin, and the SDK validates the value before
   anything is sent.

## 6a. Before writing code against a resource: `pltr context`

Run `pltr context` first instead of several `get`/`schema`/`list` commands:
it's one compact pack written for you to read (Markdown, at most 15 KB; pass
`--format table` for it if you set `PLTR_FORMAT=json`, which gives the same
content as JSON). It says what it cut and how to narrow it.

```bash
pltr context dataset <rid-or-path>          # columns + types, sample rows, schedules, latest job
pltr context ontology <ontology> --types Employee,Department   # keys, properties, links, actions, queries
pltr context folder <rid-or-path> --depth 2 # resources with type, path and RID
```

Without `--types`, `context ontology` is a summary of every object type;
describe the ones you need with `--types`. For tests that shouldn't call
Foundry, add `--fixture-dir tests/fixtures` (and `--rows N`, at most 1000):
it writes sample rows (Parquet + schema JSON) or objects (JSON). They are real
data: tell the user, and keep them out of git unless they say otherwise.

## 6b. The verify loop: trigger with `--wait`, then `pltr assert`

After you start a build, a schedule run, an import or a SQL query, don't poll
by hand and don't stop checking early. Add `--wait` (and `--timeout`
seconds; default 600, or 300 for SQL): pltr returns once the work finished,
with exit 0 and the final state, exit 8 if it failed, or exit 9 if it's still
running (then run the error's `suggestedCommand`). Then verify the output
with `pltr assert`, which exits 8 when a check fails:

```bash
pltr orchestration builds create --dataset "/My Space/My Project/sales" --branch master --wait --format json
pltr assert dataset "/My Space/My Project/sales" --min-rows 1 --updated-within 1h --format json
pltr assert build ri.foundry.main.build.abc --succeeded
pltr assert objects my-ontology Employee --min-count 1
```

Keep `--timeout` below your own tool-call timeout (for example 100 for a
two-minute limit): the RID is on the `{"type": "started"}` stderr line, and
after exit 9 the error's `suggestedCommand` waits again without starting the
work twice. Never re-run the trigger command to "retry" a wait.

`--schema expected.json` compares a dataset's columns with the output of
`pltr dataset schema get --format json`. To check an ontology action without
applying it, use `pltr ontology action-validate`.

**After a git push to a code repository**, Foundry's checks run first (a few
minutes) and, on the first push, create the transform's output dataset; you
can't build it before that. Don't write a polling loop: `pltr resource wait`
polls until a resource exists at the path (or RID), then prints it (exit 0),
or exits 9 after `--timeout` (run the error's `suggestedCommand`; it started
nothing, so waiting again is always safe). Then build the branch you pushed
with `--wait`, and check the change itself:

```bash
git push origin my-feature
pltr resource wait "/Space/Project/clean/orders" --timeout 100 --format json
pltr orchestration builds create --dataset "/Space/Project/clean/orders" --branch my-feature --wait --format json
pltr assert dataset "/Space/Project/clean/orders" --branch my-feature --schema expected.json --min-rows 1
```

Without `--branch` the build runs the default branch's code. If it fails at
once with `BuildTargetsMissingJobSpecs` (exit 6), the checks haven't
published the transform on that branch yet: wait a minute and build again.

The public API has no check or commit status: `resource wait` only knows
that the dataset exists, so after a later push it returns at once, and a
build started before the checks finish can run the previous code. Fresh
rows don't prove the new code ran: assert what the change should show
(`--schema` for a new column), and if it doesn't, wait a few minutes and
build again.

## 6c. Writing app code: `--emit-code`

When you write code that calls Foundry (an app, a pipeline, a script), first
get the call working with pltr, then add `--emit-code` to the same command:
it prints the foundry-platform-sdk Python code for that call, with the same
arguments, instead of running it. Use it instead of guessing SDK parameter
names, model classes or pagination:

```bash
pltr ontology object-search my-ontology Employee --where '{"type": "eq", "field": "dept", "value": "R&D"}' --emit-code
pltr api datasets dataset read-table <dataset-rid> --api-format ARROW --emit-code
```

The snippet reads `FOUNDRY_HOST` and `FOUNDRY_TOKEN` (and any secret
argument, such as connection secrets) from the environment, looks up any
Compass path you gave, and pages the SDK's way: read its comments. Nothing runs, so
it's safe on destructive commands. A command that makes several calls (or no
Foundry call) fails with `emit_code_unsupported` (exit 2): use `pltr commands
show <command>` for its SDK methods and `pltr api ... --emit-code` for each.

## 6d. Building an OSDK app: `pltr osdk generate`

To build a TypeScript or React app on ontology objects, generate the OSDK
package with pltr: it needs Node.js 18+ and npm, but no Developer Console
application, and it keeps the token off command lines. Run it from the app's
root:

```bash
pltr context ontology <ontology> --types Order          # API names: properties, links, actions
pltr osdk generate --ontology <ontology> --object-type Order --action-type assign-order --out ./osdk --package-name @orders-app/sdk --format json
```

Add the result's `dependency`, `peerDependencies` (and `reactDependencies`)
to the app's `package.json`, and its `overrides` entry (`@osdk/api`): without
it `tsc` fails with TS2322. Objects get links only with
`--link-type Order.customer` (and the linked object type). To change the
types, run it again with every type and `--replace`.
`npx @osdk/create-app` needs a terminal, so write the app from
[workflows/osdk-react-app.md](workflows/osdk-react-app.md). Signing users
in needs an OAuth client ID from the user, with the app's redirect URIs
registered in Developer Console. To host the built app on Foundry, see §6e.

The object, link and action types must already exist. The Platform API
can't create them, so neither can pltr: ask the user to create them in
Ontology Manager (or in an Ontology as Code repository, where their stack
has one), then check them with `pltr context ontology`.

## 6e. Hosting a web app: `pltr site deploy`

To put a built web app (an OSDK React app, say) on Foundry, build it, then
deploy the build folder to its third-party application's website. One command
zips the folder, uploads it as a new version and deploys it:

```bash
npm run build
pltr site deploy dist --application ri.third-party-applications.main.application.<id> --auto-version package-json --yes --format json
```

- The JSON has the `version`, the website's `subdomains` and `url`
  (`https://` and the first subdomain); `curl` the `url` to check the deploy.
  No `url` comes with a warning that says why: usually the website has no
  approved subdomain yet.
- Versions are `MAJOR.MINOR.PATCH` and can't be uploaded twice (exit 7,
  `conflict`, before anything is uploaded): bump `version` in package.json,
  or pass `--version`. `--auto-version git-describe` takes the git tag
  (`v1.2.0` gives `1.2.0`; commits after it give a pre-release, which Foundry
  may refuse) and refuses uncommitted changes to tracked files. Without a
  version flag the command refuses to run.
- If the deploy fails after the upload, follow the error's message: it says
  whether to deploy the uploaded version with `pltr site rollback` or to
  upload a new one. Don't re-run `site deploy` with the same version.
- Deploying replaces the live site: pass `--yes` only when the user asked for
  the deploy. `--upload-only` uploads without deploying (no `--yes` needed);
  `pltr site rollback <version> --application <rid> --yes` deploys an
  uploaded version, and `pltr site versions --application <rid>` lists them.
- Exit 9 means Foundry was still scanning the upload for vulnerabilities after
  `--timeout`: the version is uploaded, and the error's `suggestedCommand`
  deploys it.

Hosting needs a one-time setup in the UI that pltr can't do; ask the user for
it: website hosting turned on for the application in Developer Console, a
subdomain requested there and approved, the domain added to Control Panel's
network ingress allowlist (otherwise visitors get an ingress 403), and
`https://<subdomain>/auth/callback` registered as a redirect URL of the
application.

## 7. Workflows

**Inspect a dataset and query it with SQL**

```bash
pltr resource get-by-path "/My Space/My Project/flights" --format json
pltr dataset get ri.foundry.main.dataset.<id> --format json
pltr dataset files list ri.foundry.main.dataset.<id> --format json
pltr sql execute 'SELECT origin, COUNT(*) AS n FROM `ri.foundry.main.dataset.<id>` GROUP BY origin' --format json
```

**Build a dataset and follow the build**

```bash
pltr orchestration builds create --dataset ri.foundry.main.dataset.<id> --branch master --format json
pltr orchestration builds create '{"type": "upstream", "targetRids": ["/My Space/My Project/sales"], "ignoredRids": []}' --branch master --format json
pltr orchestration builds get ri.foundry.main.build.<id> --format json
pltr orchestration builds jobs ri.foundry.main.build.<id> --format json
```

**Search ontology objects** with Foundry's typed query (`SearchJsonQueryV2`):

```bash
pltr ontology object-search my-ontology Aircraft \
  --where '{"type": "eq", "field": "status", "value": "ACTIVE"}' \
  --properties tailNumber,status --format json
```

`pltr api ontologies ontology-object search` takes the endpoint's request
exactly as Foundry's API docs describe it, for options the curated command
doesn't have.

**Grant access to a project**

```bash
pltr admin user search jane --format json                      # find the user ID
pltr resource-role list ri.compass.main.folder.<id> --format json   # role IDs in use
pltr resource-role grant ri.compass.main.folder.<id> --role <role-id> --principal-id <user-uuid>
```

Role IDs come from the role set of the project's space (for example
`compass:manage` is Owner in the default role set).

More: [workflows/](workflows/) has longer workflows for data exploration,
pipelines and permissions.

## Getting help

```bash
pltr commands search <words>      # find a command
pltr commands show <command>      # everything about one command
pltr <group> --help               # a group's commands
```
