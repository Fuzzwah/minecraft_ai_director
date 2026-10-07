# Live World Regeneration Specification Delta

## MODIFIED Requirements

### Requirement: Regeneration requires verified generation assets
Live-world regeneration SHALL proceed only after the container-bearing Java 26.3 temple pack, adaptive offering quest implementation, and their isolated runtime checks are complete and reviewed. A planning artifact or unverified datapack SHALL NOT authorize replacement of the live world or Director state.

#### Scenario: Feature is not ready
- **WHEN** generation assets are absent, incompatible, unverified, or not merged into the live source checkout
- **THEN** the existing live world and Director state remain unchanged
- **AND** the unmet prerequisite is reported rather than producing another replacement world

#### Scenario: Planning only
- **WHEN** the operator requests a proposal or specification update
- **THEN** no live server restart, world regeneration, or state replacement occurs

#### Scenario: New generation or quest assets are unverified
- **WHEN** the updated pack, chest transaction behavior, supply probe, or progression behavior lacks target-version runtime evidence
- **THEN** the live world is not replaced
- **AND** the existing services and persistent state remain untouched

### Requirement: Use fresh state for regenerated terrain
The replacement live world SHALL use a new random seed and SHALL start with fresh quest JSON, settlement SQLite state, and a new settlement world identity when settlements are enabled. Old quest, reward, building, and initialization records SHALL NOT attach to the new terrain.

#### Scenario: Start the Director against regenerated terrain
- **WHEN** the designated live world is replaced
- **THEN** the replacement server starts with the approved Java 26.3 pack before first terrain generation
- **AND** its Director state is newly initialized for that world
- **AND** the old world and matching Director state remain available as one rollback pair

### Requirement: Verify the replacement before normal play
Acceptance SHALL require a working Java 26.3 server with the updated pack enabled, at least one naturally generated village containing the complete temple, an inspected offering chest and ender chest, a persisted nearest-village world spawn, authenticated Director RCON access, and isolated smoke evidence for communal and private quest inventory boundaries. A failed or uncertain inspection SHALL stop acceptance.

#### Scenario: Accept the new generation
- **WHEN** generated villages, container contents, world spawn, Director startup, and quest inventory probes pass
- **THEN** the replacement can be opened for normal play
- **AND** the acceptance record identifies the spawn temple and the nearest inspected village

#### Scenario: Container or quest boundary fails
- **WHEN** a generated temple lacks either approved container, a communal offering can be satisfied from the wrong inventory, or private consumption can affect another player
- **THEN** the replacement is rejected
- **AND** the old matched rollback pair remains the recovery source
