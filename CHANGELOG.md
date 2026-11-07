# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
While pltr is 0.x, a minor release can contain breaking changes; they are
listed under "Breaking changes" or marked **Breaking**.

Entries for 0.5.0 to 0.16.0 were written after the fact from the git history
and pull requests. Numbers in parentheses are pull requests or issues.

## [0.16.0] - 2026-06-25

### Changed

- Requires foundry-platform-sdk 1.95.0 or later (was 1.69.0) (#173).

### Removed

- **Breaking:** Python 3.9 support. pltr needs Python 3.10 or later, like the
  SDK since 1.71 (#173).

## [0.15.0] - 2026-04-17

### Added

- `pltr language-models list`, `status` and `enroll` (#164, #165; #167,
  #168). They call Foundry endpoints directly: the SDK has no methods for
  them.
- `pltr ontology object-type-create` and `link-type-create` (#143; #169).
  They also call Foundry endpoints directly.

### Fixed

- `pltr sql execute` decodes the Arrow IPC results the API returns into rows
  (#171). pltr now depends on pyarrow.
- `language-models anthropic messages` and `messages-advanced` send message
  roles in upper case (`USER`, `ASSISTANT`), as the API requires (#163;
  #166).

## [0.14.1] - 2026-02-28

### Fixed

- `language-models anthropic messages` and `messages-advanced` pass their
  parameters to the SDK as keyword arguments; they passed a `request` object
  the SDK doesn't accept (#159; #161).

## [0.14.0] - 2026-02-28

### Fixed

- `project list` uses filesystem endpoints the SDK has (#155).
- `resource list` and `resource search` walk folders instead of calling
  methods the SDK doesn't have (#156).
- `connectivity connection list` works with current SDK clients, falling
  back to scanning folders (#154).
- `orchestration builds search` handles beta (preview) mode and paging
  (#153).
- `folder list` and `resource get-by-path` failures show the error details;
  they printed an empty message (#157, #158).

## [0.13.1] - 2026-02-25

### Added

- `pltr data-health`: `check get`, `create`, `replace` and `delete`, and
  `report get` (#37; #131).
- `pltr audit list` and `audit get` for audit log files (#35; #132).
- `pltr widgets`: `get`, `release list/get/delete`, `repository get` and
  `dev-mode get/enable/disable/pause` (#31; #133).

### Changed

- **Breaking:** `folder create` and `dataset create` require
  `--parent-folder`. The old default, the root folder
  `ri.compass.main.folder.0`, doesn't exist on some stacks, so creates
  failed silently (#137; #140).

### Fixed

- `--format json` and `--format csv` print to stdout; before, they only
  took effect with `--output` (#136; #141).
- Ontology object commands use the parameter names of foundry-platform-sdk
  1.69.0 (`select` and `branch`) (#135; #139).

## [0.13.0] - 2026-02-04

### Added

- `pltr functions`: `query get`, `get-by-rid`, `execute` and
  `execute-by-rid`, and `value-type get` (#109; #116).
- `pltr streams`: `dataset create` and `stream create`, `get`, `publish`,
  `publish-batch` and `reset` (#29, #110; #118).
- `pltr language-models`: `anthropic messages`, `anthropic messages-advanced`
  and `openai embeddings` (#120; #123).
- `pltr models`: `model create`, `model get`, `version get` and
  `version list` (#121; #124).
- `project create --owner-id` and `--owner-type` (#129).

### Changed

- Requires foundry-platform-sdk 1.69.0 (was 1.27.0) (#117).
- **Breaking:** `space create` requires `--enrollment-rid`, `--organization`
  and `--deletion-policy-org`, as SDK 1.69.0 does (#126; #127).

### Removed

- **Breaking:** `space list-members`, `space add-member`,
  `space remove-member`, `space batch-get`, `project batch-get` and
  `resource move`. SDK 1.69.0 removed their endpoints (#126; #127).

### Fixed

- `admin user list` and `admin group list` show paged results (#114).
- Project, space, folder and resource commands updated for the
  SDK 1.69.0 API changes (#126; #127).

## [0.12.0] - 2026-01-27

### Added

- `pltr cp`: copy datasets, or folders with their contents, into another
  folder (#95; #96).
- A Claude Code skill in `claude_skill/` (#97).
- Admin: `user delete`, `user batch-get`, `group batch-get`,
  `role batch-get`, `org create`, `org replace`, `org available-roles`, and
  `marking list/get/batch-get/create/replace` (#65; #98).
- Orchestration: `builds get-batch` and `schedules runs` (#69; #99).
- Media sets: `thumbnail-calculate`, `thumbnail-retrieve` and `upload-temp`
  (#70; #100).
- Filesystem: `resource delete`, `restore`, `permanently-delete`,
  `add-markings`, `remove-markings`, `list-markings`, `access-requirements`
  and `batch-get-by-path`; `project add-orgs`, `remove-orgs`, `list-orgs` and
  `create-from-template` (#72; #101).
- Connectivity: `connection create`, `get-config`, `update-secrets`,
  `update-export-settings` and `upload-jdbc-drivers` (#67; #102).
- `--page-size`, `--page-token`, `--max-pages` and `--all` on
  `admin user list`, `orchestration builds search`, `ontology object-list`
  and `dataset files list` (#46; #106).
- `pltr dataset preview` (#105). pltr now depends on pandas.
- `pltr third-party-apps get` (#30; #107).
- `pltr aip-agents`: `get`, `sessions list/get` and `versions list` (#108;
  #112).

### Changed

- **Breaking:** the commands that gained paging options fetch one page by
  default; pass `--all` for every page (#106).

### Fixed

- SQL commands call the SQL query endpoints in preview mode, which they
  required; `--preview` is on by default (#93).

## [0.11.0] - 2025-10-09

### Added

- `ontology object-count` and `ontology object-search` (#68; #90).

### Fixed

- `dataset files get` downloads with `Dataset.File.content`; it called a
  method the SDK doesn't have (#91).

## [0.10.0] - 2025-09-30

### Added

- `resource get-by-path`: get a resource by its Compass path (#86).

### Fixed

- `--format json` prints plain JSON without terminal markup, so it can be
  piped (#87).
- `orchestration builds create --help` documents the build target JSON
  (#87).
- Tables no longer wrap RID columns (#87).

## [0.9.3] - 2025-09-30

No changes to pltr itself; only the version number changed.

## [0.9.2] - 2025-09-24

### Fixed

- `orchestration builds create` sends `fallback_branches` as a list (#84).

## [0.9.1] - 2025-09-12

### Fixed

- `dataset schema apply` applies the inferred schema; it only inferred it
  (#82).

## [0.9.0] - 2025-09-12

### Added

- `dataset schema apply`: infer a dataset's schema from its files and apply
  it, through the endpoints Foundry's web interface uses (direct HTTP calls),
  for stacks where the SDK's schema endpoints needed preview access (#78).

## [0.8.0] - 2025-09-12

### Changed

- `dataset files upload` errors name the Foundry error and suggest a fix
  (#76).

## [0.7.0] - 2025-09-11

### Added

- `dataset schema get` and `dataset schema set`, including `--from-csv` to
  infer column types from a CSV file (#64).
- `dataset branches delete`, `get` and `transactions`; `dataset files delete`
  and `info`; `dataset transactions build`; `dataset views get`,
  `add-datasets`, `remove-datasets`, `replace-datasets` and
  `add-primary-key`; `dataset schedules list`; `dataset jobs list` (#74).

## [0.6.0] - 2025-09-09

### Fixed

- `dataset files upload` sends the file's content (#62).

## [0.5.2] - 2025-09-09

### Fixed

- Dataset file and transaction commands failed with an `AttributeError`;
  they now call the SDK's `Dataset.File` and `Dataset.Transaction` (#59;
  #60).

## [0.5.1] - 2025-09-09

### Added

- `pltr project`, `pltr resource`, `pltr resource-role` and `pltr space`
  (#43; #52).
- `dataset transactions start`, `commit`, `abort`, `status` and `list`, and
  `dataset files upload --transaction-rid` (#48; #53).
- `pltr connectivity`: connections and file and table imports (#36; #54).
- CSV upload examples in `docs/examples/csv-upload.md` (#55).

### Fixed

- `pltr --version` printed 0.1.0 (#50).

## [0.5.0] - 2025-09-03

### Added

- `pltr orchestration`: builds, jobs and schedules (#28; #40).
- `pltr media-sets`: `get`, `get-by-path`, `create`, `commit`, `abort`,
  `upload`, `download` and `reference` (#27; #41).
- `dataset branches list/create`, `dataset files list/get`,
  `dataset transactions list` and `dataset views list/create` (#32; #42).

## [0.4.0] - 2025-08-31

### Added

- `pltr folder`: `create`, `get`, `list` and `batch-get` (#33).

### Fixed

- CI pipeline fixes (#38).

## [0.3.0] - 2025-08-28

### Added

- Command aliases: `pltr alias` (#15).

### Fixed

- `ontology list` and the object type commands called the SDK incorrectly
  (#21, #22; #23).

### Removed

- `--page-size` on ontology commands; their SDK methods didn't take it
  (#23).

## [0.2.0] - 2025-08-15

### Added

- `pltr ontology` (#6), `pltr sql` (#7) and `pltr admin` (#8).
- `pltr shell`, an interactive mode (#9), and `pltr completion` for bash,
  zsh and fish (#11).
- User documentation in `docs/` (#14).

## [0.1.2] - 2025-08-10

### Fixed

- The release workflow (an updated signing action).

## [0.1.1] - 2025-08-10

### Fixed

- The install command in the README is `pip install pltr-cli`.

## [0.1.0] - 2025-08-10

### Added

- First release, published on PyPI as `pltr-cli`: `pltr configure` (token
  and OAuth2 profiles, with credentials in the system keyring),
  `pltr verify`, `pltr dataset get` and `pltr dataset create`.

[0.16.0]: https://github.com/anjor/pltr-cli/compare/v0.15.0...v0.16.0
[0.15.0]: https://github.com/anjor/pltr-cli/compare/v0.14.1...v0.15.0
[0.14.1]: https://github.com/anjor/pltr-cli/compare/v0.14.0...v0.14.1
[0.14.0]: https://github.com/anjor/pltr-cli/compare/v0.13.1...v0.14.0
[0.13.1]: https://github.com/anjor/pltr-cli/compare/v0.13.0...v0.13.1
[0.13.0]: https://github.com/anjor/pltr-cli/compare/v0.12.0...v0.13.0
[0.12.0]: https://github.com/anjor/pltr-cli/compare/v0.11.0...v0.12.0
[0.11.0]: https://github.com/anjor/pltr-cli/compare/v0.10.0...v0.11.0
[0.10.0]: https://github.com/anjor/pltr-cli/compare/v0.9.3...v0.10.0
[0.9.3]: https://github.com/anjor/pltr-cli/compare/v0.9.2...v0.9.3
[0.9.2]: https://github.com/anjor/pltr-cli/compare/v0.9.1...v0.9.2
[0.9.1]: https://github.com/anjor/pltr-cli/compare/v0.9.0...v0.9.1
[0.9.0]: https://github.com/anjor/pltr-cli/compare/v0.8.0...v0.9.0
[0.8.0]: https://github.com/anjor/pltr-cli/compare/v0.7.0...v0.8.0
[0.7.0]: https://github.com/anjor/pltr-cli/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/anjor/pltr-cli/compare/v0.5.2...v0.6.0
[0.5.2]: https://github.com/anjor/pltr-cli/compare/v0.5.1...v0.5.2
[0.5.1]: https://github.com/anjor/pltr-cli/compare/v0.5.0...v0.5.1
[0.5.0]: https://github.com/anjor/pltr-cli/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/anjor/pltr-cli/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/anjor/pltr-cli/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/anjor/pltr-cli/compare/v0.1.2...v0.2.0
[0.1.2]: https://github.com/anjor/pltr-cli/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/anjor/pltr-cli/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/anjor/pltr-cli/releases/tag/v0.1.0
