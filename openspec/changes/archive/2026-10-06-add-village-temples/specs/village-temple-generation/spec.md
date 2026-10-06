# Spec Delta

## Purpose

Provide discoverable Keeper temples as part of normal Minecraft village generation, without relying on optional building selection or runtime construction in occupied villages.

## ADDED Requirements

### Requirement: One Keeper temple in every newly generated village
With the generation pack installed before terrain generation, each newly generated vanilla village SHALL contain exactly one Keeper temple in its mandatory town center. This SHALL cover plains, desert, savanna, snowy, and taiga villages and their normal and abandoned variants.

#### Scenario: Generate any supported village variant
- **WHEN** Java 26.3 generates a village using any normal or abandoned town-center variant in one of the five supported village styles
- **THEN** its town center contains one Keeper temple regardless of optional house selections
- **AND** no second Keeper temple is introduced through optional village pieces

### Requirement: Recognizable and usable temple
Each Keeper temple SHALL have a roofed interior, a visible altar, and an unobstructed entrance reachable from the village center. Its exterior SHALL use materials appropriate to its village style, with a consistent altar identity across styles.

#### Scenario: Player explores the village center
- **WHEN** a player approaches a newly generated temple in any supported village style
- **THEN** the player can identify the roofed temple, walk through its entrance, and reach the altar without breaking blocks

#### Scenario: Temple generates with an abandoned village
- **WHEN** the selected village is abandoned
- **THEN** the temple retains its identifiable altar and traversable entrance despite the abandoned visual treatment

### Requirement: Preserve vanilla village placement and selection
The feature SHALL retain Java 26.3's vanilla village placement rules, biome eligibility, village frequency, and normal-versus-abandoned selection weights. Temple generation SHALL occur at the village site selected by Minecraft, not at coordinates chosen by a model or a polling process.

#### Scenario: Compare generation at a fixed seed
- **WHEN** the same seed and generation settings are used with and without the temple pack
- **THEN** village placement rules and biome selection are unchanged
- **AND** the temple-bearing town center occupies the corresponding vanilla village site

### Requirement: Preserve functional village connections
Temple-bearing town centers SHALL preserve functional connections to vanilla village roads and downstream building pieces in every supported rotation. Their foundations and interior clearance SHALL be compatible with vanilla village terrain adaptation.

#### Scenario: Village generates on uneven terrain
- **WHEN** a temple-bearing village generates on uneven terrain using a supported root rotation
- **THEN** the temple's usable floor is supported and its entrance is unobstructed
- **AND** its town-center connections can assemble vanilla roads and buildings without the temple sealing those connections

### Requirement: Vanilla Java 26.3 compatibility
The generation pack SHALL load and generate temples on an unmodified Minecraft Java 26.3 server and client, without server mods, client mods, or new Python runtime dependencies. Unsupported Minecraft versions SHALL NOT be presented as verified compatible.

#### Scenario: Load the pack on the target version
- **WHEN** a fresh Java 26.3 world starts with the generation pack installed
- **THEN** the server enables it without pack-format, registry, or template-schema errors
- **AND** a standard Java 26.3 client can render and enter generated temples

#### Scenario: Deployment targets an unverified version
- **WHEN** deployment is requested for a Minecraft version other than the verified target
- **THEN** deployment is rejected before the designated live world or Director state is replaced

### Requirement: Generation is independent of the Director loop
Keeper temples SHALL generate without an online Director process, settlement initialization, online players, or an LLM request. This feature SHALL NOT change existing quest selection, turn-in coordinates, or reward behavior.

#### Scenario: Generate villages with the Director stopped
- **WHEN** a fresh world generates supported villages while the Director is stopped
- **THEN** each village still contains its mandatory Keeper temple
- **AND** generation makes no external model request

### Requirement: Existing chunks are not retroactively changed
Installing the generation pack SHALL NOT replace or retrofit villages in already generated chunks. The mandatory temple contract SHALL apply to newly generated village starts only.

#### Scenario: Enable the pack in a previously explored world
- **WHEN** the pack is installed after a village's chunks have already generated
- **THEN** that existing village and any player edits remain unchanged
- **AND** newly generated villages use the temple-bearing town centers

### Requirement: Generated temples persist without replay
Generated temples and subsequent player edits SHALL persist through chunk unloads and server restarts without automatic reconstruction or duplicate placement.

#### Scenario: Revisit a player-edited temple after restart
- **WHEN** a player edits a generated temple and the world is saved, unloaded, and restarted
- **THEN** the saved temple and player edits remain as they were
- **AND** neither the generation pack nor the Director recreates or duplicates the temple
