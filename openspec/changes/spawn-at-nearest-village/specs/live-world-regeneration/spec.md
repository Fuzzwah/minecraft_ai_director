# Spec Delta

## ADDED Requirements

### Requirement: Derive the nearest village from the original spawn

A regenerated live world SHALL derive its default world-spawn target from the
original world-spawn coordinates recorded before regeneration. The derivation
SHALL consider the supported Java 26.3 overworld village structure types
(plains, desert, savanna, snowy, and taiga), including the nearest result rather
than assuming a biome or hard-coded village coordinate.

#### Scenario: A supported village is found

- **WHEN** the replacement world has generated terrain around the original spawn
  and at least one supported village can be located
- **THEN** the operator selects the village with the smallest horizontal
  distance from the recorded original spawn
- **AND** the selected village coordinates are recorded as regeneration evidence

#### Scenario: No supported village is found

- **WHEN** no supported village can be located from the recorded original spawn
- **THEN** regeneration acceptance stops without changing world spawn
- **AND** the failure is reported for offline investigation

### Requirement: Select a safe village spawn surface

The selected village location SHALL be inspected in the loaded overworld before
world spawn is changed. The final player position SHALL be an air position above
solid supporting terrain at the selected village site and SHALL not intentionally
place a player inside a solid structure block or unloaded chunk.

#### Scenario: Village surface is safe

- **WHEN** the selected village column has a verified solid support block and a
  clear player position above it
- **THEN** that verified position becomes the proposed world-spawn target

#### Scenario: Village surface is unsafe or uncertain

- **WHEN** the selected village location is obstructed, unsupported, unloaded,
  or otherwise uncertain
- **THEN** world spawn remains unchanged
- **AND** the operator stops and reconciles the actual world state before retrying

### Requirement: Persist the derived world spawn

After the safe target is verified, the live world SHALL set its default world
spawn to that target. The world SHALL be saved before acceptance and the target
SHALL remain after restart. Player beds and respawn anchors SHALL continue to
override the default world spawn for players who have configured them.

#### Scenario: Accept a regenerated world

- **WHEN** the nearest village and safe surface checks pass
- **THEN** world spawn matches the recorded target
- **AND** save/inspection after restart reports the same target

#### Scenario: Existing player-specific respawn exists

- **WHEN** a player has a valid bed or respawn anchor
- **THEN** that player uses its configured respawn point rather than the default
  village world spawn
