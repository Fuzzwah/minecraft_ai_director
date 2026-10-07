# Tasks

## 1. Generate the Greek-inspired temple assets

- [x] 1.1 Extend `tools/village_temples.py` and its recipe/palette inputs with a deterministic Greek-inspired composition: stepped foundation, entrance, column rhythm, open interior, altar, and pediment/roofline for every trusted root footprint.
- [x] 1.2 Regenerate all 32 Java 26.3 normal and abandoned root assets and manifest metadata, preserving source sizes, anchors, road jigsaws, connector adjustments, processors, and all four rotations.
- [x] 1.3 Remove generated ender-chest blocks and payloads from every root; retain exactly one empty normal offering chest per root at a reachable trusted position.
- [x] 1.4 Update the temple validator and `tests/test_village_temples.py` to assert Greek structural identity, biome palette rules, supported floors, clear entrances, road connectivity, single-chest/no-ender invariants, processor safety, and stable real-NBT geometry.

## 2. Move all offering submissions to the shared chest

- [x] 2.1 Change private quest creation, source inspection, announcements, and consumption commands to use the configured normal offering chest while preserving target-only private reward recipients.
- [x] 2.2 Migrate persisted private quests with `submission == "ender_chest"` to the shared chest without reading, consuming, or rewarding from legacy ender inventories; preserve IDs, targets, reward debt, and uncertainty state.
- [x] 2.3 Extend `tests/test_director.py` and test support coverage for shared-chest private completion, target-only rewards, ender-chest non-completion, legacy migration, restart idempotency, inventory fingerprint changes, and lost-response uncertainty.
- [x] 2.4 Update `README.md` and `AGENTS.md` so the temple contract documents one normal offering chest and removes ender-chest submission instructions without weakening direct reward or persistence safety rules.

## 3. Validate and deploy the changed surface

- [x] 3.1 Run `python3 -B -m unittest discover -v`, `python3 -B tools/village_temples.py --check`, `python3 -B settlement_admin.py --help`, `openspec validate --all --strict --no-interactive`, and `git diff --check`.
- [x] 3.2 Run a disposable Java 26.3 acceptance world with the revised datapack installed before generation; verify natural normal and abandoned villages, Greek structure geometry, one empty chest, no ender chest, all rotations, RCON version/data-pack loading, and save/restart persistence.
- [ ] 3.3 For the designated live Java 26.3 world only, stop writers, create a matching world/state rollback snapshot, install the revised datapack before fresh generation, provision fresh Director state, configure the selected offering chest, recompute spawn, and verify Director/RCON/state persistence before normal play.
- [x] 3.4 Attempt authenticated Minecraft-client visual verification of the Greek temple; if client authentication or rendering cannot be exercised, record that limitation and retain server/NBT evidence without claiming visual success.
