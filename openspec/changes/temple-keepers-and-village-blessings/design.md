# Design

## Context

See `proposal.md` for motivation and the four capability specs for the behavior contract.

Observed implementation boundaries:

- `director.py` stores one `State.communal_quest`, personal quests keyed only by player, and global lane counters. `Quest` has no Keeper/source identity. `source_slots()` and `source_descriptor()` resolve the global `OFFERING_CHEST`.
- `PendingReward` persists recipients, slot fingerprints, consumption commands, and uncertainty before external mutations. JSON saves use fsync and atomic replacement. This protection must survive the cutover.
- Communal recipients currently come from all online players. First-entry detection, temple membership, NPC ritual control, and healing/ward application do not exist.
- `quest_supply.AnvilWorldReader` reads stable Java 26.3 overworld region snapshots, checks loaded chunks through a callback, and observes item entities. It does not expose authoritative live villager state or a loaded-temple registry.
- The generation manifest records root sizes, altar/entry/chest offsets, and trusted geometry. `tools/village_temples.py --check` validated all 32 roots and 128 rotations during exploration. This is asset proof, not proof of live discovery, NPC walking, or effects.
- Only `village-temple-generation` and `live-world-regeneration` exist in the main spec inventory. Earlier active deltas use `adaptive-offering-quests`; this change keeps that capability path and explicitly supersedes its global hub/source/recipient assumptions, while retaining the current README's shared normal chest, warm-up, and uncertainty safeguards. Earlier ender-chest delta wording is historical, not the current operating contract.

## Goals / Non-Goals

**Goals:**

- One Director writer, with independent Keeper records and explicit ownership for every world mutation.
- Reuse existing player policy and transaction machinery while moving its state boundary from one global source to one temple.
- Make food-positive NPC exchanges a server-verified invariant, not a promise based on stale Python snapshots.
- Keep discovery and effects bounded, dimension-qualified, read-only where appropriate, and safe when chunks or entities disappear.

**Non-Goals:**

- No schema/configuration/implementation changes in this planning PR.
- No new physical Keeper, automatic construction, world replacement, or second persistence convention.
- No attempt to make Minecraft and filesystem/SQLite commits atomic. Native-AI interference and ambiguous RCON remain explicit recovery boundaries.

## Decisions

### 1. Registry from trusted template provenance and live verification

Introduce a focused temple registry module. Derive discovery candidates from stable saved village structure starts/pieces and the trusted root manifest, then resolve dimension, root anchor, rotation, entry bounds, altar approach, and designated chest. Reuse the existing NBT reader; do not scan arbitrary chests and call them temples.

Before activation, probe loaded state, identifying altar/temple cells, designated chest identity, and necessary clearance through read-only RCON. Saved coordinates are candidate evidence, not authorization to mutate. Already registered temple identities survive player edits; their operating surfaces must still pass live verification.

Scan saved candidates incrementally with a bounded per-poll budget, prioritize candidates near players for first encounters, and continually revisit the inventory of known generated temples so unloaded-to-loaded transitions are recognized even without nearby players. Newly generated but unsaved or unstable data must defer verification until authoritative evidence is available, not force a save or fabricate provenance. Do not install force-load tickets.

A stable `keeper_id` combines existing world identity, dimension, and original temple location; position is not a retry token. Overworld generated village temples are the supported discovery domain, while explicit dimensions prevent accidental coordinate collisions. Exact Java 26.3 structure-start anchoring/rotation decoding is a disposable-server acceptance gate; all four rotations and every supported village style must resolve the authored chest offset.

Alternative rejected: entity markers embedded in generation assets would miss existing temples and require changing generation semantics. A chest-only scan cannot establish trusted ownership.

### 2. Persistent altar identity and first-entry membership

Keep name, trusted personality archetype, and membership in the Keeper record. Allocate a stable locally generated name when the temple is first registered; persist it before introducing the character. First-entry detection uses live player positions and verified transformed temple bounds. Persist enrollment before issuing quests. Reentry presents existing work without duplicating membership or assignments.

Keep dialogue local to relevant players and ritual participants; altar particles and sound provide physical presentation without spawning a Keeper. Use safe text templates in demo/no-model operation. When the already configured LLM is enabled, it can phrase dialogue and select validated candidates, but never determines commands, protected reserves, reward budgets, or temple ownership. No per-poll model requests and no implicit change to billing/demo configuration.

### 3. Explicit Keeper-owned player state and sources

Replace global active quest maps/counters with `keepers[keeper_id]` records containing communal state, personal state keyed by player, per-lane timestamps/counters, and memberships. Each quest carries immutable `keeper_id`; each pending operation carries a dimension-qualified chest source independently of mutable configuration.

At assignment, use the issuing temple's verified hub for the 32-block warm-up observation and configured later local radius. Preserve the existing first-three-completions policy, catalog minima, deterministic strength bounds, next-band personal progression, fifth-assignment aspiration, and immediate successful replacement. Only eligible online members contribute to that Keeper's communal strength and rewards. Personal completion retains the current online-target policy.

Reserve items across all active/offline personal and communal work plus pending operations within the same Keeper source. Different temple chests can request the same item without collisions. NPC requests use a separate ledger and never supply player chest items.

Continue storing source fingerprints, commands, recipients, and uncertainty before consumption. Snapshot recipients as online eligible members of the issuer, not players standing near the chest. Pin retries/reconciliation to the original source; a missing chest cannot cause reassignment to another temple. Use one stable completion identity for player reward recovery, lane progression, optional settlement credit, and village blessing credit.

Alternative rejected: retaining global quest maps and adding only a display name would overwrite cross-Keeper personal assignments and retain unsafe global source resolution.

### 4. Guarded NPC operations in a server-side runtime function pack

Use a separate Java 26.3 function datapack for tightly guarded NPC exchanges and local effects, with a focused standard-library Python controller for durable scheduling and reconciliation. Keep it separate from immutable world-generation templates. RCON invokes trusted function/resource IDs and validated operation data; models do not generate commands.

For each operation, persist the Keeper, villager UUID, inventory snapshot, requested goods, compensation, reserve/capacity conditions, and operation ID before dispatch. The server-side exchange must validate the same live entity, loaded location, altar proximity, inventory components, and reserves; execute without yielding; secure compensation before the debit; and record a queryable completion marker for that operation. Failed validation must take nothing. Python queries that marker after acknowledgment loss instead of replaying an uncertain exchange. Retain uncertainty if the marker/entity is unavailable; never infer success from an empty response.

Use item-specific catalog rules derived from actual supported Java 26.3 inventory behavior. Start conservative: food nutrition is explicit, protected nutrition remains after the intended debit, profession goods require verified possession and an explicit working-stock floor, and planting seeds/tools/unsupported components are protected by default. A trade catalog is not an inventory. Reward sizing must keep donor nutrition positive even for mixed food inventories; a non-food offering still earns food while retaining its working-stock floor.

Compensation capacity is checked before accepting the operation. Do not spill rewards as item entities or commandeer unrelated inventory/equipment slots. Additional surplus distribution uses separate guarded, capped recipient grants after donor compensation; another villager's grant failure cannot replay the sacrifice.

Separate compensation from village surplus because only the donor's secured exchange is a prerequisite to debit. Permanent tests must cover changed inventories, full capacity, non-food floors, component preservation, and ambiguous execution, not mocked function-call forwarding.

### 5. Native visits and deterministic village ownership

Assign each eligible adult villager to one verified local Keeper, based on bounded locality and stable tie-breaking, keyed by UUID. Do not control transported distant villagers or depend on their profession to invent stock. One pending ritual per villager prevents overlapping temple debits.

Use bounded native-AI approach requests during safe daylight opportunities, aiming at the manifest's verified altar approach. Native walking must retain work, sleep, trading, and fleeing behavior; no teleportation, permanent `NoAI`, forced immobilization, or hidden distant sacrifices. On arrival, revalidate the inventory and perform a brief locally visible acknowledgment. Blocked routes and danger abort without debit.

Native Java 26.3 movement control and the non-yielding inventory exchange are explicit feasibility gates before integrating autonomous schedules. Verify them in a disposable world with real villagers and the existing stairs. If either gate fails, stop that implementation path and report the exact missing capability; do not ship silent inventory subtraction as a substitute for the agreed ritual.

### 6. Bounded prosperity, recovery, and local wards

Store village completion-credit identities, capped blessing expiry, recipient eligibility timestamps, and food-grant budgets alongside Keeper quest state. Keep optional settlement SQLite credit unchanged and idempotent; village benefits must work when settlements are disabled.

Each fully successful player or NPC quest records one local village credit. Credits extend healing/protection and a hostile-targeted ward only up to trusted caps. Recalculate effect duration from the persisted expiry when refreshing, rather than restarting full duration after a crash. Use bounded absolute expiry/eligibility times, reject invalid clock/state data, and never pay for missed unloaded intervals.

Configure conservative healing/protection strength, duration caps, service radius, nutrition/working floors, and assistance budgets in trusted policy. Healing targets the most injured eligible local villagers first, including non-donors. Safety-net food grants require verified low stock and capacity; durable per-villager and per-village rate limits prevent relog/reload farming. No escalating demands as population grows.

The ward applies finite weakness/slowness effects only to an explicit approved hostile list inside the verified local area. Do not use broad `@e` effects, spawn golems, alter difficulty/gamerules, remove enemies, or change blocks. Effect strength never stacks between overlapping Keepers. Villagers have deterministic assistance ownership, while hostile effects use the same bounded strength. No resurrection or guarantee against every cause of death.

Existing player potion effects and unrelated entity effects are not globally cleared when a temple pauses; Keeper-applied effects simply expire. Choose the supported effect IDs, refresh cadence, and hostile list through real Java 26.3 verification, then document their exact limits.

### 7. Suspension, dry-run, and clean migration

Distinguish unloaded/unverifiable from missing/replaced/obstructed sources. Suspend new activity for the affected temple only, preserve all debt, and report the cause. Admin repairs can allow safe resumption, but uncertain operations still require verified reconciliation. Never clear a chest, replace a block, change world identity, or reset counters as recovery.

Use one versioned quest JSON migration in the existing fsync/atomic-save convention. Map the original single-source quests and counters only to the verified original configured temple. Preserve exact quest IDs, original pending commands/fingerprints, historical captured recipients, uncertainty, and settlement idempotency keys. Do not manufacture historical memberships: new communal completions use observed entry membership, while already prepared historical recipient snapshots remain frozen. Keep legacy personal assignments intact with their original target.

Ambiguous source mapping blocks affected operations rather than moving them. Dry-run previews migration and all Keeper/NPC/effect activity using non-persistent state and read-only probes; no persistent enrollment, credits, grant markers, or effects. Remove obsolete global runtime aliases after successful migration instead of retaining two source-resolution conventions.

## Risks / Trade-offs

- Native AI movement may not expose a safe writable Java 26.3 control surface -> prove it with real villagers before integration; no visual or behavior claim from fake RCON.
- Compensation/debit/marker mechanics may be incompatible with the target item schema -> prove guarded server-side exchange and interruption behavior before any autonomous writer activation.
- Structure-start data can be stale or unloaded -> treat saved data as discovery hints, require live probes, and defer first interaction until verification rather than force-saving/loading.
- Multiple simultaneous Keepers increase quest/reward volume -> bound per-poll work, preserve per-Keeper cooldowns/reservations, and cap local prosperity budgets.
- Positive feedback can become an unlimited resource farm -> strict capacity/need checks, working reserves, staggered NPC cadence, and persistent recipient/village budgets; no catch-up payouts.
- Resistance, healing, and wards do not guarantee survival or create beds -> document limits and verify combat behavior without claiming invulnerability or guaranteed population growth.
- Active earlier deltas overlap the player capability -> reconcile the spec lineage before archiving; do not overwrite newer Keeper rules with older global/ender-chest wording.
- RCON and state commits cannot be atomic -> persist intent, use queryable server operation markers where proven, preserve uncertainty otherwise, and reconcile offline from matched backups.

## Migration Plan

### Repository implementation and acceptance

1. Implement only after this planning change is reviewed and an apply request is made. Keep tests isolated and live services untouched during planning/development.
2. Prove discovery/rotation, native approach, and guarded exchange in a disposable Java 26.3 world. Then integrate the complete behavior, versioned migration, admin diagnostics/reconciliation, and read-only previews.
3. Run deterministic behavior regressions, generator validation, admin CLI smoke, and real multi-temple/NPC/combat/restart scenarios. Verify first-entry dialogue and visible ritual in a vanilla client; server checks alone do not prove them.
4. Update README operating/configuration contracts, retaining world identity and both persistent stores. Resolve the existing spec lineage before synchronization/archive.

### Separately authorized deployment and rollback

1. Merge the reviewed implementation through the normal PR workflow. Stop the Keeper writer before updating its mounted source; preserve unrelated checkout files and configuration.
2. For the runtime datapack/config/state migration, use writer-stopped maintenance, flush and stop Minecraft as required, and create complete matched world/state/private-config backups. Record installed source/pack versions and checksums without exposing secrets.
3. Install reviewed runtime pack copies explicitly. No regeneration or terrain replacement is required by this design; do not apply historical generation-cutover instructions to this runtime update.
4. Start with the writer disabled, require actual server readiness, verify datapack availability and read-only discovery/migration previews, compare state checksums, and inspect chest ownership and loading.
5. Activate exactly one writer only after acceptance. Verify original state migration, temple membership, local NPC/ward behavior, and persistence; restore any temporary admission controls/runtime masks.
6. If migration/mutation ownership is uncertain, stop writers and reconcile the verified operation offline or restore the complete matched backup generation. Never downgrade only the JSON/schema after the world has changed, discard pending debt, or retry uncertain sacrifices.

## Open Questions

- Exact effect strength/duration, service radius, assistance budget, and supported profession-goods floors are conservative policy tuning, to be fixed and documented after the specified Java 26.3 probes; they cannot weaken the behavioral reserve, locality, capacity, or boundedness requirements.
- Keeper naming/archetype vocabulary can be chosen during presentation work without changing persistent identity or quest ownership.
