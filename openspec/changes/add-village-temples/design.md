# Design

## Context

See `proposal.md` for motivation and the two delta specifications for behavior. The live service uses a pinned vanilla Java 26.3 image, host port 25555, and source mounted from primary `main`; the Director shares its Minecraft network namespace. Its existing data/state volumes are separate from the older Java 1.21.1 settlement playtest.

Read-only inspection of `/data/versions/26.3/server-26.3.jar` established:

- Village starts use five `minecraft:village/<style>/town_centers` pools and `WORLD_SURFACE_WG`, with vanilla `beard_thin` terrain adaptation.
- Those pools reference **32** root templates: desert 6, plains 8, savanna 8, snowy 6, taiga 4. Half are abandoned variants. Existing root templates have no embedded entities, but contain jigsaw metadata for roads, villagers, animals, and decorations.
- Root horizontal dimensions range down to 7 by 7 blocks. Some roots use a different floor height; taiga meeting point 2 has roads at local y=2 instead of y=1.
- The target template palette uses **`id` and `properties`**, and its DataVersion is **5023**. Server metadata identifies datapack version **121.0** and protocol **777**.
- Vanilla village placement uses random spread, spacing 34, separation 8, and salt 10387312.

The existing `director_buildings` pack is format 48. `tests/support.py::read_template` is path-bound to that pack and implements only its limited NBT tags; it must not be assumed to decode arbitrary vanilla or 26.3 assets. The existing `keeper_shrine` is 3×3×4 and is not the roofed village temple specified here.

## Goals / Non-Goals

**Goals:** make the mandatory root itself contain the temple; preserve root connectivity and vanilla site selection; isolate generation assets from managed settlement construction; make asset output reproducible; make live cutover reversible.

**Non-goals:** any periodic village scanner, post-generation placement loop, automatic terrain clearing around player builds, or adoption of generated villages into the settlement database. The proposal lists gameplay exclusions, including player-edit protection and new turn-in locations.

## Decisions

### 1. A separate 26.3 generation datapack

Add `datapack/director_village_temples/`, leaving the 1.21.1 construction pack and its registry untouched. Package only the necessary town-center pools and replacement root templates; retain other vanilla roads, houses, village structure definitions, biome tags, and structure-set placement.

Use the exact 121.0 pack metadata accepted by Java 26.3, confirmed in the isolated runtime before deployment. Do not claim a broad version range or silently rewrite the old pack's compatibility metadata.

Alternative: upgrade the existing construction pack and settlement engine simultaneously. Rejected because that expands the change into a separate version migration and risks the existing playtest.

### 2. Cover every root selection, not weighted optional houses

Provide a temple-bearing template at each of the 32 vanilla root resource locations. Override the five town-center pool definitions only as needed to select those roots with the same entry ordering, weights, processor references, and projections. Use normal single-pool elements for authored roots requiring explicit interior air; legacy elements ignore template air and cannot alone establish room clearance.

The temple replaces or incorporates the center's decorative centerpiece. It is a compact roofed building with a consistent stone altar and biome-appropriate exterior, not an additional probabilistic child. Abandoned processors must retain an identifiable altar and usable entry. Do not put Keeper temples into optional house pools, which would allow zero or multiple copies.

The 32-way mapping is explicit. Keep each root's original horizontal footprint and ground anchor; grow vertical size only as required by the roof. Preserve road-jigsaw positions, orientations, names, targets, pools, and final states. Provide paths from those connectors to the entrance. Preserve ancillary spawn/decor connector behavior; where its old position conflicts with the new room, relocate that connector within the same root to a safe, documented open position rather than deleting it or changing its pool. No new embedded entities, inventories, loot, or block-entity payloads are added; required vanilla jigsaw metadata remains trusted generation metadata, not a model input.

Alternative: add a temple entry to each houses pool. Rejected because selection and space exhaustion cannot guarantee one per village. An independent temple structure sharing the village placement salt is also insufficient to guarantee attachment to the selected village root.

### 3. Deterministic asset authoring and semantic verification

Add a standard-library development tool under `tools/` to read the exact vanilla 26.3 server archive and emit the authored datapack. Record its input version/checksum and a per-root authoring manifest with temple/altar bounds, floor height, entry, and connector adjustments. Commit generated NBT assets and the authoring recipes; do not commit the Mojang server archive. Generation is a development operation, not a runtime dependency.

Keep NBT encoding/decoding in asset/test tooling rather than the Director loop. Reuse the existing unittest style and extend test helpers only where required to inspect the actual new assets, retaining old template tests unchanged. Decode generated assets and test meaningful geometry: one altar-bearing temple per selectable root, walkable entrance/interior, contained blocks, supported floor, all four rotations, and usable road connections. Exercise selection boundaries that cover rare abandoned entries. Do not substitute identical-file or JSON-wiring assertions for those behaviors.

Rehearse on a separate disposable Java 26.3 world: natural villages in all five styles plus controlled root-selection fixtures covering all 32 templates, uneven terrain, rotation, save/restart, and edits that must not be replayed. The fixtures exist only in the isolated test workspace, not the live pack. Compare vanilla village location results at fixed seeds. Real block/structure inspection is required; mocked RCON proves neither generation nor rendering. Record a standard client's visual/accessibility review when available, and label its absence explicitly.

### 4. Separate world-generation ownership from Director ownership

Generation is entirely Minecraft's responsibility. Keep the Director, current quest turn-in behavior, and settlement enablement unchanged. Generated temples are not recorded as owned settlement buildings and are not eligible for Director upgrade/removal merely because the template resembles a managed shrine. No new model prompt, billable call, global village registry, or runtime scan is needed.

### 5. A paired replacement generation, with old volumes retained

Use a documented operator runbook rather than a new general-purpose deployment framework. After implementation is reviewed, merged, and deployed from primary `main`, create a fresh data/state volume pair for this generation and update only the designated live Quadlet volume references. Keep the previous pair intact as well as taking a fresh stopped-generation archive snapshot. This avoids deleting the sole rollback copy and makes paired rollback explicit.

Preserve server policy/configuration and administrative allowlists, not old terrain, world-local player data, quest debt, or settlement records. Reuse existing private environment files and Podman secret references without placing their contents in the repository. Default to current seed **-4643071103847636909**, set it explicitly for new-world creation, and preserve existing survival/authentication settings. A different seed requires an operator decision.

The world reset includes player progress; approval of the proposal is not a live-cutover command. The operator must acknowledge that reset when authorizing deployment. No player-data migration is included.

The current server unit wants the Director unit, so starting Minecraft normally
also starts the companion. During server-only acceptance, runtime-mask the
Director service before starting Minecraft and verify it remains inactive.
Unmask it only after fresh state and spawn settings are ready, or after restoring
the complete old generation during rollback. This is a temporary cutover control,
not a permanent change to normal service dependencies.

## Risks / Trade-offs

- **Town-center footprint and connection collisions** → Per-root recipes keep original X/Z bounds, preserve boundary road connectors, and test walkability rather than enlarging a generic overlay that swallows jigsaw exits.
- **Legacy air handling or abandoned processors block a temple** → Author explicit room clearance with appropriate pool-element semantics and inspect actual generated normal/abandoned roots; do not rely on the NBT file alone.
- **A missed rare root breaks the every-village guarantee** → Cover all 32 effective root selections, including abandoned boundaries, in semantic asset checks and controlled runtime generation.
- **26.3 schema differs from the existing pack** → Pin version/provenance, use the observed palette schema, and require clean 26.3 startup and actual generation before acceptance.
- **Keeping the seed keeps the mountain at spawn** → This change does not flatten terrain or promise a spawn temple. Record actual new spawn and a nearby temple's coordinates for playtesters.
- **Player builds/progress are reset** → Separate deployment approval, current matched backups, retained old volume pair, and explicit rollback. Do not carry old quest/building state into new terrain.
- **Other packs overriding town centers can invalidate coverage** → Declare the conflict, inspect the enabled stack, and reject live acceptance if effective village starts do not contain the authored roots; do not promise arbitrary worldgen-pack interoperability.
- **No player protection is supplied** → Describe temples as generated buildings, not protected zones. A separate proposal is required for edit protection or a protected spawn village.

## Migration Plan

1. Review these artifacts; push planning on `main`. Create/synchronize a feature worktree from that planning commit and run `/opsx-apply` there only. Implementation and task-progress changes stay on the feature branch.
2. Build and verify the pack in isolated Java 26.3 worlds. Rehearse cutover and paired rollback with disposable volume pairs. Update README/AGENTS operational references as part of implementation, then integrate reviewed implementation through the existing shipping workflow.
3. Before live cutover, verify designated container/service identity, source commit, effective generation pack, access policy, seed, and volume mappings. Obtain explicit authorization covering world and player-progress reset.
4. Stop the Director, flush the world, stop Minecraft, and take a fresh complete data/state snapshot under `/home/fuz/mc-ai-director-backups/`. Check archive contents/checksums, protect snapshot permissions, and save the prior Quadlet references and spawn settings in private rollback metadata. The earlier pre-temple snapshot is historical evidence, not a substitute for a current backup.
5. Create the replacement data/state volumes. Preserve server settings and administrative access files without copying `world/` or its player data. Pre-create the configured level directory with the new pack in its `datapacks/` directory, and ensure it is enabled for the first generation. Apply the explicit seed and switch both services' volume references as one offline cutover.
6. Runtime-mask the companion service to inhibit its existing automatic start dependency, then start Minecraft alone. Keep normal player access gated during acceptance, verify enabled pack/startup logs, locate a naturally generated village, and inspect its temple. Save/restart and check persistence. Restore the normal access policy only after acceptance.
7. Read actual spawn from the new world's metadata and update Director spawn settings. Unmask and start exactly one Director against the fresh state, verify authenticated RCON and persistent-state ownership, and record connection/version plus a temple's coordinates. Leave settlement construction disabled unless separately configured and approved.
8. If checks fail, stop writers and Minecraft; restore the previous data/state pair and deployment/spawn settings together before unmasking the companion. Verify the original seed/state and private RCON on port 25555 before resuming play. Retain failed-generation evidence privately rather than deleting or mixing it into old state.
