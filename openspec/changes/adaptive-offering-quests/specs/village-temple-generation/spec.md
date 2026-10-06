# Village Temple Generation Specification Delta

## MODIFIED Requirements

### Requirement: Recognizable and usable temple
Each Keeper temple SHALL have a roofed interior, a visible altar, an unobstructed entrance reachable from the village center, one empty normal Keeper offering chest, and one ender chest. Its exterior SHALL use materials appropriate to its village style, with a consistent altar identity across styles. The offering chest and ender chest SHALL occupy documented, reachable positions inside the authored temple and SHALL NOT block the entrance, altar approach, or vanilla road connections.

#### Scenario: Player explores the village center
- **WHEN** a player approaches a newly generated temple in any supported village style
- **THEN** the player can enter without breaking blocks
- **AND** can reach the altar, the Keeper offering chest, and the ender chest
- **AND** the normal chest starts without preloaded loot

#### Scenario: Temple has approved container block entities
- **WHEN** a supported root is decoded and validated
- **THEN** its only authored block-entity payloads are the documented offering chest and ender chest
- **AND** no entity, command block, arbitrary container, or unrelated block-entity payload is present

#### Scenario: Temple generates with an abandoned village
- **WHEN** the selected village is abandoned
- **THEN** processors may weather ordinary temple blocks
- **BUT** the altar, entrance, offering chest, and ender chest remain identifiable and reachable

### Requirement: Generation is independent of the Director loop
Keeper temples SHALL generate without an online Director process, settlement initialization, online players, or an LLM request. This SHALL include creation of the empty offering chest and ender chest block entities, and SHALL NOT require quest state or Director configuration.

#### Scenario: Generate villages with the Director stopped
- **WHEN** a fresh Java 26.3 world generates a supported village while the Director is stopped
- **THEN** the village contains one temple with its altar, empty offering chest, and ender chest
- **AND** generation makes no external model request

### Requirement: Existing chunks are not retroactively changed
Installing the generation pack SHALL NOT replace or retrofit temples, offering chests, or ender chests into already generated villages. The complete temple contract SHALL apply to newly generated village starts only.

#### Scenario: Enable the pack in a previously explored world
- **WHEN** the updated pack is installed after a village's chunks have already generated
- **THEN** that existing village and its player edits remain unchanged
- **AND** newly generated villages use the complete container-bearing temple
