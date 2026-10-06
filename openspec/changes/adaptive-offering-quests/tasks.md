# Tasks

## 1. Temple container assets

- [x] 1.1 Extend the Java 26.3 village-temple authoring tool and manifest to place one empty Keeper offering chest and one ender chest at documented local positions in every one of the 32 effective normal and abandoned town-center roots.
- [x] 1.2 Update template validation to permit only those two approved container block entities, reject all other block-entity/entity payloads, and verify container positions, entrance clearance, altar approach, floor support, road joints, and all four rotations.
- [x] 1.3 Regenerate the committed temple NBT assets and pack metadata from the pinned Java 26.3 source archive; verify deterministic output and no changes to village placement pools or the Java 1.21.1 construction pack.
- [x] 1.4 Add asset tests proving every root has exactly one reachable offering chest and one reachable ender chest, an empty initial offering inventory, a valid roof/altar/entry, and no unauthorized payload.

## 2. Supply observation and strength scoring

- [x] 2.1 Define Python-owned quest catalogs, quantity bounds, supply-source categories, progression bands, score thresholds, and communal/private configuration without allowing model-authored IDs or scores.
- [x] 2.2 Implement a standard-library Anvil/chunk observation path using the mounted world data and existing NBT codec conventions; inspect bounded spawn-village blocks, generated containers, nearby item entities, player inventories, and ender-chest contents while treating parse, freshness, and loaded-chunk uncertainty as unavailable.
- [x] 2.3 Implement bounded online-player strength profiles from Java 26.3 RCON-observable experience, equipment, and progression materials; compute private scores per target and communal difficulty from the documented eligible-player average.
- [x] 2.4 Implement lane-specific candidate filtering: observed spawn-village supply for local communal quests, target-player supply for local private quests, and progression-gated early/established/Nether/End/endgame pools for stronger players.

## 3. Quest state and inventory transactions

- [x] 3.1 Replace the single active quest state with one durable communal quest and a validated private-quest map, preserving safe legacy-state handling and restart/idempotency semantics.
- [x] 3.2 Add configured spawn-temple offering-chest discovery/validation and Java 26.3 ender-chest inventory probes; reject missing, unloaded, changed, or ambiguous source inventories without guessing coordinates.
- [x] 3.3 Implement prepared/uncertain/completed offering-consumption intents that remove only the requested item and quantity, preserve unrelated slots and metadata, and never replay an ambiguous RCON mutation.
- [x] 3.4 Update communal/private scheduling, announcements, completion detection, and reward ownership: communal chest completion rewards all eligible online players once; private ender-chest completion rewards only its target once.
- [x] 3.5 Constrain both LLM and deterministic fallback generation to the same filtered candidate set and decline a lane when no safe candidate exists; remove direct player-inventory completion as an implicit fallback.

## 4. Regression and failure-path verification

- [x] 4.1 Add deterministic unit coverage for local pumpkin-versus-carrot filtering, progression-band boundaries, communal average versus private target scoring, empty candidate sets, malformed model responses, and legacy state loading.
- [x] 4.2 Add transaction tests for normal chest and ender-chest exact consumption, unrelated-slot preservation, all-online communal rewards, target-only private rewards, restart recovery, lost RCON responses, and no duplicate reward/consumption.
- [x] 4.3 Run `python3 -B -m unittest discover -v` and the temple asset checks; retain only tests that prove observable behavior, boundaries, ownership, persistence, and failure handling.

## 5. Isolated Java 26.3 acceptance

- [x] 5.1 Provision a uniquely named disposable Java 26.3 test world with the updated pack installed before first generation, private RCON, and no collision with the existing 1.21.1 settlement test server.
- [x] 5.2 Generate natural supported villages and controlled root cases; inspect actual blocks and inventories to prove both containers, empty offering state, reachable entrance/altar, road connectivity, rotation, save/restart persistence, and no duplicate/replayed generation.
- [x] 5.3 Smoke the Director against the isolated Java 26.3 server: real RCON proved supply filtering, bounded-strength uncertainty, and exact offering consumption; deterministic tests proved communal/private ownership and restart/uncertain handling. Client-player reward flow remained unavailable because the cached client authentication returned HTTP 401.
- [x] 5.4 Exercise a standard Java 26.3 client when available to verify players can enter temples, open both containers, and use the offering workflow; record any client-only verification limit explicitly. (Client launch reached Java 26.3 but cached authentication returned HTTP 401; no client workflow was verified.)

## 6. Reviewed live cutover

- [x] 6.1 Update README.md and AGENTS.md with the offering-chest/ender-chest contract, adaptive quest behavior, new-seed reset warning, Java-version boundaries, backup/rollback sequence, and verification evidence.
- [ ] 6.2 Stop live Director writers in the required order, flush Minecraft, and preserve a fresh complete matched snapshot of the designated live server and Director volumes without touching unrelated worlds or exposing credentials.
- [ ] 6.3 Create the replacement live world with a new random seed, install and enable the verified pack before first generation, and provision fresh quest state, settlement database, and world identity.
- [ ] 6.4 Derive the nearest supported village from the recorded original spawn, inspect a safe surface and transformed offering-chest coordinate, set and flush world spawn, then start services in the required order.
- [ ] 6.5 Verify live pack enablement, generated temple containers, chest/ender-chest boundaries, Director startup, communal/private quest smoke behavior, save/restart persistence, and zero uncertain operations before opening the world for normal play.
- [ ] 6.6 If any acceptance check fails or state is uncertain, stop writers and roll back the complete matched world/Director snapshot rather than retrying construction or mixing old state with new terrain.
