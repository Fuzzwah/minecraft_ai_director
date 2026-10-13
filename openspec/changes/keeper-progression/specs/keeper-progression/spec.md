# Spec Delta

## Purpose

Give all players a shared, persistent Keeper whose rank grows through successful offerings and unlocks bounded protective blessings and modest player XP bonuses without changing quest ownership or item rewards.

## ADDED Requirements

### Requirement: Award equal shared completion credit
When Keeper progression is enabled, each fully successful personal or communal quest SHALL award exactly one Keeper XP to the world's shared Keeper, independently of difficulty, quantity, number of recipients, or settlement enablement. Failed, retired, dry-run, pending, and uncertain quests SHALL award no credit.

#### Scenario: Different quest lanes and difficulties contribute equally
- **WHEN** one personal quest and one communal quest of different reward tiers fully complete
- **THEN** the shared Keeper total increases by two
- **AND** the communal quest contributes one credit whether it rewards one or several players

#### Scenario: An offering or reward is unresolved
- **WHEN** consumption, a player reward, or a required settlement obligation remains pending or uncertain
- **THEN** that quest contributes no Keeper credit
- **AND** credit is earned only when all required obligations subsequently resolve successfully

### Requirement: Preserve credit idempotently across restarts
A successful quest's Keeper credit, lane completion, and retirement SHALL become durable together. Reprocessing that quest ID after a later tick, restart, or attempted duplicate completion SHALL NOT consume another offering, grant another reward, or increase Keeper XP again.

#### Scenario: Restart after a successful completion
- **WHEN** the Director restarts after the completion was persisted
- **THEN** the saved Keeper total and rank are retained
- **AND** processing the same quest ID leaves inventory, rewards, and Keeper total unchanged

#### Scenario: Persistence fails before a completion commit
- **WHEN** the Director cannot persist the final successful completion
- **THEN** it stops further mutation until durable state is inspected
- **AND** restart uses the saved reward progress rather than issuing acknowledged rewards again

### Requirement: Use cumulative fixed rank milestones
The Keeper SHALL start at rank 1 Dormant and advance to rank 2 Awakened at 3 credits, rank 3 Warden at 10, rank 4 Exalted at 25, and rank 5 Ascendant at 50. Rank SHALL remain capped at 5 while the lifetime completion total continues increasing. Keeper rank SHALL NOT raise quest difficulty or bypass existing supply/progression rules.

#### Scenario: A completion crosses a milestone
- **WHEN** a successful quest increases the total from 9 to 10
- **THEN** the Keeper becomes rank 3 Warden
- **AND** the next temple appearance milestone becomes due without changing active quest goals

#### Scenario: Final rank has already been reached
- **WHEN** a successful quest increases the total from 50 to 51
- **THEN** the total becomes 51 and rank remains Ascendant
- **AND** no prestige reset, sixth rank, or repeated final-rank upgrade is created

### Requirement: Freeze benefits at offering preparation
Each newly prepared offering transaction SHALL retain the Keeper rank earned before that transaction and its complete recipient-specific benefit plan. Retries and restarts SHALL use that plan even if another quest advances the Keeper. The milestone-crossing quest SHALL NOT receive benefits from the rank it is about to unlock.

#### Scenario: A pending offering survives another rank advancement
- **WHEN** an offering prepared at Awakened remains pending while another quest unlocks Warden
- **THEN** the pending offering retains Awakened benefits
- **AND** later offerings prepared after the advancement receive Warden benefits

#### Scenario: The third completion awakens the Keeper
- **WHEN** an offering prepared while the Keeper is Dormant becomes the third successful completion
- **THEN** that offering receives Dormant benefits and unlocks Awakened
- **AND** the next newly prepared offering uses Awakened benefits

### Requirement: Grant bounded protection and utility blessings
Dormant SHALL grant no blessing. Higher ranks SHALL grant only finite-duration Haste I and Resistance I from a fixed rank policy, with no effect exceeding 120 seconds. Blessings SHALL occur only as part of successful offering rewards, without a continuous aura, offensive effect, effect clearing, or intentional reduction of an existing stronger effect.

#### Scenario: A ranked offering rewards its recipients
- **WHEN** a Warden offering completes normally
- **THEN** its recipients receive Haste I for 60 seconds and Resistance I for 30 seconds according to vanilla effect merging
- **AND** no unrelated player receives these effects from a personal completion

#### Scenario: A stronger effect already exists
- **WHEN** a recipient has Haste II and receives a Keeper Haste I blessing
- **THEN** the Keeper does not clear or replace the stronger active effect with Haste I
- **AND** there is no special cleanup command when the Keeper blessing expires

### Requirement: Add modest player XP without changing item rewards
Keeper bonus player XP SHALL be 0, 5, 10, 15, or 20 points per recipient at ranks 1 through 5 respectively. It SHALL be additional to existing base XP-level rewards, not multiplied by tier or recipient count. Existing item reward IDs, quantities, selection, and settlement rewards SHALL remain unchanged.

#### Scenario: A private Warden quest completes
- **WHEN** its prepared benefit plan uses rank 3
- **THEN** its target receives 10 bonus XP points in addition to the existing base rewards
- **AND** another online player receives neither the bonus XP nor the private reward

#### Scenario: A communal Ascendant quest completes
- **WHEN** its frozen eligible recipients are rewarded at rank 5
- **THEN** each recipient receives 20 bonus XP points
- **AND** the shared Keeper still earns only one completion credit

### Requirement: Protect benefit ownership and uncertain delivery
Blessings and bonus XP SHALL use the same frozen recipient ownership as base rewards: one target for personal quests and eligible online players captured at communal completion preparation. Benefit intent and delivery progress SHALL survive restarts. Missing, negative, or ambiguous mutation acknowledgements SHALL stop delivery without credit or blind replay.

#### Scenario: A player joins after communal preparation
- **WHEN** a communal reward transaction was prepared for Alice and Bob and Carol joins before delivery finishes
- **THEN** Carol is not added to that prepared transaction
- **AND** recipient ownership remains Alice and Bob across restart

#### Scenario: Bonus XP acknowledgement is lost
- **WHEN** the server may have granted bonus XP but its response is lost
- **THEN** the operation remains durably uncertain and Keeper credit is not awarded
- **AND** restart does not reissue the XP command or replace the captured benefit plan

### Requirement: Activate without inventing historical progress
Keeper progression SHALL require explicit enablement and a stable verified world/temple binding. Activation of an existing world SHALL initialize zero Keeper XP without backfilling capped warm-up counters or resetting existing state. Existing active and pending quests SHALL retain their original reward obligations; successful completions after activation SHALL earn credit once.

#### Scenario: Existing quest state has warm-up progress and pending debt
- **WHEN** Keeper progression is first enabled for that world's state
- **THEN** Keeper XP starts at zero while quests, warm-up counters, settlement identity, and pending uncertainty remain intact
- **AND** a migrated pending reward retains its old command ordering and receives no retrofitted blessing or bonus XP
- **AND** its eventual fully successful completion earns one Keeper credit

#### Scenario: Keeper progression is disabled
- **WHEN** the Director runs without Keeper enablement
- **THEN** ordinary quest behavior continues without new Keeper credit, benefits, or temple mutations
- **AND** saved Keeper progress and already prepared benefit obligations are retained rather than discarded

### Requirement: Expose earned progress separately from appearance
Read-only Keeper status SHALL show world/temple binding, lifetime total, earned rank, next milestone or maximum-rank status, installed temple rank, and any blocked or uncertain upgrade. A rank advancement SHALL produce a best-effort player announcement only after durable credit; status SHALL remain authoritative if an announcement is interrupted.

#### Scenario: Decoration is blocked after a rank advancement
- **WHEN** the Keeper has earned Warden but the temple remains at Awakened because a patch target was edited
- **THEN** status shows earned rank 3 and installed rank 2 with the blocker
- **AND** subsequent ordinary quests can still complete and earn Keeper credit

### Requirement: Keep model authority and previews constrained
Models SHALL NOT select Keeper XP, ranks, effect IDs, durations, bonus amounts, temple coordinates, or decoration commands. Dry-run and read-only status/preview SHALL issue no mutation, grant no benefit or credit, and leave persistent quest and settlement state unchanged.

#### Scenario: Model output attempts to select a power
- **WHEN** a model-authored quest includes an effect, Keeper rank, arbitrary XP, or temple mutation
- **THEN** validation rejects that output before any mutation
- **AND** Keeper policy remains Python/admin-owned

#### Scenario: Preview an existing world
- **WHEN** a read-only Keeper preview inspects the active temple and next milestone
- **THEN** it reports the intended changes and safety blockers using read-only probes
- **AND** world inventory, quest JSON, and settlement database checksums remain unchanged
