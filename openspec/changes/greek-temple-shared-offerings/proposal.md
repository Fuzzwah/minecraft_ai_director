# Proposal

## Why

The current Keeper temple is a compact utility room and does not provide the
Greek-inspired landmark that made the village center memorable. The private
ender chest is also unnecessary because quest rewards are already delivered
straight to player inventories; using one shared offering chest simplifies the
world contract without removing private, target-only rewards.

## What Changes

- Replace the compact Keeper temple centerpiece with a recognizable Greek-inspired temple façade and interior while preserving vanilla village placement, jigsaw connectors, supported rotations, and biome-appropriate materials.
- Keep one integrated normal chest as the temple offering source; remove the generated ender chest from all normal and abandoned roots.
- Change private quests to consume offerings from the same configured normal chest as communal quests, while retaining target-only reward ownership.
- Preserve durable prepared/uncertain/completed consumption handling, direct inventory rewards, settlement rewards, and restart idempotency.
- Regenerate and validate all Java 26.3 normal and abandoned temple roots, including controlled rotations and saved-world persistence.
- Update the Java 26.3 live deployment copy and documentation only after backup, source-pack validation, and fresh-world verification.

## Capabilities

### New Capabilities

- `adaptive-offering-quests`: Shared chest submission for communal and private lanes with lane-specific reward ownership.

### Modified Capabilities

- `village-temple-generation`: Greek-inspired temple geometry and a single integrated normal offering chest without an ender chest.

## Non-Goals

- No change to vanilla village placement, biome eligibility, normal-versus-abandoned selection weights, or town-center connector topology.
- No player-inventory or arbitrary-chest submission fallback.
- No change to the direct `give`-based reward economy, configured reward validation, settlement reward idempotency, or LLM trust boundary.
- No support for Minecraft versions other than the verified Java 26.3 target.
- No retroactive conversion of already generated villages; the updated datapack applies only to newly generated village starts.
- No live-world deployment during proposal creation or implementation planning.
