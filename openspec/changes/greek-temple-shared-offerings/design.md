# Design

## Context

The current Java 26.3 generation pack transforms vanilla town-center roots into
small roofed rooms with an altar, a normal chest, and an ender chest. The root
assets vary substantially in footprint and connector height, and the generator
already validates jigsaws, terrain support, rotations, processors, block
entities, and container payloads. The Director currently models
`offering_chest` and `ender_chest` as separate submission sources even though
vanilla rewards are already sent directly to players with validated `give`
commands.

See `proposal.md` for motivation and user-visible scope.

## Goals / Non-Goals

**Goals:**

- Produce a visibly Greek-inspired temple in every trusted Java 26.3 normal and
  abandoned town-center root without changing village placement or connectors.
- Keep one normal chest as the only offering source for both quest lanes.
- Preserve private target-only reward ownership, durable consumption intent, and
  uncertain-operation recovery.
- Make generated NBT, manifest metadata, validator checks, and runtime behavior
  agree exactly.

**Non-Goals:**

- No support for Java versions other than 26.3.
- No retroactive editing of already generated villages.
- No new Minecraft entities, arbitrary block entities, player-inventory
  submission fallback, or model-authored coordinates/items/rewards.
- No change to direct inventory reward commands or settlement reward semantics.

## Decisions

### Greek temple geometry is generated from trusted vanilla roots

Extend the existing root transformation tool rather than hand-editing only the
currently selected taiga structure. For each root, retain its original size,
anchor, road jigsaws, processor metadata, and approved connector adjustments.
Generate a deterministic temple composition inside the existing root bounds:

- supported stone or biome-appropriate foundation and approach stairs;
- a front colonnade with a consistent column rhythm;
- an open entrance and traversable interior;
- an architrave and pediment/roofline silhouette;
- a centered, visible Keeper altar;
- one normal chest in a trusted interior location.

Use a palette family per village style so desert, plains, savanna, snowy, and
taiga temples remain visually coherent with their surroundings. Abandoned roots
use the same structural silhouette and retain only processor-safe weathering.
The validator checks the structural identity and walkable paths in all four
rotations instead of asserting one incidental block arrangement.

The generator writes the full trusted manifest and compressed NBT assets. The
manifest records one chest position per root and no ender-chest position.

### Use one canonical offering source

Change private quest creation and validation to set the same canonical
`offering_chest` submission source used by communal quests. Source inspection,
fingerprinting, consumption command generation, and announcement text all use
the configured loaded normal chest. Recipient calculation remains lane-specific:
communal quests snapshot eligible online recipients, while private quests retain
only their validated target.

No reward path changes: after successful offering consumption, the existing
idempotent reward transaction sends direct inventory rewards and experience to
those recipients.

### Migrate legacy quest state on load

When loading persisted state, rewrite private quests with
`submission == "ender_chest"` to `submission == "offering_chest"` while
preserving quest ID, target, item, quantity, reward data, candidate metadata,
and pending uncertainty fields. The migration performs no RCON reads or writes
and never consumes legacy ender inventory. Subsequent completion requires the
configured normal chest.

### Separate repository assets from live deployment

Implementation changes remain in repository source, tests, generator inputs,
and documentation. Deployment is a separate apply task:

1. run unit, generator, OpenSpec, and disposable Java 26.3 checks;
2. stop the live Director writer before changing world/state copies;
3. create a matching world/state rollback snapshot;
4. install the revised datapack before regenerating only the designated live
   Java 26.3 world;
5. provision fresh quest state for the replacement terrain;
6. locate and inspect the selected village, configure its chest coordinates,
   recompute and persist spawn, then start the Director;
7. verify RCON, generated chest contents, no ender chest, persistence, and
   recovery boundaries before normal play.

The settlement Java 1.21.1 test server and unrelated family worlds are not
valid deployment targets for this pack and remain unchanged.

## Risks / Trade-offs

- Root footprints and terrain adaptations differ, so a single decorative
  template cannot be copied blindly. Per-root generation and all-rotation
  validation increase asset churn but preserve the vanilla connector contract.
- A larger Greek silhouette may reduce decorative detail in the smallest roots;
  connector preservation and walkability take precedence over ornament density.
- Migrating legacy private quests changes where players must deposit pending
  offerings. The migration is explicit and non-mutating to avoid consuming an
  ender inventory under the old contract.
- Installing the revised pack does not alter existing village chunks. A fresh
  live-world generation is required for visual verification; the rollback pair
  remains the recovery path if generation, spawn, container, or Director checks
  fail.
- A Minecraft client is required for visual confirmation. Server/RCON and NBT
  checks can prove geometry and state but cannot prove rendered appearance.
