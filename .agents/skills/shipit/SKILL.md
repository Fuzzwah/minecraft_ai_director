---
name: shipit
description: Release the Minecraft AI Director through a verified topic-branch PR to main.
---

# Minecraft AI Director release

## Identity and rules

- Repository: `Fuzzwah/minecraft_ai_director`, remote `origin` at
  `git@github.com:Fuzzwah/minecraft_ai_director.git`.
- Component: standard-library Python quest Director and optional durable
  settlement construction, including trusted Java 26.3 datapack assets.
- Resolve the current root with `git rev-parse --show-toplevel`; do not switch
  repositories. This host's checkout is
  `/home/fuz/orca/workspaces/minecraft_ai_director/village`.
- Read root `AGENTS.md` and `README.md`, plus any subsequently added applicable
  contribution/deployment rules. Preserve their world safety and recovery rules.
- Allowed source: a nonempty, non-`main` topic branch. This release uses
  `Fuzzwah/village`. Target: **`main`**, GitHub's default branch.
- Do not commit/push directly to `main`. Before each commit or push, run
  `git branch --show-current` and verify the source branch.
- Commit/push/PR work is performed **directly**; there is no project requirement
  to route through `@committer` and no such role is configured here.
- This workflow belongs in the repository and is included in the signed-off
  release establishing project operating/release documentation.

## Scope and validation

Inspect status, tracked/untracked paths, full release diff, remote, and existing
PRs before staging. Stop on unrelated changes; do not stash, discard, reset,
amend, or force-push them. Stage explicit approved paths, never `git add .`.

For the settlement release, approved paths are `.gitignore`, `AGENTS.md`,
`README.md`, `director.py`, `settlement.py`, `settlement_admin.py`,
`config/structures.json`, `config/settlement.json`, `datapack/director_buildings/`,
`tests/`, and this workflow. Confirm directory contents contain only approved
assets/tests before staging. Later releases must determine their own exact scope.

Required local validation from the repository root:

```bash
python3 -B -m unittest discover -v
python3 -B settlement_admin.py --help
git diff --check
```

Tests need no external packages or server. There is no configured formatter,
build step, or GitHub Actions workflow at this release; do not invent a gate.
Inspect remote protection/rules on each release rather than assuming they remain
unchanged.

For RCON/construction changes, require real Java 26.3 smoke evidence in the
isolated test world. Historical Java 1.21.1 evidence covered staged workshop
construction, chest rejection, owned upgrade, safe removal, and restart
persistence. Fresh 26.3 evidence covers starter placement and exact blocks,
idempotent initialization, guarded removal preview, and loaded chunks past the
idle threshold. Re-exercise changed behavior on future releases; do not claim
client rendering or authenticated quest completion from RCON alone.

For a release, confirm the running server, settlement, and a real read-only
world-mutation preview, with unchanged SQLite checksum:

```bash
export TEST_ROOT=/home/fuz/mc-director-village-test
"$TEST_ROOT/server.sh" status
"$TEST_ROOT/director.sh" status
"$TEST_ROOT/server.sh" console list
"$TEST_ROOT/director.sh" admin show settlement
"$TEST_ROOT/director.sh" admin list plots
sha256sum "$TEST_ROOT/director_settlement.sqlite3"
DIRECTOR_DRY_RUN=1 "$TEST_ROOT/director.sh" admin remove structure civic_center
sha256sum "$TEST_ROOT/director_settlement.sqlite3"
```

Inspect current state first. The example previews removal of the existing shrine;
never omit `DIRECTOR_DRY_RUN=1`. If it has changed or is occupied, choose another
unchanged, unoccupied building or an unlocked construction on a compatible free
plot. Report unavailable smoke if neither exists. A cottage is locked at the fresh
world's 0 XP; do not grant XP or remove buildings to manufacture a smoke fixture.
The checksum must match unless an independently observed concurrent Director
write occurred; in that case isolate writers safely and verify again.
No blind mutation retries.

Keep credentials, worlds, quest JSON, SQLite files/backups, and logs out of Git.
The host-only Podman cgroup configuration and private test deployment files are
not release assets. They are documented in `AGENTS.md` and `README.md`.

## Commit, PR, and merge

1. Review the final diff and validation evidence. Create one concise imperative
   commit covering all and only signed-off paths; use existing Git identity.
2. Verify branch again; push the topic branch to `origin` with upstream tracking.
3. Reuse an existing open PR for this source if one exists; otherwise create a
   non-draft PR targeting `main`. Write the body to an artifact outside the repo
   and use `gh pr create --body-file` to preserve Markdown formatting.
4. PR title describes the feature/fix. Body sections:
   - `## Summary`: behavior and scope, including documentation/workflow changes.
   - `## Verification`: actual unit/CLI/live checks, results, and visual limits.
   - `## Safety and deployment`: opt-in integration, durable recovery boundary,
     private RCON, state preservation, and explicit production deferral.
5. Inspect the published title/body/base/head using `gh pr view`. Fix malformed
   formatting before merging.
6. Inspect `reviewDecision`, reviews, `statusCheckRollup`, `mergeable`, and
   `mergeStateStatus`. Refresh remote branch protection and active rules.
   At workflow creation, `main` is unprotected with no active rules or required
   checks/approvals; this is an observed baseline, not a bypass permission.
7. All required checks/reviews must pass. Also do not merge with pending/failing
   reported checks, requested changes, unresolved review threads, conflicts, or
   blocked/unknown mergeability. Report pending/unavailable/blocking gates rather
   than bypassing them. No required post-PR synchronization is currently defined;
   update only if a repository gate requires it, without force-pushing.
8. Normal merge method is **squash** (enabled on GitHub). Use
   `gh pr merge <number> --squash --match-head-commit <verified-head-sha>`.
   Do not use `--admin`, bypass gates, or delete the source branch: it is used by
   the live test-server checkout/worktree.
9. Confirm PR state `MERGED`, URL, merge commit, and working-tree status. Do not
   switch this live-mounted checkout to `main` just for release housekeeping.
10. Report workflow path/creation, commit subject/hash, pushed branch, PR URL,
    checks/review state observed, merge SHA/state, validation, and deployment.

## Deployment block

**Production/family-server deployment is intentionally deferred.** This release
publishes source/assets/docs, not a cutover of any existing family world.
Settlement integration remains off by default. Enabling it needs administrator
world backups, a stable world ID, reviewed empty plots/protected regions,
compatible installed templates, and a successful server-connected dry-run.

The isolated test deployment at `/home/fuz/mc-director-village-test` is already
running Java 26.3 on `10.1.1.232:25568` with private localhost RCON and DEMO mode. Preserve
its world/configuration/quest state/SQLite and reconciliation backups. No restart
is required merely for this release's Git commit/merge or documentation changes.
For future Python changes requiring reload, follow `AGENTS.md` lifecycle controls;
never start a second Director loop. Runtime config/datapack copies must be
explicitly reviewed and deployed, not overwritten from repository examples.
