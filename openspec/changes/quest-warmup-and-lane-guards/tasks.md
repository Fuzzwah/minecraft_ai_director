# Tasks

## 1. Accurate nearby harvestable supply

- [x] 1.1 Replace section-total resource evidence in `quest_supply.py` with validated positional Java 26.3 block-state decoding, including mixed supported palette representations, padded-word boundaries, single-state sections, negative coordinates, truncation, and invalid indices; verify isolated decoded-position regressions and agreement with saved Java 26.3 chunks.
- [x] 1.2 Filter block/container/drop evidence by the actual horizontal radius and surface harvestability; count mature crops and conservative yields, exclude whole-melon false supply and building-log warm-up requests, and reject incomplete/unstable/unloaded observations; verify age, radius-edge, insufficient-yield, buried-resource, and changing-file cases in isolated supply tests.
- [x] 1.3 Document the 32-block warm-up evidence, maturity/yield rules, and fail-closed behavior in README's adaptive-offerings section; verify examples agree with the tested nearby-wheat/pumpkin/no-carrot scenario and distinguish later wider observations.

## 2. Durable warm-up state and completion transitions

- [x] 2.1 Add communal/per-player warm-up completion counts, personal post-warm-up issued sequence, and quest policy/mode/reference metadata to JSON state with conservative legacy defaults and strict invalid-field handling; verify round-trip and legacy-load regressions preserve quest IDs, targets, pending commands, fingerprints, debt, and uncertainty.
- [x] 2.2 Credit each lane only when all consumption/reward obligations finish, atomically with pending-record removal; run recovery with settlements disabled as well as enabled; verify failed/uncertain/dry-run operations do not advance warm-up and restart recovery credits a quest exactly once.
- [x] 2.3 Document first-three-completion semantics, independent player progress, conservative legacy defaults, and no-reset migration in README; verify the described third-completion/fourth-assignment boundary against transition tests.

## 3. Conflict-free easy openings and personal goals

- [x] 3.1 Apply warm-up before progression filtering, using local evidence only and catalog-minimum quantities backed by yield; pass identical constrained candidates to LLM validation and fallback; verify novice/high-score openings, no inventory-only locality bypass, quantity rejection, and empty-set deferral.
- [x] 3.2 Derive reservations from active communal, personal/legacy, offline-target, and pending records; enforce them on generation, model acceptance, and before consumption, updating the set between same-cycle assignments; verify personal-to-communal and communal-to-personal conflicts, multiple players, stale model results, uncertain reservations, and restart behavior.
- [x] 3.3 Implement creation-time personal reference bands, normal one-band-above goals, every-fifth issued aspirational preference, progression/confidence ceilings, and deferral without sequence advancement; verify mixed-player groups, aspiration fallback, band ceilings, and stable assigned goals after membership changes.
- [x] 3.4 Announce communal work to the group and personal warm-up/long-term/aspirational work to its target with the shared normal chest; document conflict deferral and hybrid progression in README and relevant AGENTS safety guidance; verify generated announcement output through a throwaway scenario and keep existing ownership/transaction regressions unchanged.

## 4. Safe handling of existing active quests

- [x] 4.1 Before consuming old-policy active quests, revalidate with reliable supply and retire only untouched policy-invalid or later duplicate assignments using pending-first/communal-first precedence; preserve uncertain or pending operations and suspend on unknown evidence; verify the existing unavailable-carrot replacement scenario, duplicate legacy quests, no retirement reward/consumption, and revalidation that does not repeat after normal harvesting.
- [x] 4.2 Document the backed-up in-place upgrade, invalid-quest explanations, pending-operation protection, and rollback boundary; verify migration on a disposable copy of quest state leaves unrelated chest contents, building/world identity, and durable recovery records intact.

## 5. Integrated verification and designated-world rollout

- [x] 5.1 Run `python3 -B -m unittest discover -v`, `python3 -B tools/village_temples.py --check`, `python3 -B settlement_admin.py --help`, `openspec validate --all --strict --no-interactive`, and `git diff --check`; record actual results and confirm no datapack/template or settlement-geometry changes.
- [x] 5.2 Smoke real Java 26.3 supply and quest selection in a disposable acceptance environment without billable model calls: compare mature wheat/pumpkin/absent-carrot positions against independent read-only RCON checks, exercise same-cycle lane reservations and completion/warm-up persistence across restart, and record output proving the path rather than relying solely on mocked tests.
- [ ] 5.3 After reviewed shipping, stop the single Director writer on the designated current Podman deployment and create a matched world/config/JSON/SQLite backup; synchronize reviewed primary source, preserve village/chest coordinates and world identity, preview local candidates read-only, then observe safe existing-quest migration and service/state persistence; verify no terrain regeneration, no state reset, no billable acceptance calls, and no uncertain mutation replay.
- [x] 5.4 Attempt authenticated client verification that opening resources are genuinely easy to reach and harvest near the village and announcements distinguish communal/personal goals; record any client limitation without claiming visual or walking-access proof from RCON alone, and update README with only exercised acceptance evidence.

## Workflow follow-up

- Review the proposal before apply; synchronize the implementation worktree with the published planning commit.
- Sync/archive the existing adaptive/shared-chest deltas and this additive delta in reviewed dependency order; keep the shared normal-chest contract rather than resurrecting historical ender-chest instructions.
