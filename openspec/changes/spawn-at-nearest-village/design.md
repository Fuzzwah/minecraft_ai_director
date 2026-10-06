# Design

## Context

See `proposal.md`. The live Java 26.3 world was regenerated with the village
temple datapack, but its persisted world spawn remained `[0, 72, 0]` while the
nearest taiga village is at `[112, ~, 32]`. The generation pack controls village
pieces, not the world's spawn metadata, and vanilla generation does not
retroactively move world spawn.

## Goals / Non-Goals

**Goals:**

- Make the nearest supported village discoverable from the default world spawn
  after a controlled regeneration.
- Keep the operation explicit, inspectable, and safe for a persistent world.
- Apply the already-authorized one-time correction to the current live world.

**Non-Goals:**

- No village placement, frequency, template, or datapack changes.
- No relocation of beds, respawn anchors, player positions, or settlement plots.
- No automatic spawn relocation in arbitrary existing worlds or unrelated
  Minecraft deployments.
- No terrain clearing, block replacement, or forced chunk generation as a
  fallback for an unsafe target.

## Decisions

1. **Use an explicit post-generation operation, not a template change.**
   After the replacement world first generates, query the five supported
   `minecraft:village_*` structure types from the recorded original spawn and
   choose the smallest horizontal distance. This preserves vanilla generation
   and works with the actual seed and terrain.

2. **Validate the target before mutation.**
   Load the selected village column, inspect the support block and clear player
   space, and reject uncertain or obstructed targets. For the current world,
   `[112, 71, 32]` is `minecraft:smooth_stone` and `[112, 72, 32]` is air, so
   `[112, 72, 32]` is the verified target.

3. **Persist the world spawn without changing quest coordinates.**
   Apply `/setworldspawn <x> <y> <z>`, flush the world, and verify level metadata
   and RCON after save/restart before opening the world for normal play. The
   Director's quest/turn-in spawn configuration remains a separate contract and
   is not changed by this feature.

4. **Keep the operation idempotent and scoped.**
   Run it only for the designated live Java 26.3 world after the required
   stopped-generation rollback snapshot. Never use it to overwrite an uncertain
   world, repair an unrelated server, or attach old Director state to new terrain.

5. **Keep player-specific respawn semantics unchanged.**
   World spawn is only the default for players without a valid bed or respawn
   anchor. The runbook must not clear or rewrite player respawn data.

## Risks / Trade-offs

- Structure locate output and safe-surface inspection require a reachable Java
  26.3 server with the relevant chunks loaded; a failed or localized response
  must stop acceptance rather than guess coordinates.
- The nearest village may be on uneven terrain or have a blocked anchor, so the
  safe target can differ from the locate marker and must be recorded.
- This is an operator-controlled deployment step rather than an automatic
  per-world hook. That avoids hidden world mutation and preserves fail-closed
  recovery, at the cost of requiring explicit regeneration checklist execution.
