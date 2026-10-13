# Spec Delta

## Purpose

Provide durable communal and personal player quests owned by individual temple Keepers, with issuer-only turn-in, local supply-backed warm-up, and explicit reward ownership.

## ADDED Requirements

### Requirement: Maintain independent Keeper-owned player lanes
Each Keeper SHALL maintain at most one active communal quest and one active personal quest per eligible member. Each quest SHALL identify its issuing Keeper and retain a stable quest identity. A player SHALL be able to hold personal quests from different Keepers concurrently without one replacing another.

#### Scenario: Player meets two Keepers
- **WHEN** a player visits two healthy temples with safe unreserved candidates
- **THEN** each Keeper can issue its own personal quest and maintain its own communal quest
- **AND** assignments, cooldowns, and completion records remain separate

### Requirement: Accept offerings only at the issuing Keeper's chest
Both player lanes SHALL use only the issuing Keeper's designated loaded normal chest. The full requested quantity SHALL be present in that chest; quantities SHALL NOT aggregate across temples. Ender chests, NPC inventories, player inventories, arbitrary containers, and another Keeper's chest SHALL NOT satisfy the quest.

#### Scenario: Correct goods are offered to the wrong Keeper
- **WHEN** Keeper A issued a quest and its requested items exist only in Keeper B's chest
- **THEN** A's quest remains incomplete and B's items are not consumed for it

#### Scenario: Quantity is split between temples
- **WHEN** neither Keeper chest contains the full requested quantity for A's quest
- **THEN** A's quest remains incomplete even if the combined quantity would be enough

#### Scenario: Valid offering includes unrelated items
- **WHEN** A's designated chest contains its quest quantity plus unrelated stacks or extra quantity
- **THEN** only the requested item and quantity are consumed
- **AND** unrelated slots, components, and surplus are preserved

### Requirement: Reward communal membership and personal ownership
Communal completion SHALL reward eligible online players who have met the issuing Keeper, regardless of their current location. Personal completion SHALL reward only its named target under the existing online-target completion policy. Recipients SHALL be durably captured before consumption and SHALL NOT change during recovery.

#### Scenario: Member travels to another village
- **WHEN** an online member of A is elsewhere when A's communal quest completes
- **THEN** that eligible member receives A's communal reward
- **AND** an online player who has never met A receives no reward

#### Scenario: Personal quest completes
- **WHEN** a named target is eligible for completion at their issuing Keeper
- **THEN** only that target receives the personal reward
- **AND** another member does not receive the target's reward

### Requirement: Keep warm-up independent per Keeper and target
The first three successfully completed communal quests per Keeper and first three personal quests per Keeper and target SHALL be warm-up quests. Warm-up SHALL use the trusted catalog minimum and verified harvestable supply within 32 horizontal blocks of that temple's quest hub. Strength SHALL NOT bypass warm-up, and inventory possession alone SHALL NOT substitute for local evidence.

#### Scenario: Experienced player meets a new Keeper
- **WHEN** a strong player who finished A's warm-up first meets B
- **THEN** B's personal warm-up starts independently
- **AND** B requests only verified local minimum quantities

#### Scenario: Third personal completion at one temple
- **WHEN** a target successfully completes their third personal quest from A
- **THEN** only that target's A warm-up advances to post-warm-up
- **AND** B's warm-up and another target's progress are unchanged

### Requirement: Observe harvestable local supply conservatively
Local candidate evidence SHALL represent actual bounded resource positions and conservative obtainable yields. Immature crops, whole-section palette totals, inaccessible resources, out-of-radius positions, and unsupported yield assumptions SHALL NOT establish supply. Missing, unloaded, malformed, or changing observations SHALL defer the affected lane without widening its radius.

#### Scenario: Different villages grow different crops
- **WHEN** A has mature wheat and B has immature carrots but no qualifying wheat
- **THEN** A's wheat does not establish supply for B
- **AND** B does not request immature carrots as a harvestable opening offering

#### Scenario: Warm-up yield is below minimum
- **WHEN** an item's conservative local yield is below its trusted catalog minimum
- **THEN** that item is excluded rather than issuing an impossible quantity

### Requirement: Reserve distinct player items within each Keeper source
An item reserved by a Keeper's active communal quest, any personal quest including an offline target, or pending consumption/reward work SHALL be unavailable for another assignment from that Keeper. Reservations SHALL survive restarts and uncertainty. Separate Keeper chests SHALL be able to reserve the same item independently. NPC offerings SHALL remain outside player chest accounting.

#### Scenario: Same material is requested at two temples
- **WHEN** A and B independently have verified local wheat and separate chests
- **THEN** each can reserve wheat for its own quest
- **AND** neither consumes the other's wheat

#### Scenario: Offline personal target reserves an item
- **WHEN** A has an active personal wheat quest for an offline member
- **THEN** A cannot assign wheat to its communal lane or another personal target
- **AND** the reservation survives restart

### Requirement: Retain progression-safe post-warm-up difficulty
After warm-up, communal difficulty SHALL use the bounded average strength of eligible online members of its Keeper. Personal goals SHALL follow the existing next-band and every-fifth-assignment aspirational policy only within the target's own unlocks. Assigned goals SHALL NOT be repriced solely because membership or group strength changes.

#### Scenario: Advanced player is not a member
- **WHEN** an advanced online player has not met A
- **THEN** that player's strength does not raise A's communal difficulty

#### Scenario: Weak member cannot unlock the next personal band
- **WHEN** the target lacks the progression unlock required by the normal next band
- **THEN** the personal lane defers rather than borrowing another member's unlock

### Requirement: Constrain model and fallback selection equally
Model selection and deterministic fallback SHALL use the same trusted Keeper-local candidates, quantity bounds, lane, target eligibility, and reward catalog. The model SHALL NOT author commands, coordinates, chest sources, progression scores, or arbitrary rewards. An empty safe pool SHALL produce no assignment.

#### Scenario: Model selects a different temple or unavailable item
- **WHEN** model output attempts to select a chest source or an item outside the issuing Keeper's candidates
- **THEN** it is rejected before mutation
- **AND** fallback uses only that Keeper's safe candidates or defers

### Requirement: Pin durable player transactions to their original source
Before consumption, the system SHALL durably record quest identity, issuing Keeper, dimension, exact chest position, inventory fingerprint, quantities, and recipients. Changed sources and ambiguous responses SHALL suspend the operation for reconciliation. Recovery SHALL NOT redirect to another chest, replay uncertain consumption, or duplicate rewards or village blessing credit.

#### Scenario: Chest disappears during a pending operation
- **WHEN** an operation prepared at A's chest can no longer verify that source
- **THEN** it stays bound to A and suspended
- **AND** B's chest is not used as a fallback

#### Scenario: Response is lost after consumption
- **WHEN** consumption may have succeeded but acknowledgment is lost
- **THEN** uncertainty survives restart and the item remains reserved
- **AND** no consumption or reward is blindly replayed

### Requirement: Advance only fully successful lane completions
Completion counters and personal assignment sequences SHALL persist per Keeper. A fully successful quest SHALL advance its lane once and make replacement eligible in the same tick, subject to safe candidates. Failure, retirement, deferral, uncertainty, partial rewards, and dry-run SHALL NOT advance progress. Failed supply probes SHALL NOT start the ordinary no-candidate cooldown.

#### Scenario: Successful reward recovery finishes after restart
- **WHEN** pending work becomes fully successful and its replacement has a safe candidate
- **THEN** that Keeper's lane advances once and can receive a replacement immediately
- **AND** a later restart does not advance the count again

### Requirement: Preserve original state during Keeper migration
Existing quest IDs, targets, counters, reservations, and reward debt SHALL be retained and associated only with a verified original temple source. Historical pending recipient snapshots SHALL remain unchanged. Ambiguous source ownership SHALL stop migration of affected work rather than guessing. Untouched policy-invalid quests SHALL only retire under existing safe revalidation rules.

#### Scenario: Legacy source is verifiable
- **WHEN** the original configured temple source is verified during backed-up migration
- **THEN** its existing quests and lane counters belong to that Keeper without resetting progress
- **AND** new Keepers start independent progress without copying those counters

#### Scenario: Legacy pending source cannot be established
- **WHEN** durable commands, configuration, and world evidence cannot establish one original source
- **THEN** the affected operation remains protected for offline reconciliation
- **AND** no other Keeper inherits or executes its consumption
