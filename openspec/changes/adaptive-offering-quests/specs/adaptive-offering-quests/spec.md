# Adaptive Offering Quests Specification

## Purpose

Provide two durable Keeper quest lanes that use real Minecraft offering inventories, adapt difficulty to player progression, and never request an item outside the safe supply and progression candidates available to the relevant players.

## ADDED Requirements

### Requirement: Maintain distinct communal and private quest lanes
The Director SHALL maintain at most one active communal quest and at most one active private quest for each eligible online player. A communal quest SHALL target the online group; a private quest SHALL identify exactly one target player. Active quests and their lane, target, candidate context, and completion state SHALL survive Director restarts without duplicate quest creation.

#### Scenario: Multiple players are online
- **WHEN** quest generation is due and two or more eligible players are online
- **THEN** the Director MAY create one communal quest and one private quest per eligible player
- **AND** each quest has an unambiguous lane and ownership target

#### Scenario: Director restarts with active quests
- **WHEN** the Director restarts while communal or private quests are active
- **THEN** it reloads those quests and does not create replacement quests until their existing lifecycle completes or is safely cancelled

### Requirement: Use lane-specific offering inventories
Communal quests SHALL be submitted to the configured Keeper offering chest at the world-spawn temple. Private quests SHALL be submitted to the target player's ender-chest inventory. A quest SHALL NOT complete from an unrelated player inventory, an unrelated chest, or an LLM-provided coordinate.

#### Scenario: Communal offering is deposited
- **WHEN** the communal offering chest contains at least the requested quantity of the requested item
- **THEN** the Director recognizes the communal quest as completable
- **AND** preserves all unrelated chest contents

#### Scenario: Private offering is deposited
- **WHEN** the target player's ender chest contains at least the requested quantity of the requested item
- **THEN** the Director recognizes only that target player's private quest as completable
- **AND** another player's ender-chest contents cannot satisfy it

#### Scenario: Offering is in the wrong inventory
- **WHEN** the requested item exists only in a player inventory, a different chest, or another player's ender chest
- **THEN** the corresponding quest remains incomplete
- **AND** no item or reward is consumed or granted

### Requirement: Consume offerings with durable uncertainty protection
Before mutating an offering inventory, the Director SHALL persist the intended quest consumption and reward ownership. It SHALL consume only the requested item and quantity, preserve unrelated slots and item metadata, and SHALL NOT replay consumption or rewards after an ambiguous RCON response. An uncertain operation SHALL remain pending for explicit reconciliation rather than being retried blindly.

#### Scenario: Exact offering consumption succeeds
- **WHEN** the expected inventory state is observed and the server acknowledges consumption
- **THEN** the requested quantity is removed exactly once
- **AND** the lane-appropriate reward is granted exactly once
- **AND** the completed quest is durably recorded

#### Scenario: RCON response is lost during consumption
- **WHEN** the server may have consumed an offering but the Director cannot verify the response
- **THEN** the quest enters an uncertain durable state
- **AND** the Director does not consume again or grant duplicate rewards

### Requirement: Filter candidates by observed supply and progression
The Director SHALL derive each lane's candidate set from trusted spawn-area observations, relevant inventories, and target progression. Local communal quests SHALL require observed spawn-village supply; private local quests MAY also use the target player's inventories. Higher progression bands MAY unlock configured early, established, Nether, End, and endgame materials. Unknown inspection SHALL exclude a candidate.

#### Scenario: Spawn village has pumpkins but no carrots
- **WHEN** the local supply observation contains pumpkin resources and no carrot resources
- **THEN** a local quest MAY select pumpkins if they are in the configured catalog
- **AND** a local quest SHALL NOT select carrots solely because carrots are in the global catalog

#### Scenario: Supply inspection is unavailable
- **WHEN** the Director cannot obtain a trustworthy observation for a local candidate
- **THEN** that candidate is excluded from the current local quest set
- **AND** the Director does not fall back to an arbitrary catalog item

#### Scenario: Stronger player unlocks a higher band
- **WHEN** a target player's bounded progression score crosses a configured progression threshold
- **THEN** the private candidate set MAY include the corresponding higher-band materials
- **AND** candidates remain limited to Python-owned configured item IDs and quantities

### Requirement: Use deterministic strength inputs and group averaging
The Director SHALL compute each online player's bounded strength from server-observable progression signals, including experience and equipped or owned progression materials. The model SHALL NOT provide or alter the score. Private difficulty SHALL use the target player's score; communal difficulty SHALL use the average score of eligible online players. A missing or malformed player signal SHALL reduce confidence and SHALL NOT grant an advanced tier by default.

#### Scenario: One advanced player and one novice are online
- **WHEN** private quests are generated for both players
- **THEN** the advanced player's private candidate band MAY exceed the novice's band
- **AND** the novice's private quest is not promoted solely by the advanced player's presence

#### Scenario: A communal quest is generated
- **WHEN** eligible players have different strength scores
- **THEN** communal difficulty is derived from the documented average rather than the strongest player alone
- **AND** communal reward ownership remains group-wide

### Requirement: Keep LLM and fallback selection within the same safe set
The Director SHALL pass the lane-specific candidate IDs, quantity bounds, progression band, and player context to the LLM. Validation SHALL reject any item, quantity, target, lane, or reward outside Python-owned candidates. Deterministic fallback SHALL use the same filtered candidate set and SHALL create no quest when that set is empty.

#### Scenario: Model requests an unavailable carrot
- **WHEN** the current lane candidate set excludes carrots
- **THEN** validation rejects the model result
- **AND** fallback selects only from the filtered set or declines to create a quest

#### Scenario: No safe candidate exists
- **WHEN** a lane has no observed or progression-eligible candidate
- **THEN** no active quest is created for that lane
- **AND** the Director records the reason without mutating inventories or granting rewards

### Requirement: Announce and reward by lane ownership
Communal announcements SHALL instruct players to deposit offerings into the Keeper offering chest and communal completion SHALL grant the configured direct reward to all players eligible at completion plus the configured communal settlement progress once. Private announcements SHALL identify the target player and ender-chest submission location; private completion SHALL grant the configured direct reward only to that target player plus the corresponding settlement progress once.

#### Scenario: Communal quest completes
- **WHEN** the public offering chest satisfies the communal quest
- **THEN** all eligible online players receive the communal direct reward exactly once
- **AND** a later tick or restart cannot pay it again

#### Scenario: Private quest completes
- **WHEN** the target player's ender chest satisfies the private quest
- **THEN** only the target player receives the private direct reward
- **AND** the quest's settlement progress and completion record are idempotent

### Requirement: Preserve trust and compatibility boundaries
The quest system SHALL remain standard-library-only, use only validated item IDs, inventory sources, quantities, and reward objects, and keep the target Java runtime compatible. Quest generation SHALL not turn an LLM response into a command, coordinate, chest slot, arbitrary progression score, or unvalidated reward.

#### Scenario: Malformed or hostile model response
- **WHEN** a model response includes a command, coordinate, inventory slot, unknown item, or arbitrary reward
- **THEN** validation rejects the response before any RCON mutation
- **AND** the Director uses the safe fallback or declines the lane
