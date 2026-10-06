# Proposal

## Why

Playtesters want more Keeper temples to discover while exploring, but the live server currently generates only vanilla structures and world spawn is not a prepared settlement. Attaching temples to Minecraft's existing village generation gives them natural locations without an LLM choosing construction coordinates or a runtime process carving up occupied villages.

## What Changes

- Add a vanilla-server datapack targeting **Minecraft Java 26.3** that includes exactly one recognizable Keeper temple in every newly generated village: plains, desert, savanna, snowy, and taiga, including abandoned variants.
- Make the temple part of the mandatory village town-center template, not an optional weighted house. Retain vanilla village placement, biome selection, roads, and normal/abandoned selection.
- Give temples an accessible entrance, roof, and recognizable altar with biome-appropriate materials. Keep them independent of Director-managed construction, quest rewards, and settlement initialization.
- **BREAKING:** Regenerate the long-lived live world on **`10.1.1.232:25555`** when the feature is verified and deployed. This replaces terrain, builds, and world-local player progress; the old generation survives only in rollback storage. Preserve a fresh, matched world/Director-state snapshot, install generation assets before the replacement world's first generation, and start with fresh world-specific Director state.
- Keep the current seed as the deployment default so comparisons are reproducible. Recompute actual spawn coordinates; do not reuse the old Director spawn settings blindly.
- Implement in a feature worktree only after review; deploy merged, reviewed code from the primary `main` checkout.

**Non-goals:** retrofitting existing villages; increasing village frequency; guaranteeing a temple at world spawn; flattening the mountain; player block-edit protection; changing quest turn-in locations; enabling the settlement engine; upgrading the separate Java 1.21.1 construction datapack; adding server mods or client dependencies. A protected playable village is separate work, not an implicit result of this datapack.

## Capabilities

### New Capabilities

- `village-temple-generation`: Mandatory, terrain-integrated Keeper temples in newly generated vanilla villages while retaining vanilla placement and village connectivity.
- `live-world-regeneration`: Version-checked, backed-up replacement of the designated live world and its matching Director state, with acceptance checks and paired rollback.

### Modified Capabilities

None. The project currently has no accepted OpenSpec capability specifications.

## Impact

- New generation assets under `datapack/director_village_temples/`; the existing `datapack/director_buildings/` remains unchanged for Java 1.21–1.21.1.
- Deterministic standard-library asset tooling and consumer-visible NBT/geometry regression coverage, reusing existing test conventions where compatible.
- Live deployment documentation, a rehearsed regeneration procedure, and the existing user-systemd Quadlets outside the repository. Host port **25555**, private RCON, and other Minecraft worlds remain unchanged.
- No external LLM calls, new Python runtime dependencies, or changes to quest/reward behavior are required.
