# Spec Delta

## Purpose

Provide easy, demonstrably local opening offerings and distinct personal goals while protecting shared-chest ownership, progression limits, and durable recovery.

## ADDED Requirements

### Requirement: Offer an easy local warm-up per quest lane
The Director SHALL keep the first three successfully completed communal quests and first three successfully completed personal quests per target in a warm-up phase. Warm-up SHALL override progression-based difficulty, require verifiable supply within 32 horizontal blocks of the configured selected-village quest hub, and request the trusted catalog minimum quantity. Generating, deferring, retiring, or failing a quest SHALL NOT advance warm-up.

#### Scenario: New player joins a wheat and pumpkin village
- **WHEN** the target has no completed personal quests and communal warm-up is unfinished
- **THEN** both lanes select only qualifying nearby resources at minimum quantities
- **AND** neither lane requests carrots without verified nearby harvestable carrot supply

#### Scenario: Strong player starts a new lane
- **WHEN** a player's high progression score would unlock advanced materials but that lane has fewer than three completions
- **THEN** its new quest remains a local warm-up quest

#### Scenario: Third completion ends warm-up
- **WHEN** the third quest in a lane completes successfully
- **THEN** the next assignment for that lane uses the post-warm-up policy
- **AND** another player's personal warm-up remains independent

### Requirement: Observe actual harvestable supply at bounded positions
Local supply evidence SHALL represent actual resource positions and conservative obtainable item quantities. Immature crops, states with unknown growth, resources outside the selected radius, and resources that do not yield the requested item without an unavailable tool SHALL NOT count. Section-wide totals or palette membership alone SHALL NOT establish local supply.

#### Scenario: Mature wheat and immature carrots are nearby
- **WHEN** the local observation contains enough mature wheat, nearby pumpkins, and only immature carrots
- **THEN** wheat and pumpkins can qualify
- **AND** immature carrots contribute no immediate harvestable carrot quantity

#### Scenario: Resource lies across the radius boundary
- **WHEN** a resource is inside an intersecting chunk but more than 32 horizontal blocks from the quest hub
- **THEN** it does not contribute to warm-up supply

#### Scenario: Melon blocks do not yield whole melon items
- **WHEN** a whole melon item is a catalog candidate but only ordinary harvestable melon blocks are observed
- **THEN** the Director does not treat those blocks as proof of whole melon supply

### Requirement: Fail closed on unreliable supply observations
The Director SHALL exclude local supply whose chunk decoding, block-state interpretation, loading, or snapshot stability is uncertain. Malformed packed states SHALL NOT silently become arbitrary resources or a complete snapshot. An unavailable observation SHALL defer affected local assignments without widening the radius or using global-catalog fallback.

#### Scenario: Saved block-state data is malformed
- **WHEN** a packed block-state array is truncated or contains an invalid palette index
- **THEN** its local evidence is unavailable rather than guessed
- **AND** no quest is generated from the invalid evidence

#### Scenario: Snapshot changes during inspection
- **WHEN** a relevant saved region changes while it is being inspected
- **THEN** the affected observation is rejected for that selection cycle

### Requirement: Bound warm-up quantity by verified available yield
Every warm-up quest SHALL request no more than the conservative currently observed obtainable quantity of its item. If available yield is below the trusted minimum, the item SHALL be excluded. Target inventory ownership alone SHALL NOT substitute for nearby warm-up evidence. Both LLM validation and fallback SHALL obey the same quantity bounds.

#### Scenario: Only one pumpkin is available
- **WHEN** the minimum pumpkin request is two and only one qualifying pumpkin is observed
- **THEN** pumpkins are excluded rather than creating an impossible two-pumpkin quest

#### Scenario: Model exceeds the observed quantity
- **WHEN** an LLM requests more than the allowed warm-up quantity
- **THEN** its result is rejected and fallback uses only the permitted candidate bounds

### Requirement: Reserve distinct items across shared-chest quest work
The Director SHALL prohibit assigning an item already reserved by an active communal quest, any active personal quest including an offline target, or a pending offering/reward operation. Reservations SHALL apply in both lane directions and survive restarts. Uncertain operations SHALL retain their reservation until reconciled; lane scheduling order SHALL NOT bypass the guard.

#### Scenario: Communal wheat and personal pumpkin are active
- **WHEN** another personal quest or a replacement communal quest is due
- **THEN** wheat and pumpkin remain unavailable to the new assignment while reserved

#### Scenario: No unreserved local resource exists
- **WHEN** all qualifying warm-up items are already reserved
- **THEN** the lane defers without increasing difficulty or reusing another quest's item

#### Scenario: Pending consumption survives restart
- **WHEN** a quest has left the active slot but its offering or reward operation is pending
- **THEN** a restart does not release the item's reservation

### Requirement: Make post-warm-up personal goals harder but progression-safe
After personal warm-up, normal personal assignments SHALL use the band immediately above communal difficulty only when unlocked by that target's progression. Every fifth post-warm-up personal assignment SHALL prefer one additional unlocked band as an aspirational goal. If no aspirational candidate qualifies, normal selection SHALL apply; if no normal candidate qualifies, the lane SHALL defer. Neither group strength nor luck SHALL unlock a band for a weaker target.

#### Scenario: Target unlocks the next communal band
- **WHEN** communal difficulty is local and the post-warm-up target unlocks the early band
- **THEN** normal personal candidates come from the early band, not the communal local item pool

#### Scenario: Novice cannot support the next band
- **WHEN** the post-warm-up target has not unlocked the band above communal difficulty
- **THEN** no harder personal quest is invented or unlocked by another player's score

#### Scenario: Fifth assignment offers a lucky longer-term goal
- **WHEN** the fifth post-warm-up personal assignment has an unreserved candidate in the next additional band and the target unlocks that band
- **THEN** that assignment uses the aspirational band and is announced as a longer-term personal goal
- **AND** deferrals do not consume the assignment sequence

#### Scenario: Communal difficulty later changes
- **WHEN** group membership changes after a personal quest was durably assigned
- **THEN** that personal quest is not repriced or replaced solely to match a new group average

### Requirement: Persist progression without duplicate completion credit
Warm-up completion counts and personal assignment sequence SHALL survive restarts with quest state. Each fully successful quest SHALL advance its lane once regardless of reward recovery or restart. Missing legacy counters SHALL initialize to zero without fabricating historical completions. Pending, failed, dry-run, and uncertain operations SHALL NOT advance completion counts.

#### Scenario: Restart during reward recovery
- **WHEN** reward recovery completes and the Director restarts again
- **THEN** the recovered quest contributes exactly one completion to its lane

#### Scenario: Existing state has no warm-up fields
- **WHEN** pre-change quest state is loaded
- **THEN** counters start conservatively at zero
- **AND** existing IDs, targets, reward debt, inventory fingerprints, and uncertainty remain intact

### Requirement: Reconcile untouched policy-invalid active quests without world mutation
Before completing pre-change active quests, the Director SHALL identify policy-invalid or colliding assignments. It SHALL safely retire only quests without pending mutation/reward intent, announce the reason, and reselect when safe evidence exists. Retirement SHALL NOT consume offerings, issue rewards, advance warm-up, or modify uncertain operations. Uncertain observation SHALL suspend validation rather than assert that a resource is absent.

#### Scenario: Existing opening carrot quest has no valid local supply
- **WHEN** reliable inspection excludes carrots and the active carrot quest has no pending operation
- **THEN** it is durably retired and a safe unreserved nearby candidate can replace it
- **AND** existing chest contents remain unchanged

#### Scenario: Existing conflict includes an uncertain operation
- **WHEN** an active quest collides with an item reserved by an uncertain operation
- **THEN** the uncertain operation is preserved and no competing consumption command is issued
