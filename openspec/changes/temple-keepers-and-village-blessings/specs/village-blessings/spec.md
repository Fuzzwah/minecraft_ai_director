# Spec Delta

## Purpose

Make local villages healthier through bounded Keeper healing, protective blessings, and hostile-targeted defensive wards earned by both player and NPC quests.

## ADDED Requirements

### Requirement: Credit local prosperity from both quest populations
Fully successful player and NPC quests SHALL earn bounded village benefit credit at their issuing Keeper. Each completion SHALL credit that village once, independently of player reward ownership. Failed, uncertain, retired, or dry-run work SHALL not grant completion credit; another temple SHALL not receive or redeem it.

#### Scenario: Player completes a personal quest
- **WHEN** a player's personal quest from A fully succeeds
- **THEN** its target receives the existing personal reward and A receives village benefit credit once
- **AND** B does not receive that credit

#### Scenario: NPC completes a sacrifice
- **WHEN** an NPC exchange at A fully succeeds
- **THEN** A receives benefit credit separately from player quest progress
- **AND** the donor is not required to be an online player

### Requirement: Heal local villagers including non-donors
Earned blessings SHALL periodically heal injured eligible villagers inside the issuing Keeper's verified local service area, prioritizing greater injury under bounded policy. Healing SHALL include non-donors and SHALL not require another sacrifice. Safety-net healing SHALL remain modest and independently rate-limited.

#### Scenario: Injured villager cannot donate
- **WHEN** an injured local villager has no safe surplus during an active blessing
- **THEN** it can receive healing without losing goods or completing an NPC quest

#### Scenario: No local villager is injured
- **WHEN** a healing pass finds only healthy villagers
- **THEN** it does not produce food, player rewards, or artificial completion credit

### Requirement: Apply bounded protective blessings
Earned local blessings SHALL provide temporary damage resistance to eligible villagers with configured strength and duration caps. Further completions SHALL only extend benefits within those caps. Blessings SHALL not grant permanent invulnerability, alter unrelated player effects, or promise protection against every cause of death.

#### Scenario: Many quests finish in succession
- **WHEN** multiple completions arrive while a blessing is already active
- **THEN** protection remains within its configured duration and strength limits
- **AND** repeated completions do not create permanent or unbounded effects

### Requirement: Actively weaken local threats with a defensive ward
An active earned blessing SHALL maintain a bounded defensive ward that weakens or slows trusted hostile entity types within its local service area. Targeting SHALL exclude players, villagers, friendly entities, and mobs outside that area. The ward SHALL not kill, teleport, delete, or spawn entities, rewrite terrain, or change global difficulty or gamerules.

#### Scenario: Approved attacker enters a blessed village
- **WHEN** an approved hostile entity enters A's active ward area
- **THEN** it receives the bounded ward's weakening or slowing effect
- **AND** nearby villagers remain eligible for healing and protection

#### Scenario: Player or distant hostile is nearby
- **WHEN** a player is inside the ward or a hostile is outside its boundary
- **THEN** that entity receives no hostile-targeted ward effect

### Requirement: Keep benefits local without multiplying overlap
Each Keeper SHALL have a verified bounded village service area independent of its players' current positions. Villager eligibility and overlapping ward application SHALL use deterministic ownership and caps so adjacent temples do not multiply assistance or effect strength. Travelling members SHALL not carry village wards to other locations.

#### Scenario: Communal member completes from elsewhere
- **WHEN** A's communal completion rewards an online member located near B
- **THEN** village benefits remain at A
- **AND** that member's location does not move or duplicate A's ward

#### Scenario: Two service areas overlap
- **WHEN** two active wards cover the same approved hostile or eligible villager
- **THEN** effect strength remains capped rather than adding together
- **AND** food assistance eligibility is not multiplied by the overlap

### Requirement: Persist benefit ownership and expiry safely
Village credit, completion identities, assistance budgets, and blessing expiry SHALL survive restart. Unloading or suspension SHALL stop new benefit application without force-loading or accruing missed rewards. Resuming SHALL use recorded expiry rather than restarting the full blessing duration. Existing effects SHALL expire naturally and not be globally cleared.

#### Scenario: Restart after credited completion
- **WHEN** the Director restarts after A's quest credited a blessing
- **THEN** the recorded blessing retains its original capped expiry
- **AND** the same quest does not credit it again

#### Scenario: Chest disappears during a blessing
- **WHEN** A is suspended because its designated chest is missing
- **THEN** A performs no further healing or ward refresh until safe resumption
- **AND** unrelated temples and unrelated effects remain unchanged
