# Spec Delta

## Purpose

Define safe communal and private Keeper quests that share one physical temple
offering source while preserving target-specific reward ownership and durable
completion behavior.

## ADDED Requirements

### Requirement: Share one normal offering chest across quest lanes
The Director SHALL use the configured loaded normal temple chest as the offering
source for both communal and private quests. Private quests SHALL retain exactly
one target player, but SHALL NOT read or consume that player's ender-chest
inventory.

#### Scenario: Private offering is deposited in the temple chest
- **WHEN** the configured temple chest contains the requested item and quantity for an active private quest
- **THEN** the Director recognizes the private quest as completable
- **AND** only its target player receives the direct reward
- **AND** unrelated online players receive no reward from that private quest

#### Scenario: Private offering exists only in an ender chest
- **WHEN** the requested item exists only in the target player's ender chest
- **THEN** the private quest remains incomplete
- **AND** no item or reward is consumed or granted

### Requirement: Remove ender-chest temple dependency
Generated Keeper temples SHALL contain no ender chest used by the offering quest
contract. Quest announcements, validation, source inspection, and consumption
errors SHALL identify the normal temple chest as the only offering location.

#### Scenario: Temple pack is inspected
- **WHEN** any supported normal or abandoned temple root is decoded
- **THEN** it contains at most the configured normal offering chest and no generated ender chest
- **AND** the normal offering chest starts empty without a loot table

### Requirement: Preserve durable shared-chest transaction safety
Shared-chest consumption SHALL retain prepared, uncertain, and completed
intent protection. It SHALL consume only the requested item and quantity,
preserve unrelated slots and metadata, and SHALL NOT replay consumption or
rewards after an ambiguous response.

#### Scenario: Shared chest changes after intent preparation
- **WHEN** the chest fingerprint differs before the Director executes a prepared private or communal consumption
- **THEN** the operation stops without issuing consumption commands
- **AND** the durable state remains available for reconciliation

#### Scenario: Director restarts after shared-chest completion
- **WHEN** the Director restarts after a shared-chest consumption or reward response may have completed
- **THEN** it does not consume the same offering or grant the same reward again
- **AND** the target ownership of a private reward remains unchanged

### Requirement: Migrate legacy private submission state safely
A persisted private quest whose submission source is the removed ender chest SHALL
be migrated to the shared normal chest source without reading or mutating the
ender-chest inventory. The migration SHALL preserve its quest ID, target, item,
quantity, rewards, and uncertainty state.

#### Scenario: Legacy private quest is loaded
- **WHEN** state contains an active private quest with an ender-chest submission source
- **THEN** the Director rewrites its source to the configured normal offering chest
- **AND** the quest remains incomplete until the shared chest satisfies it
- **AND** no legacy ender-chest item is consumed
