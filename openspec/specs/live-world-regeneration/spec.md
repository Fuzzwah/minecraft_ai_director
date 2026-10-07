# live-world-regeneration Specification

## Purpose

Safely replace the designated live Minecraft world for verified village-temple generation while preserving a matched rollback source, isolating unrelated worlds, and preventing old Director records from attaching to new terrain.

## Requirements

### Requirement: Regeneration requires verified generation assets
Live-world regeneration SHALL proceed only after the reviewed temple-generation feature is merged, its Java 26.3 assets pass isolated generation checks, and the operator authorizes the destructive cutover. A planning request or an unverified datapack SHALL NOT authorize replacement of live world or Director state.

#### Scenario: Feature is not ready
- **WHEN** generation assets are absent, incompatible, unverified, or not merged into the live source checkout
- **THEN** the existing live world and Director state remain unchanged
- **AND** the unmet prerequisite is reported rather than producing another vanilla replacement world

#### Scenario: Planning only
- **WHEN** the operator requests a proposal or specification update
- **THEN** no live server restart, world regeneration, or state replacement occurs

### Requirement: Restrict the cutover to the designated live deployment
The cutover SHALL affect only the long-lived Java 26.3 server at `10.1.1.232:25555` and its matching Director state. Its source SHALL remain the reviewed primary `main` checkout, and unrelated family servers and the isolated settlement test world SHALL remain unchanged.

#### Scenario: Target identity does not match
- **WHEN** the selected world or deployment does not match the designated live server
- **THEN** regeneration is rejected before any persistent data is replaced

#### Scenario: Complete the approved live cutover
- **WHEN** the designated live world is replaced
- **THEN** the live connection remains `10.1.1.232:25555` with private RCON
- **AND** other Minecraft servers retain their worlds, port mappings, and state

### Requirement: Preserve a consistent rollback snapshot
Before regeneration, the operator SHALL stop Director writers, save the live world, stop Minecraft, and preserve both complete server data and matching Director state from that stopped generation. The snapshot SHALL have verified archives and checksums and SHALL be inaccessible to other local users because server settings can contain credentials.

#### Scenario: Snapshot fails verification
- **WHEN** either snapshot archive is absent, unreadable, incomplete, or fails its recorded checksum
- **THEN** the existing persistent world and Director state are retained
- **AND** the cutover does not proceed

#### Scenario: Existing backup predates further play
- **WHEN** players or the Director have changed the live generation since the previous snapshot
- **THEN** a fresh stopped-generation snapshot is taken before replacement

### Requirement: Install generation assets before the first generation
The replacement world SHALL have the verified temple-generation datapack installed and enabled before its first terrain generation. A missing or rejected pack SHALL prevent the replacement world from being accepted for play.

#### Scenario: Start the replacement world
- **WHEN** the new Java 26.3 world generates its first chunks
- **THEN** the enabled temple pack governs village generation from that first startup

#### Scenario: Pack is rejected during startup
- **WHEN** startup rejects the pack or reports generation-resource errors
- **THEN** the replacement world is not opened for normal play and the Director is not started against it
- **AND** the cutover is repaired while isolated or rolled back to the preserved generation

### Requirement: Use fresh state for regenerated terrain
The replacement world SHALL use fresh world-specific player and Director state rather than old player positions, quest JSON, building records, or reward debts. If settlements are enabled, the replacement SHALL use a new stable world identity. Previous progress SHALL remain available only in the preserved rollback generation.

#### Scenario: Start the Director against regenerated terrain
- **WHEN** the new Director first connects to the replacement world
- **THEN** no old active quest, pending reward, recorded structure, initialization flag, or player position is inherited
- **AND** at most one Director writer owns the new state

### Requirement: Preserve live server policy and generation settings
Regeneration SHALL retain the live server's survival settings, authentication policy, access-control configuration, and secret references. The current world seed SHALL be retained unless the operator explicitly chooses a different seed. The Director's spawn configuration SHALL be derived from the replacement world's actual spawn.

#### Scenario: Regenerate without requesting a new seed
- **WHEN** the operator approves regeneration without overriding generation settings
- **THEN** the replacement uses the previous seed and live access policy
- **AND** Director spawn coordinates match the new world's actual spawn rather than copied assumptions

### Requirement: Verify the replacement before normal play
Acceptance SHALL require a working Java 26.3 connection on port 25555, an enabled temple pack, a generated temple at a located live-world village, authenticated Director RCON access, and persistence through save and restart. Pack-format checks and mocked RCON SHALL NOT substitute for actual generation evidence; unverified client-only behavior SHALL be reported explicitly.

#### Scenario: Accept the new generation
- **WHEN** generation and live-runtime checks pass and any client-only verification limit is documented
- **THEN** the operator can open the new generation for normal play
- **AND** the checks identify the generated temple's village and coordinates for player inspection

### Requirement: Roll back world and Director state together
Rollback SHALL restore the previous world/server data, matching Director state, deployment references, and spawn configuration as a pair. It SHALL NOT combine old terrain with new quest/building state or silently replay uncertain rewards.

#### Scenario: Replacement fails acceptance
- **WHEN** the operator chooses rollback after a failed cutover check
- **THEN** the previous world and matching Director state are restored together
- **AND** the previous live server resumes at port 25555 without the replacement's state being attached to it
