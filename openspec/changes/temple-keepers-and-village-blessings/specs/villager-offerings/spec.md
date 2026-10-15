# Spec Delta

## Purpose

Let villagers complete independent local Keeper quests through visible altar visits and real-inventory sacrifices that improve village prosperity without exhausting food or working resources.

## ADDED Requirements

### Requirement: Maintain independent local NPC quests
Each active Keeper SHALL offer independent NPC quests to eligible adult villagers belonging to its local village. NPC quests SHALL not share player quest progress, player chest contents, or player rewards. A villager SHALL not participate in simultaneous rituals for overlapping Keepers.

#### Scenario: Player and villager offer the same material
- **WHEN** a villager sacrifices an item also requested by a player quest
- **THEN** the NPC transaction is recorded separately and does not satisfy the player quest
- **AND** no NPC item is deposited into or consumed from the player offering chest

#### Scenario: Village lies near two temples
- **WHEN** a villager could fall inside two temple service areas
- **THEN** it has one stable local Keeper assignment for active NPC work
- **AND** both Keepers do not debit it or distribute overlapping assistance in the same eligibility period

### Requirement: Request only actually possessed approved goods
NPC requests SHALL use verified live villager inventory quantities and trusted item-specific rules. Approved food and profession-related goods SHALL be supported only when actually possessed and safe to spare. Profession, trade catalogs, nearby terrain, saved inventory snapshots, and model assertions SHALL NOT substitute for live possession.

#### Scenario: Smith has an iron trade but no iron inventory
- **WHEN** the smith's trade catalog includes iron but its live inventory has none
- **THEN** no iron sacrifice is assigned or fabricated

#### Scenario: Villager has an approved non-food surplus
- **WHEN** a villager actually holds approved profession-related goods above its protected working reserve
- **THEN** a bounded NPC request can use that surplus
- **AND** unsupported goods and components remain untouched

### Requirement: Protect nutrition and working reserves
NPC assignment and final sacrifice SHALL preserve trusted nutrition and item-specific working reserves. Seeds, tools, planting supplies, or other essential stocks SHALL not be exhausted by repeated quests. Missing reserve definitions, inventory uncertainty, or insufficient surplus SHALL defer the request without penalty or harder replacement demands.

#### Scenario: Villager retains breeding food but no surplus
- **WHEN** sacrificing the requested food would cross its protected nutrition reserve
- **THEN** no sacrifice occurs and the villager loses no goods

#### Scenario: Repeated non-food requests reach the reserve
- **WHEN** additional requests would reduce a protected material below its working reserve
- **THEN** further requests for that material stop
- **AND** the Keeper does not escalate demand to compensate for depleted stock

### Requirement: Perform visible visits without overriding survival behavior
A sacrifice SHALL occur only after the participating villager reaches its verified altar approach and completes a bounded visible ritual. Work, sleep, trading, danger avoidance, and ordinary village AI SHALL not be permanently disabled. A blocked path, danger, unloading, or interrupted visit SHALL cancel or defer the attempt without consuming goods.

#### Scenario: Villager reaches the altar
- **WHEN** an eligible villager arrives safely with the requested surplus still available
- **THEN** it pauses for a visible altar ritual and its Keeper acknowledges the offering locally
- **AND** it returns to ordinary activity afterward

#### Scenario: Attack interrupts the approach
- **WHEN** a villager flees a threat before the sacrifice commits
- **THEN** its goods remain intact and the attempt produces no completion credit
- **AND** the ritual does not teleport or immobilize the villager to force completion

### Requirement: Secure food-positive donor compensation
A successful NPC exchange SHALL leave the donor with more usable nutrition than the food sacrificed and preserve protected working stocks. Compensation SHALL be secured before any debit and require verified inventory capacity. If compensation or the final reserve check cannot be verified, sacrifice SHALL not occur. Unrelated stacks and components SHALL remain intact.

#### Scenario: Food exchange succeeds
- **WHEN** a verified sacrifice and its secured food compensation complete
- **THEN** the donor's usable nutrition increases rather than decreases
- **AND** only the approved sacrifice quantity is removed

#### Scenario: Donor inventory cannot accept compensation
- **WHEN** the donor has no verified safe capacity for the reward
- **THEN** it is not debited
- **AND** reward items are not dropped as collectible player loot

### Requirement: Distribute bounded village surplus after compensation
After donor compensation is secured, additional food rewards SHALL be distributed to verified low-stock local villagers with capacity. Distribution SHALL preserve components, respect per-recipient and village budgets, and not require the recipient to donate. Failure to distribute extra surplus SHALL not justify repeating the donor's debit or inventing a second quest completion.

#### Scenario: Non-donor needs food
- **WHEN** a successful NPC quest has surplus budget and another local villager has low stock and capacity
- **THEN** that villager can receive surplus food without having made an offering

#### Scenario: Surplus recipient becomes unavailable
- **WHEN** a selected recipient unloads or its inventory changes before distribution
- **THEN** unsafe distribution is deferred or withheld
- **AND** the donor's sacrifice is not repeated

### Requirement: Offer a modest unconditional recovery safety net
An active Keeper SHALL provide bounded food assistance and healing to local villagers with verified need even when no safe sacrifice is possible. Assistance SHALL not require an offering, create player quest credit, grant unbounded goods, or apply failure penalties. Healthy or unverifiable recipients SHALL not receive need-based food grants.

#### Scenario: Poor village has no offerings
- **WHEN** villagers have insufficient reserves but verified inventory capacity
- **THEN** eligible villagers receive modest rate-limited food assistance and healing
- **AND** no goods are taken in exchange

#### Scenario: World reload follows assistance
- **WHEN** a village unloads or the Director restarts after a safety-net grant
- **THEN** the grant's budget and eligibility record survive
- **AND** no duplicate grant or accumulated missed payout is issued

### Requirement: Preserve exact NPC exchange ownership and uncertainty
NPC work SHALL durably identify its Keeper, villager, requested goods, compensation, and operation identity. A lost response or changed live inventory SHALL not trigger blind re-execution, another debit, or duplicate prosperity credit. NPC exchange recovery SHALL not consume from a player chest or another villager.

#### Scenario: Acknowledgment is lost
- **WHEN** an NPC exchange may have completed but its response is lost
- **THEN** its durable operation is inspected or reconciled before any further debit
- **AND** compensation and village credit are not blindly replayed

#### Scenario: Villager disappears during pending work
- **WHEN** the recorded villager dies, transforms, or cannot be verified
- **THEN** the operation remains protected for reconciliation
- **AND** another villager does not inherit its sacrifice or reward debt

### Requirement: Bound rituals and prevent population-driven resource pressure
NPC request size, eligibility cadence, and reward budgets SHALL be bounded by trusted policy. A larger population SHALL not increase per-villager sacrifice demands or bypass protected reserves. Unloaded or suspended temples SHALL not perform NPC exchanges or assistance, and missed activity SHALL not accrue catch-up payouts.

#### Scenario: Village population grows
- **WHEN** food rewards permit additional villagers to join a village
- **THEN** per-villager demands remain bounded and protected reserves still apply
- **AND** additional participants cannot bypass the village reward budget
