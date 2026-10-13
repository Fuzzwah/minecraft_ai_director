# Proposal

## Why

Completing Keeper quests currently rewards players but leaves the Keeper and its sanctuary unchanged. Shared, persistent Keeper progression will make every player's offerings contribute to a growing protective presence, with useful blessings and visible temple milestones.

## What Changes

- Introduce one world-bound Keeper progression track, independent of optional settlements. Each successfully completed personal or communal quest earns one Keeper XP, once per quest rather than per recipient or difficulty tier.
- Unlock five ranks at cumulative completion totals 0, 3, 10, 25, and 50: Dormant, Awakened, Warden, Exalted, and Ascendant. Rank caps at Ascendant; the lifetime completion total continues growing.
- Grant brief, deterministic protection/utility blessings and modest bonus player XP points at higher ranks. Preserve existing item rewards, base player XP levels, quest difficulty, candidate supply rules, and lane ownership. Freeze the earned rank and benefit plan when an offering transaction is prepared; the milestone-crossing quest unlocks benefits for subsequent offerings.
- Evolve only the explicitly registered active offering temple: altar/entrance lighting, paired static copper-golem sculptures, richer idol and gold accents, then a radiant sanctuary/sun motif. Preserve the existing sandstone landmark, stairs, chest, lid clearance, and road access.
- Use small, authored exact-state block transitions with durable mutation intent, loaded-chunk and player guards, and no whole-template replacement. Track earned rank separately from installed appearance so an ordinary decoration obstruction does not block future quests or discard Keeper XP.
- Start existing worlds at zero Keeper XP without resetting their quests, warm-up counters, players, settlement database, or temple. Add explicit opt-in configuration, read-only status/preview, rank announcements, and operating/recovery documentation.

### Scope and non-goals

Target vanilla Java 26.3 and the existing shared normal offering chest. Scope includes all five temple styles, normal/abandoned authored variants, and four rotations, but only one admin-registered temple is mutated in a given world. Static sculptures use stable waxed copper building blocks, not living golems or entity-based displays.

No world regeneration, historical-completion backfill, multiple-temple synchronization, living NPC, permanent aura, offensive blessing, rare-item inflation, prestige/reset mechanic, LLM-selected powers, new Python dependency, settlement enablement, or production deployment is authorized by this proposal. Installing source or a generation pack alone must not activate temple upgrades.

## Capabilities

### New Capabilities

- `keeper-progression`: Durable shared rank advancement, idempotent completion credit, rank-defined blessings/bonus XP, recipient ownership, opt-in migration, and observable progress.
- `keeper-temple-evolution`: Explicit temple registration, authored milestone decoration transitions, exact-state safety, durable upgrade recovery, and separation of earned rank from installed appearance.

### Modified Capabilities

None. `village-temple-generation` continues to govern the unchanged generation assets and their non-retroactive installation; explicitly enabled runtime decoration is owned by `keeper-temple-evolution`, not automatic regeneration or reconstruction. Existing offering requirements retain their shared-chest and lane-safety contract.

## Impact

- `director.py`: Extend `State` and `PendingReward` serialization/migration, frozen reward planning, successful completion commit, duplicate-completion rejection, and main-loop milestone processing. Preserve existing settlement obligations and lane scheduling.
- Proposed `keeper.py`: Standard-library rank policy, trusted temple binding/patch validation, guarded upgrade execution, and status/preview helpers without constructing a `StructureManager`.
- `tools/village_temples.py`, proposed `config/keeper_temples.json`: Derive versioned decoration transitions from the real bundled roots and validate cumulative appearances/rotations. Do not alter the generation roots to activate this feature.
- Proposed read-only `keeper_admin.py`, `tests/test_director.py`, `tests/test_village_temples.py`, targeted Keeper safety tests, and `README.md`: Progress inspection, consumer-visible regression coverage, isolated Java 26.3 and client acceptance, configuration, backups, and recovery.
- Durable state remains in `DIRECTOR_STATE`; preserve any existing `DIRECTOR_DATABASE` and world/configuration as the same generation. Explicit activation binds Keeper records to a stable admin-assigned world identity and the verified temple geometry.
- Planning conflict: `adaptive-offering-quests` still contains older ender-chest/two-container delta text. Current source, README, the main temple spec, and the later `greek-temple-shared-offerings` artifacts use one shared normal chest. This change builds on that current contract and does not revive or silently rewrite the stale proposal.
