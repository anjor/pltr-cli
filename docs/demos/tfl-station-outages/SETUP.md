# Setup checklist

Do this before the rehearsal. It covers everything in the Foundry UI except
the object type and action, which are created on camera. Allow a day: the
website subdomain needs approval.

## Foundry

- [ ] **Folder** `/<space>/pltr demos/station-outages`, where `<space>` is
      the first part of the "pltr demos" project's path in
      `pltr project list`. Create it with
      `pltr folder create station-outages --parent-folder "/<space>/pltr demos"`
      or in the UI. The code repository goes in it.
- [ ] **Code repository** in that folder: the Python transforms template,
      named `station-outages-transforms`. Leave the template's example
      transform as it is.
- [ ] **Developer Console application** named `Station Outages`:
  - [ ] An OAuth client for a single-page app (public client, no secret).
  - [ ] Redirect URIs `http://localhost:8080/auth/callback` and
        `https://<subdomain>/auth/callback`.
  - [ ] Website hosting turned on, with a subdomain requested. **Wait for
        approval.**
  - [ ] The subdomain's domain added to Control Panel's network ingress
        allowlist. Without it, the hosted app answers 403.
  - [ ] Note the application RID, the client ID and the subdomain for
        [PROMPT.md](PROMPT.md).
- [ ] **Leave the ontology alone.** The object type and action are created
      during the recording, from the agent's spec.

## The machine

- [ ] `uv tool install pltr-cli==0.20.0` (or `pipx install
      pltr-cli==0.20.0`). Then `pltr --version` should print 0.20.0.
- [ ] `pltr verify` passes with the default profile.
- [ ] A separate Claude Code configuration for the demo, so the run starts
      cold. Your usual one loads your global `CLAUDE.md`, rules, plugins and
      memory, and a plugin with an older pltr skill would compete with
      0.20.0's. Install the skill from the 0.20.0 tag into it, without
      changing your checkout:

      ```sh
      export CLAUDE_CONFIG_DIR=~/.claude-pltr-demo
      mkdir -p "$CLAUDE_CONFIG_DIR/skills/pltr"
      git -C <pltr-cli checkout> archive v0.20.0 claude_skill | tar -x --strip-components=1 -C "$CLAUDE_CONFIG_DIR/skills/pltr"
      ```
- [ ] Run `claude` with `CLAUDE_CONFIG_DIR` set, and sign in with `/login`.
      Start the rehearsal and the recording the same way.
- [ ] Node.js 18 or later and npm (`node --version`).
- [ ] An empty demo directory, such as `~/demos/station-outages`, holding
      only the clone of the code repository at `./transforms`. Check that
      `git push` works from the clone.
- [ ] No `CLAUDE.md` in the demo directory or its parents. The separate
      configuration takes care of memory and plugins.
- [ ] The three data URLs in [PROMPT.md](PROMPT.md) answer:
      `uv run docs/demos/tfl-station-outages/check_data.py` in the pltr-cli
      checkout prints 200 for each, then the counts that
      [PLAN.md](PLAN.md) quotes.

## Recording setup

- [ ] Screen at 1920x1080, with the terminal on the left two-thirds and the
      browser on the right third.
- [ ] Terminal font at 16 pt or larger, and a shell prompt that doesn't show
      the hostname or username.
- [ ] A browser profile signed in to Foundry, with no other tabs and the
      bookmarks bar hidden.
- [ ] Do Not Disturb on.
- [ ] Screen recorder (OBS or QuickTime) recording the full screen. Keep
      the raw file: the video is cut from it.
- [ ] A notes file open off-screen, to log the time of each act (see
      [SCRIPT.md](SCRIPT.md)).

## After the rehearsal

- [ ] Delete what the rehearsal made, so the recording starts clean:
  - the raw and output datasets;
  - the object type and action;
  - the transform commits (reset the repository's branch);
  - the website versions.

  Or use a second folder and application for the recording.
- [ ] Note every place the agent stumbled, in a new Rehearsal section of
      [PLAN.md](PLAN.md).
