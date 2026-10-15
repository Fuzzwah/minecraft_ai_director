# Spec Delta

## Purpose

Provide persistent, distinct Keeper presences at verified loaded village temples, with local interaction, reliable offering-chest identity, and non-destructive suspension.

## ADDED Requirements

### Requirement: Discover verified loaded temples
The system SHALL recognize every loaded generated Keeper temple using trusted world and temple evidence, including its dimension and orientation. An arbitrary chest or lookalike altar SHALL NOT authorize a temple. Discovery SHALL NOT force-load chunks, generate terrain, or rewrite blocks.

#### Scenario: Two rotated temples are loaded
- **WHEN** two supported generated temples with different orientations are loaded
- **THEN** each is identified with its own altar, entrance, and designated chest
- **AND** both can operate independently

#### Scenario: Evidence is missing or ambiguous
- **WHEN** temple provenance or geometry cannot be verified
- **THEN** the candidate does not authorize inventory mutations or blessings
- **AND** an arbitrary nearby chest is not substituted

### Requirement: Preserve one altar presence per temple
Each verified temple SHALL have one persistent Keeper identity, name, and personality anchored to its altar. The Keeper SHALL speak through local text, sound, and altar effects without requiring a physical Keeper mob, custom client, or external model call. Personality SHALL NOT alter safety or reward eligibility.

#### Scenario: Another player visits after a restart
- **WHEN** a previously recognized temple is revisited after restart by a different player
- **THEN** the same named Keeper introduces itself
- **AND** no second identity or physical Keeper is created

### Requirement: Introduce and enroll first-time visitors
The first verified temple entry by a player SHALL record that player's membership, introduce the named Keeper, and attempt that Keeper's communal and personal quest assignments. Existing assignments SHALL be retained, and unavailable safe candidates SHALL defer issuance. Membership SHALL survive restarts.

#### Scenario: First and repeated entry
- **WHEN** a player first enters a healthy temple and later leaves and reenters it
- **THEN** the first entry introduces and enrolls the player
- **AND** reentry does not duplicate membership, restart warm-up, or duplicate active quests

#### Scenario: New member finds an active communal quest
- **WHEN** a new visitor joins a Keeper with an active communal quest
- **THEN** the visitor is informed of that quest rather than creating a competing communal assignment
- **AND** a personal assignment is attempted only if safe candidates remain

### Requirement: Verify the designated offering chest
Each active temple SHALL have a verified loaded normal offering chest at its designated position, with usable access and lid clearance. Existing contents and metadata SHALL be preserved. A different chest, ender chest, or unloaded container SHALL NOT substitute for that source.

#### Scenario: Loaded chest contains player goods
- **WHEN** a healthy temple is discovered or revisited with items already in its chest
- **THEN** those items and their metadata remain intact
- **AND** discovery does not empty, replace, or initialize the container

### Requirement: Report and suspend damaged temples
A missing, replaced, or obstructed designated chest SHALL cause a report and suspension of that temple's new assignments, sacrifices, assistance, and blessings. Other healthy temples SHALL continue operating. Suspension SHALL preserve identity, membership, quests, reserves, and pending transactions; no automatic repair or relocation SHALL occur.

#### Scenario: Player removes one temple chest
- **WHEN** a player removes the designated chest from one of two loaded temples
- **THEN** the affected temple is reported and suspended without placing a replacement
- **AND** the other temple remains operational
- **AND** the affected Keeper's durable records remain intact

#### Scenario: Admin restores the designated chest
- **WHEN** an admin repairs the source and its identity, access, and loading are verified again
- **THEN** the existing Keeper can resume safe activity
- **AND** uncertain transactions remain suspended until reconciled

### Requirement: Pause unloaded temples without losing identity
A temple whose relevant chunks are not verifiably loaded SHALL perform no world or inventory mutations. Unloading SHALL NOT be treated as chest destruction, clear its state, or accumulate missed assistance or ritual payouts. Reloading SHALL restore the same Keeper and outstanding work without replay.

#### Scenario: Unload and reload a village
- **WHEN** a temple unloads and later reloads
- **THEN** it retains its name, membership, quests, and pending operations
- **AND** it receives no burst of missed donations or safety-net rewards

### Requirement: Keep interactions local and bounded
Keeper introductions, quest reminders, and ritual effects SHALL identify their speaker and reach relevant visitors or local participants rather than globally broadcasting every temple's activity. Multiple loaded temples SHALL NOT require separate concurrent Director writers or unbounded work per poll.

#### Scenario: Players visit different temples
- **WHEN** players are visiting different Keepers concurrently
- **THEN** each receives the appropriate local Keeper's introduction and assignments
- **AND** introductions do not appear as an unrelated global narrator's message

### Requirement: Preview all Keeper activity without mutation
Dry-run SHALL use read-only world probes and non-persistent state copies. Discovery, membership previews, player completion previews, NPC exchanges, safety-net assistance, and blessing previews SHALL not change persistent JSON, SQLite, world blocks, inventories, entities, effects, or rewards.

#### Scenario: Preview a loaded multi-temple world
- **WHEN** dry-run inspects healthy and suspended temples with eligible player and NPC work
- **THEN** it reports proposed activity and suspension reasons
- **AND** persistent state and world checksums remain unchanged
