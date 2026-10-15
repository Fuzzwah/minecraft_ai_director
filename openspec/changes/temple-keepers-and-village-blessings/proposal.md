# Proposal

## Why

Temples currently share one global Keeper, quest hub, and offering chest; villagers do not participate. Give each loaded temple a distinct altar presence whose player and NPC quests support a healthier local village without consuming essential village resources.

## What Changes

- Discover and verify every loaded generated Keeper temple, preserving its altar, chest contents, and player edits. Persist one named Keeper identity per temple; no physical Keeper entity is spawned.
- Introduce the Keeper on a player's first temple entry, persist membership, and attempt safe communal and personal assignments. Missing candidates defer issuance rather than inventing resources.
- **BREAKING:** Scope communal quests, personal quests, warm-up progress, cooldowns, and chest-item reservations to the issuing Keeper. A player's quests from different Keepers coexist.
- **BREAKING:** Accept player offerings only in the issuing Keeper's own normal chest, not at other temples. Communal rewards go to eligible online players who have met that Keeper; personal rewards remain target-only.
- Preserve exact source ownership and existing prepared/uncertain/completed transaction protection across migration, unloading, and restarts.
- Add independent NPC quests using actual possessed food and approved profession-related goods, protected nutrition/working reserves, natural altar visits, and reward-secured sacrifices. NPC goods never enter player quest accounting.
- Make successful NPC exchanges nutrition-positive: compensate the donor first and distribute bounded surplus to low-stock villagers with capacity. Provide modest unconditional assistance when no safe surplus exists.
- Let both player and NPC completions earn bounded local healing, protective blessings, and a defensive ward that weakens or slows approved hostile mobs.
- Report a missing or invalid designated chest and suspend only its temple. Never repair, replace, clear, or relocate blocks automatically; never force-load chunks.

### Non-goals

No runtime implementation in this planning PR, physical Keeper NPCs, custom client/resource pack, server mods, new Python dependencies, automatic temple reconstruction, world regeneration, terrain replacement, cross-temple completion, golem spawning, invulnerability, failure penalties, or implicit billable model calls. Existing optional settlement construction and its world identity remain independent.

## Capabilities

### New Capabilities

- `temple-keepers`: Verified loaded-temple discovery, persistent altar identities, first-entry membership, local presentation, and report/suspend lifecycle.
- `adaptive-offering-quests`: Keeper-owned player quest lanes, issuer-only chest transactions, per-Keeper progression, and membership-based communal rewards. This path is already used by earlier change deltas but has not yet been promoted into the main spec inventory; this change captures the current operating contract plus the explicit Keeper-scoping cutover, rather than creating a competing player-quest capability.
- `villager-offerings`: Independent, actual-inventory NPC quests; protected working reserves; safe altar sacrifice; donor compensation; surplus distribution; and unconditional recovery assistance.
- `village-blessings`: Bounded local healing, protection, and defensive wards funded by player and NPC completions.

### Modified Capabilities

None. `village-temple-generation` already guarantees one usable chest in generated assets. Its geometry, generation independence, and preservation of player edits remain unchanged; runtime chest verification belongs to `temple-keepers`.

## Impact

- `director.py`: Replace global quest/source assumptions in `State`, `Quest`, `PendingReward`, scheduling, announcements, membership/recipient selection, and persistence with Keeper-owned records and explicit durable sources. Remove obsolete runtime paths after a safe migration.
- `quest_supply.py`: Reuse bounded, fail-closed Anvil observation and inventory parsing; evaluate player supply around the issuing temple rather than the single spawn hub. Saved entity data is not sufficient authorization to mutate a live villager.
- New focused standard-library runtime modules and, if proven necessary, a Java 26.3 function datapack for server-side NPC movement/exchanges and effects. These are implementation targets, not assets created by this PR.
- Existing temple manifest/NBT in `datapack/director_village_temples` and `tools/village_temples.py`: reuse trusted geometry, rotations, altar, and chest offsets for identification; do not change generated terrain.
- `tests/test_director.py`, `tests/support.py`, and focused behavioral coverage for temple ownership, NPC reserve boundaries, uncertainty recovery, ward targeting, and restart persistence.
- `README.md`: Update operating, configuration, backup, migration, suspension, and reconciliation contracts during implementation.
- Durable quest JSON changes require a backed-up migration. Existing SQLite, optional settlement integration, the matching world, and unresolved operations must be preserved.
- Implementation requires disposable Java 26.3 server proof of discovery, guarded inventory exchange, movement, effects, and restart behavior, plus client proof of first-entry dialogue and altar rituals. Live deployment is a separately authorized, backed-up update, not part of this PR.
