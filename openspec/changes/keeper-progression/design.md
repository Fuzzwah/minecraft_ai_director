# Design

## Context

See `proposal.md` for motivation and the two capability deltas for observable behavior. This design is required because the change crosses quest persistence, reward dispatch, authoring, and irreversible world mutation.

Observed integration points:

- `director.State` owns active lanes and capped warm-up counters; `save_state` uses a temporary file, fsync, rename, and directory fsync. `load_state` rejects malformed saves rather than discarding reward debt.
- `PendingReward` stores consumption/reward progress and frozen recipients. `process_pending_rewards` commits lane progress only after base rewards and required settlement obligations finish. This is the Keeper-credit boundary.
- `vanilla_commands` currently regenerates a command sequence from the pending quest and choice. Inserting rank-dependent commands into that sequence without freezing/migrating it would reinterpret saved `vanilla_step` and risk duplicate payment.
- `StructureManager` requires settlement configuration and SQLite. Its environment checks, per-command mutation prefixes, exact-state inspection, and durable intents are useful patterns, but its whole-template placement and sensitive-block scan cannot directly upgrade the generated chest-bearing temple.
- `tools/village_temples.py` authors 32 roots on 25x25 plazas, records feature cells/chest/entry positions, rotates positions and facing properties, and checks support and traversal. The read-only baseline inspection returned 32 roots and 128 rotations. Those results do not validate proposed sculptures or new mutations.
- Existing `tests/test_director.py` covers successful completion without settlements, uncertain consumption/rewards, capped warm-up transitions, ownership, and dry-run. `tests/test_village_temples.py` decodes the actual NBT and checks rotations/processors/access.
- The older `adaptive-offering-quests` delta still describes ender-chest submission. Current code/docs and `greek-temple-shared-offerings` use one normal chest. This change preserves the latter contract; stale-artifact reconciliation is not a prerequisite code rewrite or part of this change.

## Goals / Non-Goals

**Goals:**

- Reuse the quest-state durability boundary rather than introduce a second progression database.
- Freeze every reward transaction before dispatch and credit completion in one final state commit.
- Keep ordinary appearance blockers independent of quest rewards and earned progress.
- Make geometry, policy, and mutation authority inspectable and deterministic without model decisions.

**Non-Goals:**

- No new generic job framework, generalized block editor, model reward API, or settlement dependency.
- No native copper-statue state/block-entity dependency: recognizable block-built sculptures are the chosen implementation, not a fallback after unsafe placement.
- No second writer/admin mutation loop, historical-credit inference, automatic temple repair, or configuration-change migration that rebinds occupied geometry.

## Decisions

### 1. One additive Keeper record in quest JSON

Add a versioned Keeper record to `State`, containing:

- Immutable binding: stable admin-selected `world_id`, dimension `minecraft:overworld`, approved root resource, temple minimum corner, facing, configured chest, and decoration-definition digest.
- `credited_quest_ids`: validated unique quest IDs completed while enabled. Keeper total is the number of these IDs and rank is derived from the fixed policy; do not persist an independent total that can drift from the ledger.
- `installed_rank`, initially 1 after baseline enrollment; `last_announced_rank` for best-effort at-most-once rank notices.
- Optional `upgrade`: milestone/predecessor, definition/geometry snapshot, ordered exact transitions, next step, dispatch uncertainty, status, and bounded error/evidence.

A successful completion adds its ID, advances the existing capped lane counter, makes that lane due, removes its active/pending quest, and saves once. Reject credited IDs before inventory inspection or preparing another reward. If that save fails, stop the writer rather than continue with an in-memory-only completion.

The ledger is deliberately append-only for exact duplicate rejection. It is not a new quest-history subsystem. JSON rewrite cost grows with completed quests; record that limit rather than prematurely adding SQLite or pruning idempotency evidence.

Activation initializes an empty ledger, not the capped warm-up totals. Existing active quests complete normally and earn credit if successful after activation. Existing pending rewards keep their old rewards; successful post-activation resolution earns one credit. An unresolved migrated operation earns nothing. Disabling the feature pauses new credit/benefits/decorations but preserves the record and finishes only already frozen reward obligations without silently losing debt.

Alternative rejected: reuse settlement XP. It is optional, has different levels/rewards, and would couple Keeper behavior to a disabled production subsystem.

### 2. Fixed rank policy with conservative balancing defaults

The user confirmed the five thresholds, protection/utility powers, and player XP rather than item increases. Exact effect durations and point amounts below are planning defaults, not live observations; they define the initial policy to implement and review.

| Rank | Minimum completions | Bonus XP points | Haste I duration | Resistance I duration |
| --- | ---: | ---: | ---: | ---: |
| Dormant | 0 | 0 | none | none |
| Awakened | 3 | 5 | 30 s | none |
| Warden | 10 | 10 | 60 s | 30 s |
| Exalted | 25 | 15 | 90 s | 60 s |
| Ascendant | 50 | 20 | 120 s | 90 s |

Use XP **points**, not extra levels, on top of the existing tier-dependent base XP-level command. Do not change `REWARDS`, settlement rewards, candidate bands, quantities, or progression scores. Use amplifier zero for level-I effects and vanilla effect merging, without `effect clear`, per-tick renewal, or an aura. Verify stronger active-effect preservation and same-effect refresh on Java 26.3 before accepting the implementation.

Freeze the currently earned rank when creating `PendingReward`. This keeps an offering's entitlement stable while settlement jobs or another lane complete. A third completion prepared at Dormant unlocks Awakened but receives no retroactive Awakened benefits. All later transactions use the earned rank, even if appearance is blocked.

Alternatives rejected: harder-quest weighting, a per-recipient multiplier, or bonus levels; these would change the shared-growth/economy decisions. Native statue blocks are unnecessary for this policy.

### 3. Migrate to one frozen reward plan and one executor

Extend pending rewards with a versioned list of typed, trusted actions sufficient to reproduce the base item reward, base levels, Keeper XP points/effects, and completion notifications for the captured recipients. Validate action kinds, IDs, amounts, and recipient names against the code-owned policy; do not accept arbitrary reward commands from saved/model input.

At preparation, freeze the original base choice, earned Keeper rank, recipients, and complete action ordering before consumption. Keep non-idempotent item/XP actions ahead of notifications. Execute from persisted progress using the existing persist-before-dispatch uncertainty discipline. Match actual Java 26.3 acknowledgement formats for the new XP/effect operations; no empty-response or generic-success fallback. Definite failures do not credit completion; ambiguous dispatched actions remain uncertain and must not replay. Stronger-effect merge/no-change responses need an explicit verified acceptable outcome rather than an invented success match.

On loading an unversioned pending record, materialize precisely its old `vanilla_commands` sequence as typed actions using its existing quest, choice, recipients, `vanilla_step`, and `vanilla_uncertain`. Do not append Keeper benefits or reorder already prepared actions. Migrate all records to the new representation and use one executor afterwards; remove the old regeneration path rather than retain a legacy executor. Check progress against the frozen plan length, not a stale fixed command count. Dry-run migration stays in memory.

The existing settlement `recorded`, XP, structure-step, and ownership obligations remain intact. Keeper credit occurs only after both the frozen reward plan and those existing obligations succeed. When Keeper is enabled, any uncertain reward prevents the completion commit and reports reconciliation; it does not silently pay again.

Alternative rejected: regenerate commands from current rank every poll. Rank advancement or policy edits would shift indices in pending records.

### 4. Explicit opt-in binding, independent of settlements

Proposed configuration surface follows the existing environment pattern:

- `DIRECTOR_KEEPER_ENABLED=1` activates new progression and evolution; default is off.
- `KEEPER_WORLD_ID`: stable opaque identity for this world, retained across restarts and never used as a retry switch.
- `KEEPER_TEMPLE_RESOURCE`: approved manifest root ID.
- `KEEPER_TEMPLE_MIN_X/Y/Z`: actual full template minimum corner, including the floor, not the quest hub or a translated placement anchor.
- `KEEPER_TEMPLE_FACING`: north/east/south/west using the existing facing convention.
- `KEEPER_TEMPLE_DEFINITIONS`: trusted patch-manifest path, default `config/keeper_temples.json`.

No dimension override: the initial scope is the existing overworld offering contract. Match the transformed authored chest to `OFFERING_CHEST`, validate baseline mutable cells/required clearance and temple identity, and durably enroll before credit or mutation. Verify the actual root and rotation administratively; do not infer them from spawn or search for a convenient alternative.

Once enrolled, binding/digest disagreement fails closed without replacing the record, switching world IDs, or moving the temple. Unsent work may resume only under the same verified definition. A future definition migration would require its own explicit reviewed migration; do not build one into this change.

Default-off deployment is a safe cutover, not a compatibility alias. An existing state file without Keeper data loads with zero progress when deliberately enabled. A dry-run computes prospective enrollment without saving it. Starting with malformed/inconsistent enabled configuration is an actionable startup failure before inventory mutation.

### 5. Derive small patch assets from the actual roots

Add a separate, versioned `config/keeper_temples.json` generated by an explicit authoring option in `tools/village_temples.py`; keep `--check` read-only. Do not alter the bundled generation NBT, pools, weights, processors, or baseline temple manifest merely to enable progression.

Each of the 32 root definitions records template size/floor, chest/entry, required no-touch/access cells, and ordered rank transitions with unique local positions, complete expected and target states, and necessary supports. Select processor-stable target cells so both normal and abandoned roots remain eligible without treating weathered blocks as clearable terrain. Derive coordinates from the existing real root/feature records, not repository example world positions.

Author cumulative visual stages:

- Awakened: additional supported warm lighting beside the altar and entrance, not a chest-lid obstruction or removal of current lanterns.
- Warden: paired recognizable block-built golem sculptures in side sanctuary positions. Use approved waxed copper blocks/stairs/slabs for a stable, static silhouette; no pumpkin-head golem spawning construction, entity payload, or extra container.
- Exalted: enhance the idol's crown/body accents and selected decorative capitals with gold/copper while retaining its stone identity and structural support.
- Ascendant: complete the sanctuary light pattern and enhance the existing sun motif without replacing the pediment/roof or occupying access routes.

Validate every cumulative appearance and every intermediate mutation prefix for support, bounds, road-to-altar/chest traversal, lid clearance, excluded sensitive/access cells, and four rotations. Rotate both position and state properties using the established authoring conventions. Local-to-world conversion is minimum corner plus the rotated local coordinate; never feed the minimum corner into whole-template placement.

The implementation must author concrete coordinates/shapes and demonstrate client recognition. This is asset authoring within the decided approach, not a deferred architectural investigation. If the chosen blocks are unsupported by Java 26.3 or access cannot be preserved, stop acceptance and fix the authored design; do not silently substitute an entity or whole-template replacement.

### 6. A bounded, durable decoration state machine

Implement the small state machine in proposed `keeper.py`, using supplied read-only/mutation RCON callbacks and the existing quest-state save owner. No `StructureManager`, SQLite schema, autonomous background writer, or admin mutation process is required.

Process the earliest earned but uninstalled milestone after ordinary quest work. Use at most 16 acknowledged block mutations per Director tick. Before creating an intent, verify the entire declared mutable predecessor footprint and required access/identity probes. Verify any already acknowledged prefix against its expected intermediate state before resuming. An ordinary preflight blocker retains a bounded reason and can be re-probed safely without dispatch; it does not freeze quests or force chunks to load.

For every dispatched cell:

1. Persist the immutable stage/transition snapshot and mark that step dispatch-uncertain before sending.
2. Include the overworld dimension, all affected loaded-chunk guards, full-temple player exclusion, and exact expected block state in the mutating `execute ... run setblock ...` command.
3. Accept only the real target-version command acknowledgement and an exact target-state readback; then persist the next acknowledged step and clear uncertainty.
4. If dispatch or acknowledgement is ambiguous, keep uncertainty and stop the writer. Startup must not resend the step or infer successful completion solely from finding a target-looking block.
5. At stage end, verify the complete cumulative decorative footprint, chest identity/lid space, and traversal invariants before committing `installed_rank` and clearing the job.

A definite guard failure with proven no mutation can remain blocked; a reply that does not prove this stays uncertain. Never mark a stage installed after an empty reply. A final verification failure after acknowledged steps preserves its evidence and does not repeat those steps; resume only with the saved prefix consistent or deliberate offline reconciliation.

Earned and installed ranks are separate. A preflight obstruction, player presence, or unavailable chunk simply delays appearance. A lost dispatched-mutation reply is a stronger safety condition: stop writers and reconcile, as for other uncertain world operations. This distinction preserves continued quests under ordinary decoration blockers without concealing uncertain mutation.

Completed stages never replay or self-repair. Each later stage verifies its predecessor footprint, so an edited prior sculpture blocks a dependent stage instead of being overwritten. Empty temples are required for mutation; upgrades may therefore become visible after players leave, not instantly during the offering ceremony.

Alternative rejected: whole-template upgrade. It can erase chest contents, player edits, or unsupported blocks and would require borrowing settlement placement ownership that this temple does not have.

### 7. Read-only inspection and bounded announcements

Add proposed `keeper_admin.py` with `show` and `preview` operations following the project's argparse/JSON admin pattern. `show` reads saved progress; `preview` also requires RCON and checks actual blocks. Neither runs the Director loop, an LLM, settlement initialization, or a state-save path. Set read-only mode before importing any module with import-time configuration/migration behavior.

Report binding, completion total, earned/installed ranks, next threshold, due stage, proposed cells, and blocked/uncertain evidence. Missing optional SQLite is not an error for Keeper inspection; preserve any database that is present.

After a successful completion commit, announce rank advancement and its powers using the existing Keeper tellraw style. Persist the notice watermark before dispatch for best-effort at-most-once delivery; a crash can lose a cosmetic notice but must not replay rewards. Public status remains authoritative. Do not add scoreboard objectives, signs, holograms, a chat-command parser, or a notice outbox framework.

## Risks / Trade-offs

- Vanilla RCON cannot atomically protect a multi-block patch from external edits -> exact guards on each command, preflight/postflight verification, and externally protected decorative cells during execution. Director guards are not player/plugin permission enforcement.
- RCON success wording and effect merging are not yet verified for the new operations -> isolated Java 26.3 calibration and persisted response fixtures before accepting the dispatcher; unknown responses fail closed.
- Brief XP/effects can still affect progression/combat balance -> capped level-I durations, small fixed point bonuses, unchanged item rewards, no aura, and no new unlock shortcut. The numeric policy is a documented planning default.
- JSON credit ledger grows for the life of the world -> retain exact idempotency evidence and quantify save behavior during implementation; do not prune IDs or introduce another datastore in this change.
- Chunk/player blockers can postpone visible milestones -> expose earned versus installed rank and keep quests independent of ordinary blockers.
- Existing temples can have player edits or abandonment outcomes -> only supported exact baselines enroll; preserve edits and report blockers rather than clear terrain or change the binding.
- Block-built sculptures may not read as copper golems in-game -> client acceptance checks the silhouette from entrance/interior viewpoints; revise authored sculpture geometry within the same safe footprint if necessary.
- State/source rollback can misinterpret pending plans -> preserve paired world, quest JSON, optional SQLite, exact source/configuration/definition references; no code-only rollback over new pending operations.

## Migration Plan

### Implementation and isolated acceptance

1. Implement state/plan migration and rank policy without enabling it by default; keep existing offering and settlement regressions intact.
2. Author/validate the separate patch manifest against real bundled roots, including all cumulative ranks and intermediate prefixes in four rotations.
3. Exercise the frozen benefit plan and read-only CLI against isolated fixtures; run the standard unittest suite and existing admin help smoke.
4. Use a disposable vanilla Java 26.3 world containing a generated baseline temple, with an isolated quest state and exactly one writer. Do not modify or regenerate the designated deployment or unrelated family/test worlds.
5. Observe actual bonus-XP/effect/setblock acknowledgements, player-effect precedence, real guarded patches, chest/inventory preservation, duplicate-completion rejection, and save/restart persistence. Use deterministic candidate/API preparation with demo mode, not billable model calls. Verify actual personal and communal recipient behavior with a client; RCON-only evidence is insufficient for authenticated gameplay claims.
6. Use a client to inspect all milestone appearances, recognize both sculptures, traverse supported stairs in survival, and open the unchanged chest. Record exercised evidence and any unmet client-only checks separately.

### Separately authorized activation of an existing deployment

1. Ship reviewed implementation through the normal topic-branch PR workflow. No production activation is authorized by this planning request or its implementation checklist.
2. For a later authorized activation, stop the Keeper writer, take verified paired world/state/configuration backups using the established maintenance sequence, and inspect the real generated root, rotation, minimum corner, current chest, and decorative cells.
3. Install reviewed patch-definition copies and explicit opt-in binding without changing spawn, chest, seed, world identity, terrain, existing progression, settlement enablement, admission policy, or LLM configuration.
4. Run read-only status/preview with writer stopped and compare quest/SQLite checksums. Activation starts with zero credits and no automatic rank-1 reconstruction.
5. Start exactly one writer after acceptance. Python changes require a Keeper restart; restart Minecraft only when actually needed. Check effective binding and startup logs without printing secrets.

### Recovery and rollback

An ordinary preflight blocker needs no reset: retain progress and remove only an operator-verified obstruction if desired. An uncertain dispatch requires stopping writers, backing up the current matched generation, comparing exact blocks/inventory with saved intent and acknowledged progress, and explicit offline reconciliation of only that operation. Never erase credit IDs, pending debt, or change binding/digest to bypass it.

Rollback either restores the complete paired backed-up generation and matching source/configuration, or uses an explicitly reviewed state migration after proving no new mutations/debt remain. Do not run older code against new pending reward plans or mix a previous world with newer Keeper state. Retain all recovery snapshots.
