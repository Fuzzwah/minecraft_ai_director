# Proposal

## Why

The regenerated live world now contains a Keeper temple in the nearest taiga
village, but the world spawn remains at the original terrain spawn, 116 blocks
away. Players joining without a bed or anchor therefore start away from the
feature the regeneration was intended to make discoverable.

## What Changes

- Set the current Java 26.3 live world's world spawn to the safe surface
  position at the nearest village to the original world spawn.
- Define a repeatable regeneration step that locates the nearest supported
  village from the original spawn, chooses a safe spawn surface, and sets the
  world spawn there.
- Document that beds and respawn anchors remain authoritative for players who
  have set them.
- Preserve fail-closed behavior when no supported village, safe surface, or
  verified world state can be established.

## Capabilities

### New Capabilities

### Modified Capabilities

- `live-world-regeneration`: regenerated worlds must make the nearest supported
  village discoverable through world spawn and persist the derived coordinates.

## Impact

- Live Minecraft world state at `10.1.1.232:25555` receives a one-time
  `/setworldspawn` adjustment; no blocks are changed.
- Regeneration runbook and acceptance evidence in `README.md` change.
- The live-world-regeneration specification gains spawn derivation, safety, and
  persistence requirements. No Python dependencies, settlement records, or
  village-generation templates change.
