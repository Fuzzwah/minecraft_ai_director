# Spec Delta

## Purpose

Give each temple Keeper an independent persistent rank shared by its contributors, with bounded protective blessings and modest player XP bonuses from successful player offerings without changing quest ownership or item rewards.

## ADDED Requirements

### Requirement: Award equal issuing-Keeper completion credit
Each fully successful personal or communal player quest SHALL award one XP to its issuing Keeper when progression is enabled, independently of difficulty, quantity, recipients, or settlements. All contributors SHALL share that Keeper's progress; separate Keepers SHALL have independent totals. Failed, retired, dry-run, pending, and uncertain quests SHALL award no credit.

#### Scenario: Different quest lanes and difficulties contribute equally
- **WHEN** one personal quest and one communal quest of different tiers fully complete for Keeper A
- **THEN** A's total increases by two and Keeper B's total is unchanged
- **AND** A's communal quest contributes one credit whether it rewards one or several players

#### Scenario: An offering or reward is unresolved
- **WHEN** consumption, a player reward, or a required settlement obligation remains pending or uncertain
- **THEN** that quest contributes no Keeper credit
- **AND** credit is earned only when all required obligations subsequently resolve successfully

### Requirement: Preserve credit idempotently across restarts
A successful player quest's issuer-specific Keeper credit, lane completion, and retirement SHALL become durable together. Reprocessing that quest ID after a later tick, restart, or attempted duplicate completion SHALL NOT consume another offering, grant another reward, or increase any Keeper's XP again.

#### Scenario: Restart after a successful completion
- **WHEN** the Director restarts after the completion was persisted
- **THEN** the saved Keeper total and rank are retained
- **AND** processing the same quest ID leaves inventory, rewards, and Keeper total unchanged

#### Scenario: Persistence fails before a completion commit
- **WHEN** the Director cannot persist the final successful completion
- **THEN** it stops further mutation until durable state is inspected
- **AND** restart uses the saved reward progress rather than issuing acknowledged rewards again

### Requirement: Use cumulative fixed rank milestones
Each Keeper SHALL independently start at rank 1 Dormant, reach rank 2 Awakened at 3 credits, rank 3 Warden at 10, rank 4 Exalted at 25, and rank 5 Ascendant at 50. Rank SHALL cap at 5 while its lifetime total continues increasing. One Keeper's advancement SHALL NOT raise another's rank or change quest difficulty/supply rules.

#### Scenario: A completion crosses a milestone
- **WHEN** a successful quest increases the total from 9 to 10
- **THEN** the Keeper becomes rank 3 Warden
- **AND** the next temple appearance milestone becomes due without changing active quest goals

#### Scenario: Final rank has already been reached
- **WHEN** a successful quest increases the total from 50 to 51
- **THEN** the total becomes 51 and rank remains Ascendant
- **AND** no prestige reset, sixth rank, or repeated final-rank upgrade is created

### Requirement: Freeze benefits at offering preparation
Each prepared player offering SHALL retain its issuing Keeper, dimension-qualified chest source, issuer's pre-transaction earned rank, frozen recipients, and complete benefit plan. Recovery SHALL use that plan regardless of configuration changes or any Keeper's advancement. The milestone-crossing quest SHALL NOT receive the rank it will unlock.

#### Scenario: A pending offering survives another rank advancement
- **WHEN** an offering prepared at Awakened remains pending while another quest unlocks Warden
- **THEN** the pending offering retains its issuing Keeper's Awakened benefits and original chest source
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
- **AND** its issuing Keeper still earns only one completion credit and other Keepers receive none

### Requirement: Protect benefit ownership and uncertain delivery
Blessings and bonus XP SHALL use frozen base-reward ownership: one personal target and eligible online communal recipients. With membership-based quests, eligibility SHALL be the issuing Keeper's online members, not another temple's members. Prepared recipients and delivery progress SHALL survive migration/restart. Unproven mutation acknowledgements SHALL stop delivery without credit or blind replay.

#### Scenario: A player joins after communal preparation
- **WHEN** a communal reward transaction was prepared for Alice and Bob and Carol joins before delivery finishes
- **THEN** Carol is not added to that prepared transaction
- **AND** recipient ownership remains Alice and Bob across restart

#### Scenario: Bonus XP acknowledgement is lost
- **WHEN** the server may have granted bonus XP but its response is lost
- **THEN** the operation remains durably uncertain and Keeper credit is not awarded
- **AND** restart does not reissue the XP command or replace the captured benefit plan

### Requirement: Activate without inventing historical progress
First activation SHALL require explicit enablement and verified world/temple identity, initializing only that Keeper at zero XP without backfilling warm-up counters or resetting state. Existing quests and pending rewards SHALL retain their original obligations and issuer; successful post-activation completions SHALL credit that Keeper once.

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
Read-only status SHALL identify the selected Keeper and show its binding, lifetime total, earned rank, next milestone or cap, evolution enablement, installed temple rank, and blocked/uncertain upgrade. Rank advancement SHALL produce a best-effort issuer-identified announcement only after durable credit; status SHALL remain authoritative if interrupted.

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

### Requirement: Preserve temple-owned identity during multi-Keeper integration
Keeper identity SHALL remain bound to world identity, dimension, and original template minimum corner, independently of names or decorations. Integration SHALL preserve existing credits, installed ranks, upgrade intents, and frozen rewards under that identity. Only new Keepers SHALL start at zero; no copying, redistribution, or cross-temple synchronization SHALL occur.

#### Scenario: A leveled original temple becomes one of several Keepers
- **WHEN** multi-temple discovery finds original Keeper A at Warden and a new Keeper B
- **THEN** A retains its credited quest IDs, earned and installed ranks, and pending operations
- **AND** B starts at zero XP and Dormant without copying A's credit

#### Scenario: Prepared rewards cross the integration boundary
- **WHEN** A has a partially delivered offering and a partial or uncertain appearance upgrade during migration
- **THEN** the original issuer, source, recipients, prepared rank/action order, acknowledged progress, and uncertainty are retained
- **AND** neither rewards nor decoration steps replay or reset

### Requirement: Separate player rank credit from village prosperity
Player rank XP and local village-benefit credit SHALL remain distinct. Once village benefits are available, one fully successful player completion SHALL credit its issuer's enabled rank and village benefit once each in the same durable completion commit. NPC completions SHALL credit village benefits only; assistance and historical backfill SHALL not create rank or prosperity credit.

#### Scenario: A villager completes an NPC offering
- **WHEN** the villager's exchange fully succeeds at A
- **THEN** A can receive its bounded village benefit credit without changing A's rank XP
- **AND** no player reward or other Keeper's credit is granted

#### Scenario: Player completion is recovered after village integration
- **WHEN** a pending player quest becomes fully successful for A
- **THEN** A's lane progress, enabled rank XP, and applicable village credit commit once together
- **AND** replay cannot advance either ledger and earlier completed quests are not backfilled
