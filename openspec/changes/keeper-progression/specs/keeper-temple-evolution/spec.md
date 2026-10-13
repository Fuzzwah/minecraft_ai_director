# Spec Delta

## Purpose

Make each opted-in Keeper temple reflect its own earned rank through persistent decorative milestones that preserve offerings, access, player edits, and independent progress at unrelated temples.

## ADDED Requirements

### Requirement: Register verified temple evolution explicitly
Evolution SHALL require explicit per-temple opt-in and a binding to its stable Keeper identity, Java 26.3 root variant, minimum corner, facing, and decoration definition. Its transformed chest SHALL match its quest source. The initial levels feature SHALL operate only the original registered temple; later discovery SHALL neither enable evolution nor authorize another temple's upgrades.

#### Scenario: Registration matches a generated temple
- **WHEN** the registered root variant and facing reproduce the configured chest and baseline temple geometry
- **THEN** that temple is eligible for guarded evolution
- **AND** all other village temples remain unchanged

#### Scenario: Registration or durable binding disagrees
- **WHEN** chest coordinates, world identity, geometry, or decoration definition differ from the durable binding
- **THEN** mutation is rejected with the conflicting binding reported
- **AND** progress is not reset and an alternative temple is not selected

#### Scenario: Another Keeper is discovered later
- **WHEN** multi-temple discovery registers Keeper B while A has opted into evolution
- **THEN** B's evolution remains disabled and A retains its existing enablement and installed rank
- **AND** B's discovery or rank does not install decorations at either temple

### Requirement: Installing assets does not activate retrofits
Installing code, decoration definitions, or the generation pack SHALL NOT itself change existing temples. Explicit evolution enablement and verified registration for that Keeper SHALL be required. Generation roots, village selection, spawn, and chest locations SHALL remain unchanged.

#### Scenario: Updated assets are installed without activation
- **WHEN** the Director runs with Keeper evolution disabled
- **THEN** existing temples and player edits remain unchanged
- **AND** newly generated villages retain the ordinary baseline temple appearance

### Requirement: Apply cumulative visible rank milestones
The temple SHALL retain its sandstone landmark form. Awakened SHALL add altar and entrance lighting; Warden SHALL add paired static copper-golem sculptures; Exalted SHALL enrich the idol and selected gold/copper accents; Ascendant SHALL complete sanctuary lighting and the sun motif. Sculptures SHALL use stable waxed copper building blocks, not living entities or extra containers.

#### Scenario: Warden appearance is installed
- **WHEN** the registered temple safely advances from Awakened to Warden
- **THEN** two recognizable copper-golem sculptures flank the sanctuary without occupying its chest approach
- **AND** the Awakened lighting remains installed

#### Scenario: Ascendant appearance is installed
- **WHEN** all four earned appearance milestones have safely completed
- **THEN** the enriched idol, sculptures, lighting, and sun motif form one cumulative final appearance
- **AND** the original staircase, columns, pediment, and sandstone identity remain recognizable

### Requirement: Change only authored decorative cells
Each milestone SHALL change only its approved, bounded decorative cells from exact expected states to exact target states. Whole-template replacement, terrain clearing, broad fills, arbitrary coordinates, and overwrite fallbacks SHALL be prohibited. Unsupported states or unapproved block-entity/entity payloads SHALL reject the mutation.

#### Scenario: A decorative cell has been edited
- **WHEN** a target cell differs from the exact expected predecessor state
- **THEN** the milestone stops before dispatching changes to that unstarted patch
- **AND** the player's block is preserved rather than treated as terrain to clear

#### Scenario: A container occupies a statue cell
- **WHEN** a player places a chest where a sculpture is planned
- **THEN** the upgrade is blocked without reading, emptying, or replacing that chest
- **AND** no fallback placement is attempted elsewhere

### Requirement: Preserve offering and traversal clearance
Every intermediate and completed appearance SHALL preserve the offering chest, its contents and lid space, the altar approach, supported entrance stairs, two-block walking clearance, road connections, and protected volumes. Decorations SHALL NOT remove required supporting terrain or use sensitive blocks as replacement targets.

#### Scenario: Players revisit an upgraded temple
- **WHEN** a supported temple has any installed milestone rank
- **THEN** a player can walk from its road to the altar and open the same offering chest without jumping or breaking blocks
- **AND** unrelated offering items and player edits outside decorative cells remain unchanged

### Requirement: Guard each mutating command against unsafe surroundings
Mutation SHALL require affirmatively loaded affected chunks, no player intersecting the registered temple exclusion volume, and exact expected target states. These conditions SHALL guard each mutating command, not only the initial inspection. Unloaded chunks, protected-region conflicts, unreadable probes, or players SHALL defer an unstarted mutation without changing blocks.

#### Scenario: A player enters after preview
- **WHEN** inspection found an empty temple but a player enters before a block command is dispatched
- **THEN** the command's player guard prevents the block change
- **AND** the milestone is not reported as successfully installed

#### Scenario: A chunk is unavailable
- **WHEN** any affected chunk cannot be affirmatively confirmed loaded
- **THEN** no upgrade command for that unsafe step mutates the world
- **AND** the Director does not force-load terrain or move the registered temple to bypass the guard

### Requirement: Persist intent before mutation and protect uncertain steps
Milestone identity, bound geometry, expected/target states, dispatch progress, and uncertainty SHALL be durable before mutation. A lost or ambiguous acknowledgement or a crash during dispatch SHALL protect the unfinished upgrade from replay. Empty, generic, negative, or wrong-state responses SHALL NOT be treated as proof of installation.

#### Scenario: A block-change reply is lost
- **WHEN** Minecraft may have changed a decorative block but the response was lost
- **THEN** the upgrade remains uncertain and the writer stops for explicit reconciliation
- **AND** restart does not resend that step or mark the milestone complete from appearance alone

#### Scenario: A guard prevents a dispatched command
- **WHEN** an exact-state or environment guard prevents the change
- **THEN** the milestone is not advanced without affirmative command and post-state evidence
- **AND** an acknowledgement that cannot distinguish the outcome leaves a protected uncertain record

### Requirement: Advance appearance only after exact verification
A temple's installed rank SHALL advance only after all its milestone steps and complete target/access state are verified. Its earned milestones SHALL install in predecessor order without borrowing another Keeper's rank. Ordinary decoration blockers SHALL retain earned progress and allow safe quests; actual chest/access failures SHALL suspend affected source activity.

#### Scenario: Two milestones are due
- **WHEN** earned rank is Exalted and installed appearance is Awakened
- **THEN** Warden is installed and verified before Exalted begins
- **AND** an incomplete Warden patch cannot be skipped by placing the Exalted appearance

#### Scenario: Installation finishes but final verification fails
- **WHEN** target cells or required clearance cannot be verified after acknowledged steps
- **THEN** installed rank does not advance
- **AND** status retains the blocked operation and its evidence without reconstructing the temple

### Requirement: Preserve completed appearances without reconstruction
Saved milestone appearances SHALL persist through world saves, chunk unloads, and restarts. Completed milestones SHALL NOT replay, repair player changes automatically, or duplicate sculptures. A later milestone SHALL reject edits in its required predecessor decoration footprint rather than rebuilding an earlier appearance.

#### Scenario: An installed decoration is changed after restart
- **WHEN** a player modifies a completed statue and the Director restarts
- **THEN** that edit remains intact and Warden is not reapplied
- **AND** a subsequent dependent milestone is blocked if the edited statue violates its expected predecessor

### Requirement: Preserve identity across authorized appearances
Authorized milestones and recorded partial upgrade states SHALL retain the original Keeper identity and source. Provenance-backed discovery SHALL recognize them using invariant identifying cells or trusted rank-aware geometry, not demand a baseline idol/lighting pattern. Recognition SHALL NOT mark an uncertain operation complete, repair player edits, or create another Keeper.

#### Scenario: Discovery revisits an upgraded original temple
- **WHEN** later multi-temple discovery verifies A's provenance, invariant cells, and chest after a Warden upgrade
- **THEN** it resolves the original A identity with its saved installed rank rather than enrolling a new Keeper
- **AND** valid sculptures or an ordinary decorative blocker do not falsely report the chest as damaged

### Requirement: Provide read-only previews and paired recovery
A preview SHALL report the binding, earned/installed ranks, next ordered milestone, intended block transitions, and safety blockers without persistent writes. Uncertain recovery SHALL require stopped writers, paired world/quest-state backups, inspection of exact operation records and blocks, and deliberate offline reconciliation; resets, blind retries, or identity changes SHALL NOT substitute for recovery.

#### Scenario: Preview an eligible milestone
- **WHEN** an admin previews the next milestone
- **THEN** the actual temple is inspected using read-only probes and all planned target cells are reported
- **AND** inventory, world blocks, quest JSON, and any settlement database remain unchanged

#### Scenario: Restart encounters uncertain upgrade state
- **WHEN** saved upgrade intent indicates an interrupted dispatch
- **THEN** the writer refuses mutation and reports the operation requiring reconciliation
- **AND** the saved world identity and earned progress remain unchanged

### Requirement: Verify supported appearances on the target runtime
Authored patches SHALL be validated against real bundled NBT for all five styles, normal/abandoned roots, every rank, and all four rotations. Acceptance SHALL additionally exercise actual mutations, guards, blessings, and persistence on isolated vanilla Java 26.3; client rendering, sculpture recognition, traversal, and chest usability SHALL be verified with a client rather than inferred from mocks.

#### Scenario: A rotated desert temple is upgraded
- **WHEN** the supported desert root is bound in any of the four facings
- **THEN** every transition uses the correct rotated position and block properties without replacing processor-altered terrain
- **AND** the cumulative upgraded geometry preserves required support and access

#### Scenario: Verification lacks a Minecraft client
- **WHEN** only asset checks, automated tests, or RCON evidence are available
- **THEN** that evidence is not presented as proof of visual rendering or player traversal
- **AND** client-only acceptance remains explicitly unverified until exercised
