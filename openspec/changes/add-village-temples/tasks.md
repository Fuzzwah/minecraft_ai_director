# Tasks

## 1. Reproducible temple-bearing village assets

- [ ] 1.1 Start implementation in a feature worktree based on the pushed planning commit; verify its branch is not `main` and the reviewed proposal, both specs, and design are present.
- [ ] 1.2 Add standard-library asset authoring tooling with pinned Java 26.3 provenance and complete NBT support for the consumed vanilla templates; verify it reads the actual target archive and emits reproducible assets without needing the Director or a model request.
- [ ] 1.3 Author the 32 normal/abandoned root recipes with biome-appropriate roofed temples, an identifiable altar, preserved road joints, documented ancillary-connector adjustments, and explicit interior clearance; verify decoded blocks form supported floors and walkable paths from village connections to each altar.
- [ ] 1.4 Package `datapack/director_village_temples/` with exact 26.3 metadata and the five effective root pools, retaining vanilla placement, weights, processors, and projections; verify every effective root selection resolves to one temple-bearing root rather than an optional house.
- [ ] 1.5 Add deterministic unittest coverage alongside asset work for effective normal/abandoned selection boundaries, one temple per root, connector accessibility, room clearance, floor support, and all rotations; verify plausible missing-root and obstructed-entry defects are rejected by semantic checks of real NBT assets.
- [ ] 1.6 Document the authoring command, version/provenance, pack installation, conflicts, gameplay exclusions, and the unchanged 1.21.1 construction pack in README; verify the documented asset-generation command produces the inspected datapack.

## 2. Isolated Java 26.3 generation and persistence proof

- [ ] 2.1 Provision a uniquely named disposable Java 26.3 test world with the pack present before first generation, private RCON, and no collision with existing containers/ports; verify clean pack/registry/template startup while the Director is stopped.
- [ ] 2.2 Exercise controlled generation of all 32 effective roots using isolated fixtures plus natural villages in all five styles; verify actual generated altar, roof, entry clearance, road assembly, and normal/abandoned treatment, including uneven terrain and rotated roots.
- [ ] 2.3 Compare fixed-seed vanilla and packed-world village locations and styles; verify the village sites and placement behavior remain unchanged rather than merely comparing copied JSON fields.
- [ ] 2.4 Exercise installing the pack after an existing scratch village is generated; verify its blocks/player edits are untouched while a new village generates its mandatory temple.
- [ ] 2.5 Edit a generated scratch temple, save, unload/reload, and restart; verify the edit persists and no temple replay or duplication occurs.
- [ ] 2.6 Run `python3 -B -m unittest discover -v` and the asset checks after integration; verify new geometry/selection cases and existing settlement/quest behavior pass together.
- [ ] 2.7 Inspect temple rendering and player traversal with an ordinary Java 26.3 client when available; record screenshots/coordinates and actual outcomes, or explicitly report the unavailable client-only surface without claiming it was verified.
- [ ] 2.8 Record isolated generation evidence and verification limits in README; verify documentation distinguishes observed block/runtime behavior from client visual proof and remove disposable fixtures from the deployable pack.

## 3. Rehearsed regeneration and paired rollback procedure

- [ ] 3.1 Write the operator runbook in README for target/version/commit checks, explicit reset authorization, stopped-generation private snapshots, checksum verification, fresh replacement volume pairs, preserved server policy/secret references, explicit seed, and pre-generation pack installation; verify every step names only the designated live deployment or its disposable rehearsal equivalent.
- [ ] 3.2 Rehearse the runbook with disposable old/new volume pairs, including temporarily runtime-masking the auto-started Director during Minecraft-only acceptance; verify the old pair stays intact and no Director starts before new spawn/state are ready.
- [ ] 3.3 Rehearse fresh-state startup after deriving actual world spawn; verify no old player positions, active quest, pending debt, structure record, or initialization state is inherited and exactly one Director authenticates over private RCON.
- [ ] 3.4 Rehearse failed-backup, wrong-target/version, and rejected-pack gates; verify each stops cutover before the old generation is lost or the new world is accepted for normal play.
- [ ] 3.5 Rehearse paired rollback, restoring data/state references and spawn settings together before unmasking the companion; verify original world/player edits, quest state, authentication policy, and intended port return without mixed-generation records.
- [ ] 3.6 Update AGENTS and README with the rehearsed runbook, reset/player-progress consequences, rollback ownership, and the requirement to take a new backup after further play; verify these instructions agree with the actual service dependency behavior and rehearsal evidence.

## Workflow follow-up

- Review and integrate completed implementation through the existing shipping workflow; keep the live service attached to primary `main`, never the implementation worktree.
- After the reviewed merge and separate authorization acknowledging world/player-progress reset, execute the rehearsed live cutover on `10.1.1.232:25555`. Take a fresh matched snapshot; the previous pre-temple backup is not automatically current.
- Before normal play, verify the actual live enabled pack, naturally generated temple coordinates, Minecraft status, fresh Director ownership/RCON, and save/restart persistence; report any remaining client-only verification limit. Roll back the complete old generation if acceptance fails.
- Archive this change after implementation and the agreed deployment/review requirements are satisfied; synchronize the two capability specifications and preserve accurate verification evidence.
