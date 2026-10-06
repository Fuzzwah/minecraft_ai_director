# Design

## Context

The existing Java 26.3 village pack replaces all 32 effective town-center roots with small altar temples, but its asset tooling rejects all non-jigsaw block-entity payloads. The Director is a standard-library Python process with RCON access, a JSON quest state file, optional settlement SQLite state, and a read-only mount of the live Minecraft data volume. It currently stores one active quest, selects from a static item allow-list, and checks the named player's inventory near configured spawn.

The live deployment runs Java 26.3 on `10.1.1.232:25555`; the isolated settlement server is Java 1.21.1 and must not be used as evidence for the new generation behavior.

## Goals / Non-Goals

**Goals:**

- Make every newly generated Java 26.3 Keeper temple a usable quest hub with a normal communal offering chest and an ender-chest private submission path.
- Provide separate communal and private quest lifecycles with clear reward ownership and durable recovery.
- Start quests from observed local village supply, then expand through bounded progression bands for stronger players.
- Keep all model choices constrained to Python-owned candidates and preserve the existing no-command/no-coordinate trust boundary.
- Prove the complete behavior in an isolated Java 26.3 world before replacing the designated live world.

**Non-Goals:**

- Retrofitting containers into existing villages or scanning/adopting every village into settlement ownership.
- Protecting temples from player edits or making generated containers unbreakable.
- Adding mods, third-party Python packages, or changing the Java 1.21.1 construction pack.
- Treating the ender chest as a communal inventory or granting private rewards to anyone other than the target player.

## Decisions

### 1. Author two approved container positions in every root

Extend the existing deterministic authoring tool and manifest with a fixed local position for the Keeper offering chest and a fixed local position for the ender chest. Apply the same rotation transform used for altar and connector validation. The generated templates contain an empty normal chest and a normal ender chest; only those two block-entity types are permitted by the validator. Their positions must remain inside the authored room and outside road joints, entrance clearance, and altar approach.

The deployment records the transformed offering-chest coordinate for the spawn temple. The Director owns no arbitrary coordinate selection: it reads the configured/derived temple chest coordinate associated with the persisted world spawn, and rejects missing, unloaded, or inconsistent coordinates.

### 2. Use separate durable quest lanes

Replace the single active-quest field with a state model containing one communal quest and a map of private quests keyed by validated player name. Preserve a compatibility path for old state files by either migrating an old active quest into an explicitly recorded lane or refusing it safely with a clear operator error; never silently reinterpret a pending offering or reward.

The communal quest reads and consumes the public offering chest. A private quest reads and consumes the target player's `EnderItems` inventory through the Java 26.3 inventory interface. Inventory reads capture enough slot/item/count metadata to verify the intended state before mutation. Consumption is persisted as an intent before the first mutation and moves through prepared, uncertain, and completed states. A lost response protects the affected lane from replay until reconciled.

Communal completion snapshots the eligible online reward recipients and records one reward operation per recipient. Private completion records only the target player. Settlement XP and structure rewards continue through the existing idempotent pending-reward machinery.

### 3. Build a fail-closed supply and progression context

Add a read-only world probe that uses the mounted overworld region/chunk data and existing NBT codec conventions to inspect a bounded area around spawn after a server save boundary. It extracts supported block resources, generated container item stacks, and relevant nearby item entities. Parse errors, concurrent-file ambiguity, unloaded chunks, and stale or missing data mark the affected source unknown; unknown sources do not create availability.

Use RCON for live player and ender-chest data. The probe exposes only normalized item IDs, counts, and confidence/source categories to quest selection. It does not expose arbitrary NBT to the model and does not accept model-generated source locations.

Compute a bounded strength score in Python from server-observable experience, equipment, and progression-material signals. Define named bands in configuration: spawn-local, early, established, Nether/End, and endgame. Private selection uses the target score. Communal selection uses the arithmetic average of eligible online scores, with incomplete profiles treated conservatively rather than promoted.

The candidate catalog maps items to band, quantity bounds, and acceptable supply sources. Spawn-local communal candidates require observed local supply. Private local candidates may also use the target player's observed inventory or ender chest. Higher bands unlock configured materials when the strength threshold is met; they do not require those materials to already be in the temple. The LLM receives only the resulting candidate set, and deterministic fallback consumes the same set.

### 4. Keep reward and announcement semantics explicit

Announcements distinguish communal deposits in the Keeper offering chest from private deposits in the target player's ender chest. Communal completion rewards all eligible online players captured at completion; private completion rewards only the target. No quest completion uses a player's ordinary inventory as an implicit substitute for either lane.

### 5. Treat live regeneration as a separate deployment operation

After merge and isolated Java 26.3 acceptance, stop the Director before Minecraft, flush and snapshot the complete current server and Director volumes as a matched rollback pair, and record service/configuration state without exposing credentials. Create a replacement world with a new random seed, install the updated pack before first generation, and provision fresh Director JSON/SQLite state plus a new settlement world ID. Derive and inspect the nearest supported village and offering-chest coordinate, set and flush world spawn, then exercise both quest lanes before enabling normal play. Any uncertain container, state, or spawn result rejects the cutover and uses the matched rollback pair.

## Risks / Trade-offs

- **NBT block entities expand the template trust surface.** Permit only the two named container types, require empty chest contents, validate all positions and rotations, and reject every other payload.
- **Live Anvil files can be changing while the server runs.** Establish a save boundary, treat malformed or changing region data as unknown, and fail closed instead of guessing local availability.
- **Ender-chest mutation syntax and persistence are Java-version-sensitive.** Verify exact Java 26.3 commands in the isolated server before deployment; do not infer behavior from the Java 1.21.1 settlement server.
- **Two quest lanes increase state and reward failure modes.** Persist lane-specific intents and recipient operations before RCON mutation, retain uncertain records, and exercise restart/lost-response paths.
- **A new random seed resets all live terrain and player progress.** Preserve the complete matched rollback snapshot, use fresh world-specific state, and do not touch the isolated or unrelated family worlds.
