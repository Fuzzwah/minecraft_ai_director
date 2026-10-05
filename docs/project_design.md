# Minecraft AI Director: vanilla 26.3 project design

## 1. Status, supported platform, and product

This is the implementation and production acceptance contract for the shipped Python owner, vanilla datapack, SQLite journal, player triggers, and operator CLI. The individual inventory-at-spawn prototype has been removed. Real vanilla 26.3 gameplay, inventory/recovery paths, multiplayer paging, and configured-model fallback have been exercised; this does **not** certify every production acceptance gate. See the verification record and remaining limits at the end.

**The only Minecraft target is the official, unmodified Minecraft Java Edition 26.3 dedicated server.** No Paper, Bukkit, Spigot, Fabric, Forge, server plugins, or client mods are required or supported. A vanilla datapack is part of the application. Python runs alongside the server and communicates through vanilla RCON.

### Verified release baseline

Mojang's version manifest identifies `26.3` as the current release, distinct from the newer `26.4-snapshot-2` snapshot. The exact 26.3 metadata specifies Java major version **25**. The final release notes specify data-pack version **121.0** and resource-pack version 97.1; no resource pack is required here. These values were checked on 2026-10-05.

Pin the release, not a moving `latest` alias. Do not silently adopt snapshots, another release, or legacy datapack/item schemas. Compatibility changes require a tested application release.

| Component | Supported target |
| --- | --- |
| Server and clients | Official Minecraft Java Edition 26.3 release |
| Server runtime | Java 25, as specified by Mojang's 26.3 metadata |
| Datapack | Exactly data-pack version 121.0; no advertised cross-version range |
| Director | Python 3.11+; standard-library runtime dependencies |
| Reference host | Linux/POSIX; local filesystem access, RCON, and advisory process locking |
| Multiplayer | Online-mode, whitelisted, trusted private community |

The finished product offers one cooperative collection quest at a time. Everyone can contribute to a designated chest. On success, exactly the requested items are consumed and each eligible player online at completion receives an individual reward entitlement. Rewards are inserted into that player's personal Ender Chest when online and space is available.

### Goals and non-goals

Goals: an understandable cooperative loop, visible progress, exact consumption, safe normal-operation payouts, bounded AI costs, offline/full-inventory waits, audit history, and honest crash recovery. The model supplies flavor and chooses from approved objectives; it never owns commands or rewards.

Non-goals: contributor attribution or weighted payouts; combat/exploration/crafting objectives; multiple active quests or delivery chests; custom item rewards; offline player-file editing; public-server anti-grief guarantees; custom slash-command registration; distributed directors; Minecraft Realms; support for older versions, snapshots, Bedrock, modified servers, or third-party APIs.

This design supersedes the earlier plugin architecture. Do not retain a second plugin implementation, plugin bridge, permission-node model, or alternate server target.

## 2. Binding gameplay rules

| Topic | Required behavior |
| --- | --- |
| Objective | One community collect quest; no assigned player. |
| Chest | One registered ordinary single chest, 27 slots, in the Overworld. Coordinates are independent of world spawn. |
| Attribution | Anyone can contribute; the system does not identify depositors. |
| Progress | Current matching chest contents, not cumulative deposits. Withdrawals lower progress. |
| Consumption | Exactly the target quantity, ascending slot order. Preserve unrelated stacks and surplus. |
| Leftovers | Existing contents may count toward later quests. Registration itself requires an empty chest. |
| Recipients | UUID snapshot of eligible online players taken inside the server-side completion function immediately before consumption. |
| Eligibility | Online survival/adventure players on the whitelisted server, excluding configured UUIDs. No contribution, AFK, or minimum-attendance test. |
| Reward | Same preselected vanilla item stack for every recipient; deposited into personal Ender Chest. No XP. |
| Full/offline | Persist pending entitlement indefinitely. Retry known-safe waits, never overwrite items. |
| Expiry | Two hours of healthy active time with an eligible player online. No consumption or rewards on expiry/cancellation. |
| Cooldown | Default ten minutes of healthy time after completion, expiry, or cancellation; configurable down to zero for immediate succession. Fresh state is immediately eligible. Readiness and daily caps still apply. |
| AI unavailable | Python selects a local approved candidate with fixed flavor. |
| Python unavailable | Datapack stops accepting destructive requests when its heartbeat expires. Scheduling/payouts pause; existing inventory contents remain untouched. |
| Unknown mutation outcome | Quarantine the operation for operator review; do not blindly retry. |

Online-at-completion is deliberately a community reward rule, not proof of contribution. Helpers who leave before the snapshot receive nothing; eligible players present receive a reward even if they did not donate. A recipient who disconnects after the snapshot retains the entitlement. The server whitelist controls admission; explicitly exclude operator/testing accounts if they must not receive rewards.

Pending or reviewed player payouts do not block unrelated recipients or new quests. Uncertain chest consumption blocks new quests because collection state is unknown.

## 3. Architecture and ownership

### Components

1. **Python director:** owns SQLite, scheduling, candidate generation, AI calls, command construction, pending entitlements, checkpoint coordination, audit history, and operator tools. One process executes mutations.
2. **Vanilla datapack:** owns synchronous inventory checks/mutations, completion recipient snapshots, trigger handling, boss bar rendering, structured results, operation receipts, and a heartbeat guard. It uses only vanilla functions, command storage, scoreboards, predicates, and supported item commands.
3. **Vanilla RCON:** the authenticated transport between Python and installed datapack functions. There is no Minecraft-side HTTP server or custom server API.
4. **Optional LLM provider:** OpenRouter or another OpenAI-compatible endpoint, including local Ollama. AI outage does not stop a running director.
5. **Minecraft persistence:** player files, chunks, command storage, and scoreboards. These are separate persistence domains from Python's database.

Python is required for the complete game loop. Do not claim autonomous AI fallback or pending-reward processing when it is stopped. The datapack provides paused/status messages and guards; Python resumes after checking the world, session, and journal.

### Why the datapack is required

Do not implement completion as Python reading a chest followed by independent slot-replacement commands. Players or block ticks can change state between RCON commands. A datapack function rechecks and performs an inventory operation in one synchronous server execution, with no asynchronous scheduling between those checks and writes.

This closes normal player/block-tick interleaving during that function, not every failure window. Functions are command sequences, not rollback-capable transactions; an unexpected command error or process crash can interrupt a sequence. SQLite cannot atomically commit with Minecraft files. Sections 7–9 specify conservative handling.

### Process and performance boundaries

- Acquire an OS advisory lock before connecting or executing game operations. Refuse a second director for the same state directory/server. Document that running two separately configured writers against one world is unsupported.
- Serialize all RCON mutation requests through one dispatcher. AI and disk/network work cannot enqueue uncontrolled command bursts.
- Run model requests off the polling path so a slow provider does not stop heartbeats, progress, claims, or pending delivery.
- Keep the datapack's synchronous functions bounded: scan 27 chest/Ender Chest slots, handle one chest operation or one player payout at a time, and enforce configured recipient/result size limits.
- No inventory mutation waits for Python, HTTP, or SQLite inside a function. Prepare the local intent before dispatching it.
- Use RCON connection/authentication/request-ID validation, full packet framing, and bounded multi-packet response handling. A partial response is not a successful operation result.
- Bind/restrict RCON to localhost or a protected private connection; RCON is not encrypted. No public exposed RCON port.

## 4. Player experience and vanilla controls

Name the chest `The Keeper's Offering Chest` during registration using vanilla block data. A nearby ordinary sign explains the chest and `/trigger` commands; no command-bearing sign is required. Display the chest's Overworld block coordinates in every objective.

Construct factual announcements from validated state, for example:

> [The Keeper] Iron for the village! Bring 32 iron ingots to the Offering Chest at Overworld (12, 64, -8). Progress: 0/32. Each eligible player online at completion receives 2 diamonds in their Ender Chest. Time remaining: 2h.

Optional AI flavor is a separate literal sentence. It cannot replace factual count, item, location, eligibility, deadline, or reward. JSON text components must encode generated content as text, not click events, command strings, NBT text, or rich-text markup.

### Progress and notifications

- Poll/reconcile chest progress every five seconds; do not claim instant inventory-event hooks.
- Datapack completion rechecks current contents regardless of the last displayed count.
- A boss bar shows `min(found, target) / target` while active. Show it to eligible online players; hide or mark it paused when unhealthy.
- Announce 25%, 50%, and 75% milestones once each. If a deposit crosses several, announce only the highest new milestone. Withdrawals do not rearm milestones.
- Remind every ten active minutes, with one warning at ten minutes remaining; privately show status to newly observed online UUIDs.
- Announce completion once during ordinary retries, with optional title/sound. Notification failure must never initiate a new inventory operation.
- Rate-limit full-Ender-Chest reminders to one per UUID per ten minutes.

### Player commands

Vanilla datapacks cannot register an arbitrary `/keeper` command. Use trigger objectives:

| Command | Behavior |
| --- | --- |
| `/trigger keeper_quest` | Current factual objective/progress/location/time/reward or paused status. |
| `/trigger keeper_status` | Caller-visible quest state and pending reward count; no other player's private data. |
| `/trigger keeper_claim` | Request delivery of the caller's oldest pending reward; no capacity/eligibility override. |
| `/trigger keeper_help` | Rules and the available trigger commands. |

The tick function handles/reset/enables triggers with bounded work. Status/help can use the last synchronized datapack projection. Claim marks a UUID request for Python to process; it does not trust a player-supplied item, reward tier, quantity, UUID, or operation ID. While the director heartbeat is stale, answer that service is paused instead of attempting payouts.

Normal players need no operator permission for enabled triggers. Operator tools live in the local Python CLI, not fictitious plugin permission nodes. Root/operator users who can run arbitrary vanilla commands already possess server authority and are trusted.

## 5. Objective generation, difficulty, and economy

Python constructs up to five valid candidates. The AI selects a candidate and writes title/flavor; it cannot invent counts or select recipients/rewards. Local fallback uses the same persisted candidate set and economy rules.

### Initial catalog

Only plain vanilla stacks qualify. Reject custom names, lore, enchantments, custom model data, explicit custom-data tags, and non-default gameplay components. Use exact supported-version predicates/data comparisons, not material ID alone, and never strip item components to make a stack qualify. Counts span slots.

| Item ID | Base quantity | Allowed community range | Effort weight |
| --- | ---: | ---: | ---: |
| `minecraft:iron_ingot` | 6 | 6–48 | 3 |
| `minecraft:copper_ingot` | 8 | 8–64 | 1 |
| `minecraft:gold_ingot` | 4 | 4–24 | 6 |
| `minecraft:coal` | 12 | 12–96 | 1 |
| `minecraft:redstone` | 12 | 12–96 | 1 |
| `minecraft:lapis_lazuli` | 8 | 8–64 | 2 |
| `minecraft:oak_log` | 12 | 12–96 | 1 |
| `minecraft:bread` | 6 | 6–48 | 2 |
| `minecraft:carrot` | 10 | 10–80 | 1 |
| `minecraft:cooked_beef` | 6 | 6–48 | 3 |

For `N >= 1` eligible players when generation begins, set quantity to `ceil(base * sqrt(N))`, clamped to bounds. Points are `quantity * effort_weight`: tier 1 at 24 or fewer, tier 2 at 25–80, tier 3 above 80. These are initial balancing decisions, not universal item valuations.

Exclude item IDs from the last three completed/expired quests when alternatives exist. Persist seed, candidate set, computed tiers, and candidate reward choices before calling the model. A restart or retry never rerolls. Configuration changes affect future quests only.

### Rewards

Select and store one exact item stack at activation. All completion recipients receive the same stack; the AI never selects it.

| Tier | Possible per-player rewards |
| --- | --- |
| 1 | 3 emeralds OR 4 gold ingots |
| 2 | 2 diamonds OR 8 emeralds |
| 3 | 4 diamonds OR 1 ancient debris |

A configured reward is one plain item type whose quantity fits in one supported maximum-size stack. Reject multi-item bundles, custom components, invalid IDs, and counts exceeding that item's stack limit. This keeps capacity checks and insertion small and inspectable. No XP, fallback `/give`, dropped-item delivery, or shared reward chest.

Start with twelve activations and twelve AI-call reservations per UTC day. Count fallback/admin starts against activation allowance; already-created pending rewards do not count again. No catch-up quest burst after downtime. An explicitly audited administrator override can bypass activation allowance but not item validation or unresolved-operation guards.

Because rewards are per person, total issuance is per-player count multiplied by the completion snapshot size. Show both values in history. Set a deployment participant bound, initially twenty; reject dispatch with a larger recipient snapshot before consuming anything and require the owner to deliberately raise/test the bound. Do not silently trim recipients. Catalog, reward table, server player limit, and daily cap are owner-controlled economy knobs.

## 6. Lifecycle and time accounting

| State | Required behavior |
| --- | --- |
| `IDLE` | Wait for readiness, eligible players, cooldown, and allowance. |
| `GENERATING` | Persist generation/candidates and start a 45-second deadline. Accept one valid model result or local fallback while healthy. |
| `ACTIVE` | Display progress, monitor expiry, and check completion. |
| `PAUSED` | Offline community, explicit pause, heartbeat/RCON/storage fault, or chest/setup fault. Preserve prior state and remaining time; no destructive dispatch. |
| `COMPLETING` | Journal intent, execute synchronous completion, verify/checkpoint result, and commit entitlements. Expiry/cancel cannot interleave with dispatch. |
| `COMPLETED` | Consumption acknowledged and all entitlements created transactionally in SQLite; start cooldown independently of delivery waits. |
| `EXPIRED` / `CANCELLED` | Preserve contents; create no entitlements; start cooldown. |
| `REVIEW_REQUIRED` | Unknown chest outcome. Block new completion/generation until operator resolution. |

Terminal records remain in history; the scheduler returns to `IDLE` with a separate cooldown counter. Reward processing has independent per-entitlement states.
`cooldown_seconds=0` schedules one successor after completion without waiting for pending/full rewards. It does not bypass unresolved chest operations, offline readiness, activation caps, or catch up multiple missed quests. The deployed live profile uses zero cooldown; the configuration example retains the ten-minute default.


Use Python monotonic time for runtime elapsed durations. Count active/cooldown time only while RCON/datapack/chest/storage are healthy and an eligible player is online. Count generation timeout while Python is running; if everyone leaves or readiness is lost, retain any chosen proposal/fallback but do not activate until readiness returns. Do not issue another provider call for that generation.

Persist timer counters every thirty seconds and on transitions/orderly shutdown. UTC time is for logs/daily caps, not elapsed-deadline calculations. Downtime/all-offline time does not advance active or cooldown time. At most thirty seconds of timer progress may be lost on a crash; inventory intents must be committed before dispatch.

Heartbeat every five seconds, with a datapack stale threshold of 600 server ticks. Tick lag can lengthen that wall-clock threshold; Python also fails closed on its own timeouts. On load/reload, the datapack disables destructive dispatch until a new verified handshake. On resume, reconcile all journal entries before enabling new operations.

At completion, the datapack checks the registered chest, expected quest/revision, plain matching count, and current eligible recipients. Insufficient contents, no recipients, or excessive recipients causes a non-mutating result. Expiry wins if the director has observed elapsed time reaching the deadline before dispatch. Once a valid completion request is dispatched, its result must be resolved before expiry/cancel can proceed.

## 7. Delivery chest and exact consumption

### Registration and vanilla protection limits

- One empty `minecraft:chest` with single-chest block state in `minecraft:overworld`, identified by integer coordinates and an installation/world identity stored in command storage.
- Persist registration in both SQLite and datapack configuration. Compare them on startup. Do not claim vanilla exposes a Bukkit world UUID or supports arbitrary plugin block tags.
- Use `/forceload` for the registered chunk, recording whether the application added that ticket. Unregister/remove only a ticket owned by the application; never delete another operator's existing force-load setup.
- Configure a trusted, whitelisted server and a designated spawn-area collection build. Use vanilla spawn protection and a hopper-free, nonflammable, protected layout where practical.
- Spawn protection is not a plugin-grade chest guard: operators bypass it, and environmental damage, existing automation, or direct commands need separate operational control. No guarantee of intercepting break/explosion/piston/click events.
- Do not place hoppers/droppers or an adjoining chest in the build. Check single-chest identity and nearby incompatible automation at registration/doctor; pause if the block/type changes. Ordinary players must follow the collection-area rules.
- Never recreate a missing chest, replace the block, or overwrite its contents automatically. Pause and require inspection/re-registration.
- Vanilla chest locking does not close existing viewers or stop all automation. Do not rely on `Lock` as a transaction mutex or promise to eject/lock player GUIs.

Players can deposit and withdraw normally. Wrong items occupy space but do not count. Do not delete, relocate, or refund them to an inferred owner. The system is suitable for a cooperative private server, not hostile users with unrestricted build/command access.

### Completion pipeline

1. Python stores a `PREPARED` operation with quest/revision, target, expected catalog code, quantity, and evidence reference. The server-side recipient snapshot is not invented from a prior Python `list` response.
2. Stage a typed request in command storage and call one approved completion function over RCON.
3. Inside that synchronous function, validate readiness/session, chest type/location, active quest/revision, duplicate operation receipt, catalog/count bounds, and plain item contents. Capture the full before-state and actual recipient UUID/name snapshot into temporary command storage. Abort without changes if insufficient/unready.
4. Compute the complete after-state in scratch storage, scanning slots in ascending order and reducing only matching plain stacks. Preserve every untouched stack/component. Verify exact removal count before touching the real chest.
5. Mark a receipt `RUNNING`, apply the prepared chest slot/list changes, and verify after-state. Each write must have checked success. On success publish `APPLIED` with recipient snapshot, exact consumed count, and before/after evidence. Unexpected error after any mutation is uncertain, not a safe failure.
6. Python reads the correlated result/evidence, requests `save-all flush`, and waits for a verified successful checkpoint response. A lost/failed checkpoint response does not authorize payout replay or new consumption.
7. In one SQLite transaction, acknowledge the operation, mark the quest complete, store immutable recipients, create unique entitlements, and queue a completion notice. Then begin cooldown. Separate reward operations deliver those entitlements.

The function must not `schedule` any inventory mutation across later ticks. Normal player packets/hopper block ticks cannot interleave within its synchronous command sequence; stale client actions afterward are processed under vanilla inventory rules. Validate actual client/server synchronization during release testing instead of assuming that replacing block data behaves like a plugin API.

Chest operation failure/review suppresses new mutations; it does not magically freeze physical access. Inform the operator and request that players leave the chest untouched until review. Historical whole-chest restoration is prohibited because it can destroy subsequent deposits.

## 8. Personal Ender Chest rewards

An Ender Chest inventory belongs to a player UUID, not a placed Ender Chest block. Deliver only while that UUID is online. Never edit offline `playerdata` or try `/data modify entity` to write a player's inventory; use supported vanilla item commands in the datapack.

### Entitlement rules

- Identity is `(quest_id, player_uuid)`, unique in SQLite. Names are display snapshots only; renaming must not change reward ownership.
- Store exact item/count at quest activation and completion. Pending delivery never consults the current reward table or rerolls.
- States: `PENDING`, `WAITING_OFFLINE`, `WAITING_SPACE`, `DELIVERING`, `DELIVERED`, `REVIEW_REQUIRED`, and explicitly audited `VOIDED`.
- Scan the 27 Ender Chest slots in ascending order and use the first empty slot only. Do not merge into existing player stacks or use a broad slot source that replaces multiple slots.
- If there is no empty slot, change nothing. One entire configured reward stack is the unit of delivery.
- Process oldest entitlements first, one per player per attempt. Pending records never expire automatically or block another player's rewards.

### Safe normal-operation delivery

1. Persist a local delivery intent before sending it. Request includes a validated UUID, entitlement ID, immutable reward code, expected server session, and unique operation ID.
2. Inside one synchronous function, resolve the UUID to a currently online player. The UUID is obtained from server data; do not insert an arbitrary caller/model selector or target by a potentially stale name.
3. Check readiness and operation receipt, locate the first empty Ender Chest slot, and publish a `RUNNING` receipt containing target/slot/expected reward. Offline/full results are non-mutating.
4. Recheck that exact slot is empty and execute `/item replace entity` for that single slot, then verify its item/count/components. Do not blindly use `enderchest.*`, `/item fill`, or `/item override`.
5. Write an `APPLIED` command-storage receipt and correlated response. Python checkpoints with `save-all flush` and acknowledges the entitlement in SQLite. Receipts are in command storage, not invented custom player NBT fields.
6. Send a private delivered/pending message. Later movement of a delivered reward is allowed and never creates another entitlement.

Automatically attempt after completion, when polling discovers a newly online UUID, every sixty seconds for pending online recipients, and on claim requests. A serialized dispatcher prevents login/timer/claim from running separate attempts at once. A player can change their Ender Chest between polling calls, so the emptiness check must occur inside the same function as insertion.

Minecraft 26.3 retains string slot-range shorthand such as a single `enderchest.0` slot, but expands slot-source and replacement semantics. Use precise single-slot commands and test the official 26.3 behavior. Commands execute without player actions between their synchronous checks/writes; this is not crash atomicity.

To reduce checkpoint overhead, a bounded delivery batch may contain at most eight individually journaled operations followed by one `save-all flush`. None becomes `DELIVERED` before that checkpoint is acknowledged. Unknown batch checkpoint outcome puts all applied but unacknowledged operations in review. Measure the save cost on the actual server; never silently weaken checkpoint policy to improve tick time.

## 9. Persistence guarantees and recovery

### What is guaranteed, and what is not

Known normal-operation delivery never overwrites an existing stack; duplicate requests within the verified server session return their receipt without reinserting. The database creates at most one entitlement per completion recipient. Full/offline waits do not consume a reward.

**SQLite, command storage, chunks, scoreboards, and player files do not form one atomic transaction.** A function can fail after a write; a crash or mismatched restore can preserve a reward but lose its receipt, or preserve a receipt while rolling back inventory. Neither a receipt nor a successful save command proves universal power-loss atomicity.

The contract is conservative: no automatic replay of unknown destructive outcomes, visible review state, and operator-controlled reconciliation. Do not market this as exactly-once delivery, automatic inventory rollback, or full anti-grief protection.

### Journal and startup reconciliation

Persist intent before any command that can mutate inventory. Journal states are `PREPARED`, `DISPATCHED`, `APPLIED`, `COMMITTED`, `ABORTED`, and `REVIEW_REQUIRED`. Record request/result hashes, session, quest/revision, target UUID/coordinates, complete before/after evidence, server receipt phase, and checkpoint outcome. `DISPATCHED` must be durable before issuing the dispatch command.

On director/server restart or a changed datapack load epoch, every nonterminal destructive operation enters review before new operations for that target. An unresolved player operation blocks only that player's payouts; a chest operation blocks collection. Ordinary player gameplay is not globally frozen. Database corruption/schema errors fail closed, not to empty state.

Within an uninterrupted verified server session, a lost RCON response may be recovered by reading a complete matching receipt without re-executing the mutation. A missing or `RUNNING` receipt after possible dispatch is uncertain. Do not resend on the assumption that no response means no effect.

Server epoch is a reload/start handshake discriminator, not a proof that a restore was consistent. A stored numeric load counter can itself roll back. After any restart, compare backup/world installation identity and checkpoint evidence and review nonterminal operations regardless of the counter.

A checkpoint compares the world/SQLite pair, not each player file. Independent player-only rollback can leave those identities unchanged and is not automatically detectable. The operator must use confirmation-bound `quarantine` on affected committed issuance before choosing a resolution; it changes metadata only and never overwrites current inventories.

### Operator resolutions

A review command shows the stored plan, target, current state if readable, receipt, checkpoint evidence, and risk. Inventory observations are evidence, not proof of who moved items. A reward can have been claimed/moved after insertion.

- `commit`: acknowledge an already-applied operation without repeating it. Chest commit creates the original frozen recipients' entitlements exactly once; payout commit marks delivered without reinsertion.
- `abort`: operator certifies no mutation occurred, returning the quest/entitlement to a safe retryable state.
- `compensate`: preview and explicitly authorize a typed corrective item delta or payout, using a new journaled operation and capacity checks. Require a reason acknowledging duplication/loss risk.
- `void`: explicitly cancel/waive the affected quest or entitlement without deleting audit evidence.

Require a single-use confirmation token bound to operation revision for every resolution/override. No arbitrary command text, full historical inventory overwrite, inferred depositor refund, or silent pending-reward deletion.

### Failure table

| Failure | Required response |
| --- | --- |
| AI error/timeout/invalid JSON | Local candidate within generation deadline while Python is healthy. |
| Python stopped | Heartbeat guard stops destructive functions; no autonomous quest generation. |
| RCON dropped/partial response | Read matching receipt if session is verified; otherwise review. Never blind replay. |
| Database/disk failure | Stop new destructive dispatch and scheduling; retain journal/files and show pause. |
| Chest missing/double/replaced | Pause and alert; no automatic block repair. |
| Player offline/full Ender Chest | Known non-mutating wait; retain entitlement and retry normally. |
| Function error after write or uncertain save | Review, not ordinary retry. |
| Notification failure | Retry notification only; no replay of consumption/reward. |
| Mismatched backup restore | Start paused, reconcile all affected issuance and receipts. |
| Duplicate director | Refuse owner lock; never elect another writer during an uncertain operation. |

## 10. SQLite, datapack storage, and RCON protocol

### Database

Use Python's `sqlite3`, foreign keys, WAL, `synchronous=FULL`, and explicit transactions. One owner process maintains authoritative state. Back up with the backup API or a stopped-process coordinated copy; a live main-file-only copy omitting WAL is not sufficient. Version schema and migrations; back up before upgrades and refuse destructive startup after a migration failure.

| Record | Required data/constraint |
| --- | --- |
| `server_state` | Installation/world identity, expected Minecraft/protocol version, active quest, timer counters, config revision, UTC caps, backup generation. |
| `chests` | Installation/chest ID, dimension, coordinates, expected single-chest state, owned force-load ticket. One registered chest. |
| `generations` | UUID/revision, seed, candidate/reward snapshots, model call reservation/status, chosen proposal, elapsed deadline. |
| `quests` | UUID, objective/tier/exact reward, prose/source/model, status/timers, config snapshot, terminal reason. One live quest enforced by partial unique index. |
| `recipients` | Unique quest ID + player UUID, display/eligibility snapshot taken by completion function. |
| `entitlements` | UUID, unique quest ID + player UUID, exact reward, status/wait reason, attempts/timestamps/terminal reason. |
| `operations` | Unique operation ID, kind/target/session/revision, exact request, receipt phases, before/after evidence, result, checkpoint, review/resolution data. One nonterminal operation per inventory target. |
| `notifications` | Stable event ID, audience/type/content, status and rate-limit metadata. Separate from payout state. |
| `audit_events` | Sequence/time, local operator or service actor, action/IDs, state changes, redacted details, required reason. |

Use an installation UUID plus monotonic database sequence for operation IDs; do not reuse IDs after restore/reinstall. Preserve unresolved history indefinitely and terminal history/receipts for at least ninety days. Coordinated receipt pruning requires acknowledged terminal rows and matching backup generation; it cannot make a closed quest executable again.

Preserve actual 26.3 NBT numeric types, arrays, components, and slot contents in evidence. Fingerprint complete canonical typed data, not item ID/count or raw whitespace. A version upgrade must not reinterpret unresolved evidence under another schema.

### Datapack layout and identity

Use the `keeper` namespace, the singular resource directories supported by 26.3 (`function`, `predicate`, and `slot_source` when used), vanilla load/tick function tags, and exact data-pack 121.0 metadata. Package a versioned world datapack with no server jar patch, plugin dependency, or resource-pack dependency.

Load initializes objectives and a disabled runtime, increments a load epoch, and preserves existing receipts/configuration. It must not erase journals, pending projections, or operation evidence. Datapack removal/reload requires pausing/checkpointing the director first.

Storage roles:

| Storage | Purpose |
| --- | --- |
| `keeper:config` | Protocol/build, expected installation/world identity, registered chest, exclusion list, catalog/reward codes and limits. |
| `keeper:runtime` | Enabled/session/heartbeat, load epoch, active quest/revision, public projection, bounded pending/claim UUIDs and acknowledged claim cursor. |
| `keeper:bridge` | Staged request and correlated response. One serialized writer. |
| `keeper:journal` | Immutable operation receipts/evidence, including `RUNNING`/`APPLIED` and explicit review decisions. |
| `keeper:work` | Bounded function-local validation/planning scratch; not authoritative history. |

### Typed request/response transport

1. Python commits an intent and constructs SNBT from validated typed values; never interpolate raw LLM text into command grammar.
2. Stage a complete request using `data modify storage keeper:bridge request set value ...`.
3. Execute `function keeper:bridge/dispatch` once. The function dispatches only known action codes and validates protocol/session/revision/catalog limits before calling internal functions.
4. Read `data get storage keeper:bridge response`. Parse the root compound with a bounded SNBT parser and validate correlation. Human-readable RCON wrapper text is not the payload or the success test.
5. Read evidence pages/receipt as needed, checkpoint, then acknowledge in SQLite. Queries and receipt reads are non-destructive.

Minimum request fields: `protocol` (1), `installation_id`, `session_id`, `request_id`, `operation_id` for destructive operations, `action`, and `expected_revision`. Payload depends on action: validated chest registration, immutable quest projection, completion objective code/quantity, payout UUID/reward code/entitlement ID, or a read-only cursor. Reject unknown fields/action codes, stale sessions/revisions, oversized input, invalid UUIDs, and counts outside approved definitions.

Responses have `protocol`, `request_id`, `operation_id` when relevant, `session_id`, `status`, `revision`, and a typed payload. Stable statuses include `OK`, `APPLIED`, `INSUFFICIENT_ITEMS`, `OFFLINE`, `NO_SPACE`, `NO_RECIPIENTS`, `RECIPIENT_LIMIT`, `SESSION_MISMATCH`, `STALE_REVISION`, `STALE_PREFLIGHT`, `EVIDENCE_LIMIT`, `IDEMPOTENCY_CONFLICT`, `INVALID_REQUEST`, `CHEST_INVALID`, `PAUSED`, and `REVIEW_REQUIRED`. An identical applied operation returns its original `APPLIED` result, not a new inventory write. Include actual consumed/inserted counts and receipt IDs; never infer success from a nonempty response.

Approved actions: `HELLO`, `HEARTBEAT`, `SNAPSHOT`, `REGISTER_CHEST`, `UNREGISTER_CHEST`, `ACTIVATE`, `PUBLISH_STATUS`, `COMPLETE`, `PAY`, `READ_RECEIPT`, `READ_EVIDENCE`, `READ_CLAIMS`, `ACK_CLAIMS`, `CHECKPOINT`, `RESOLVE_RECEIPT`, and `PAUSE`. Operator compensation uses the same typed inventory actions, not an arbitrary command endpoint.

`HELLO` compares installation, exact game version, pack build/protocol, configuration hash, and load epoch. Record the verified 26.3 server identity from official server metadata/startup information; a datapack self-declared version alone is not proof of the running jar. Fail closed on mismatch. Heartbeats refresh a short-lived session; startup must not auto-resume unresolved operations.

Within a verified live session, identical operation ID plus request hash returns its existing completed result. Reusing an ID with different payload rejects. A `RUNNING` receipt rejects replay and enters review. Fingerprints must compare complete data rather than NBT subset matches. Server-restored receipts are evidence requiring reconciliation, not a universal idempotency guarantee.

Bound logical requests to 16 KiB and physical RCON frames to 1400 bytes; use typed multipart staging when needed. Bound response/evidence pages to 8 KiB, public projections to 6 KiB, each item stack to 4 KiB, and total per-operation evidence to 1 MiB. Snapshot/receipt pages carry at most 16 players, fully assembling up to the hard bound of 128; default completion recipient cap is 20. Refuse a destructive request non-mutatingly if full typed inventory evidence exceeds the limits. Support complete RCON packet assembly with a whole-command deadline; never silently truncate components. The bounded SNBT parser handles escaped strings, compounds/lists, numeric suffixes, booleans, and typed arrays. Do not parse inventory with `parse_first_int`, regex fragments, or `eval`.

The official 26.3 RCON handler reads a single frame into a 1460-byte buffer and closes on a combined/partial input frame. Keep requests within the physical bound and do not pipeline the `list` response barrier: send it only after receiving the first original response. All response packets remain assembled under one deadline. Network failure still requires review, not retry. Stop a payout batch on lost connectivity before creating further intents.

### 26.3-specific implementation cautions

The official release changes slot-source semantics for `/item` and `/execute if items`, adds `/item fill` and `/item override`, renames loot-function fields (`function` to `type`, conditions to `condition`), and removes some server log lines. String slot-range shorthand remains available. Do not copy an old datapack unchanged, assume `Count` versus `count`, or assert removed log messages are mandatory. Capture the real 26.3 item/block/player/storage output and validate each function/predicate against it.

The 26.3 text codec treats `interpret:false` storage text as rendered SNBT, including string quotes. UI functions validate exact NBT string types before using `interpret:true` to decode literal string components; model text is never a compound with click/hover actions. Numeric plain text and the short catalog-derived boss-bar label do not interpolate command grammar.

No custom HTTP bridge, plugin API, `Player.getEnderChest()`, plugin save method, inventory-event interceptor, or player persistent-data API belongs in the implementation.

## 11. AI integration and privacy

Use OpenAI-compatible Chat Completions. OpenRouter requires no SDK:

```text
https://openrouter.ai/api/v1/chat/completions
```

Python uses `LLM_URL`, exact `LLM_MODEL`, and optional `LLM_API_KEY` as bearer authorization. Hosted endpoints normally require a key; a trusted local Ollama endpoint can omit it. The Python process holds the RCON secret for transport but must never include it, database contents, or command templates in model context.

Provide up to five persisted candidates, community participant count, and up to twenty recent allowlisted event summaries. Keep forty summaries only in memory; use salted pseudonymous labels. Raw chat collection is off by default. Optional `share_chat=true` / `SHARE_CHAT=1` accepts public vanilla player messages only from exact current validated identities, with at most 256 printable Unicode characters; reject slash commands, console echoes, unknown/stale names and invalid text. Before provider sharing, quote chat as explicitly untrusted context and redact known player names and UUID/IP literals. Chat may guide narrative or approved candidate selection but cannot authorize commands, rewards, objectives or recipients. `share_events=false` omits all event context. Do not persist chat in the ledger/audit or log raw prompts; vanilla public chat logs still exist. Arbitrary secrets/personal information in message bodies cannot be reliably scrubbed, so hosted-provider disclosure requires this explicit opt-in. Join/leave summaries derive from UUID snapshots; optional advancements/deaths use observed logs when available. Missing event types never block readiness or gameplay. Source startup/rotation/outage recovery begins at EOF, without replaying old chat. The vanilla server-management protocol is not required.

Model response schema:

```json
{
  "candidate_id": "candidate-2",
  "title": "Iron for the village",
  "flavor": "The Keeper's workshop needs a little help from the community."
}
```

Require a JSON object with exactly these keys, current candidate ID, and nonempty strings. Strip an optional code fence, reject unrelated surrounding text/control characters, trim whitespace, and reject title over sixty Unicode code points or flavor over 220. Do not silently truncate to validate. Reject wrong types/unknown keys. Datapack objective/reward codes still come from Python's approved catalog, not generated prose.

The system prompt defines a concise family-friendly narrator and labels recent events untrusted context. Render generated content literally. This restricts authority, not guaranteed appropriateness; an operator can disable flavor or the provider entirely and retain local quests.

Set temperature 0.8, maximum output 300 tokens, one in-flight provider request per generation, and thirty-second request deadline. Reserve the daily call allowance in SQLite before the request. A generation marked request-started is not sent again after a restart or unknown HTTP outcome; use fallback instead. No hidden model substitution, repeated malformed-output repair calls, quota/authentication retries, or provider failover outside explicit configuration.

While Python remains healthy, select fallback by the generation's 45-second deadline. Once a quest activates, discard late responses for that generation/revision. Optional structured-output settings may be used only if supported; local schema validation is mandatory regardless. Store source/model/latency/error category and provider token usage if available, never authorization headers or secrets.

Hosted calls disclose sent context to the router/provider. Explain this during setup, make event sharing configurable, support a local provider, and keep raw prompt/response logging off by default. Opt-in debug capture requires a disclosure warning and bounded retention.

## 12. Configuration and operator interface

### Target settings

These settings are implemented; explicit JSON and environment configuration determine the deployed values.

| Setting | Default / rule |
| --- | --- |
| `MINECRAFT_VERSION` | `26.3`, fixed supported release; reject another value. |
| RCON host/port/password | `127.0.0.1` / `25575` / required secret. |
| `DIRECTOR_DB` | `.runtime/director.sqlite3`; persistent writable directory, restrictive permissions. |
| `DIRECTOR_CONFIG` | `./director_config.json`; catalog/rewards/exclusions/operational limits. |
| Delivery chest | Explicit registration; Overworld integer coordinates, no implicit spawn fallback. |
| Expiry/cooldown | 7,200 / 600 healthy active seconds by default; cooldown may be zero for immediate succession. |
| Poll/heartbeat | 5 seconds each; datapack stale threshold 600 server ticks. |
| Payout retry / maximum batch | 60 seconds / eight operations before checkpoint. |
| Generation deadline / provider timeout | 45 / 30 seconds. |
| Daily activation/call caps | Twelve each per UTC day. |
| Recipient limit | Twenty; validate before consumption, never silently trim. |
| Eligible modes / exclusions | Survival and adventure / configured UUID list. |
| Reward delivery | One plain stack to first empty Ender Chest slot; no XP/pending expiry. |
| `LLM_URL`, `LLM_MODEL`, `LLM_API_KEY` | Explicit provider settings; model/key omitted from committed secrets. |
| `DEMO_MODE` | `1` forces local generation; still performs real Minecraft operations. |
| `MINECRAFT_LOG` | Optional context; never authoritative inventory/recipient state. |
| `SHARE_CHAT` / `share_chat` | Disabled by default; opt-in bounded untrusted public-chat context. `SHARE_EVENTS=0` disables all event sharing. |
| History | Ninety days minimum; unresolved evidence and pending rewards never pruned. |

Validate the full configuration, exact release/pack protocol, item IDs/components/stack limits, coordinates, UUIDs, interval bounds, caps, and state directory before enabling. Catalog/reward changes apply to future quests; active records retain snapshots. Chest change requires idle/no unresolved operation and explicit unregister/register. Never silently coerce invalid model integers, config bounds, or absent state into safe-looking defaults.

### Operator CLI

Use `python3 director.py admin ...` (with the owner's `--config` before `admin` when needed). Administrative calls reach the running owner process over an owner-only local Unix-domain socket, not a public web server or Minecraft plugin. Socket/state permissions and same-UID peer credentials restrict access; requests allow only typed actions. If the director is down, administrative commands cannot run and world mutations cannot proceed; filesystem inspection/backup must be read-only. Capture local OS actor identity and required reason in audit events.

| Subcommand | Required behavior |
| --- | --- |
| `doctor` | Exact running/expected release, pack/protocol/session, chest setup, DB integrity, pending/review counts, last checkpoint. |
| `chest register <x> <y> <z>` | Idle-only registration of empty Overworld single chest and owned force-load setup. |
| `chest unregister --reason <text>` | Idle/no unresolved operations; preserve block/items and remove only owned force-load ticket. |
| `pause --reason <text>` / `resume` | Stop new dispatch; preserve timers; reconcile/validate before resume. |
| `start <item-id> <quantity>` | Catalog-validated local objective, computed tier/reward, normal cap. |
| `start-override <item-id> <quantity> --reason <text>` | Explicit confirmation-bound cap bypass, never inventory validation/review bypass. |
| `cancel <quest-id> --reason <text>` | Cancel active/generating quest, preserve contents, no reward. Cannot bypass dispatched completion. |
| `history [quest-id]` | Immutable objective/reward/recipient count/status and operation references. |
| `rewards <player-uuid>` | Pending/delivered/review entitlements and exact wait reason. |
| `review <operation-id>` | Read-only evidence, receipt/checkpoint, current observations, proposed resolutions. |
| `quarantine <operation-id> --reason <text>` | Preview confirmation-bound metadata-only quarantine of committed issuance after independent player-file rollback; pause before resolution, never overwrite inventory. |
| `resolve <operation-id> <commit\|abort\|compensate\|void> --reason <text>` | Preview typed resolution and issue single-use revision-bound confirmation token. |
| `confirm <token>` | Execute only the still-current reviewed action. |
| `reload-config` | Validate all settings, apply only safe-boundary changes, report deferred changes. |

These commands are implemented. Confirmation tokens are actor/revision-bound and single-use. Vanilla console `/function` controls used for installation/diagnostics require operator authority; player triggers cannot invoke admin methods or specify arbitrary operation payloads. `resume` cannot bypass unresolved review.

## 13. Deployment, security, and backups

### Installation

1. Install the official 26.3 server with Java 25. Verify artifact/version against Mojang's metadata and accept the Minecraft EULA as the server owner; no automatic EULA acceptance by the director.
2. Enable online mode, whitelist/enforce-whitelist, and private RCON. Use a long unique RCON password. Build a designated collection area and review spawn protection/automation risks.
3. Place the exact 121.0 datapack under the world's `datapacks` directory and load it. Confirm it is enabled and its load function begins disabled without erasing state.
4. Configure Python/state directory; initialize the owner lock and database, perform handshake/doctor, and register the empty chest. No gameplay mutations occur until readiness succeeds.
5. Configure OpenRouter/local provider or demo mode; start the director as a non-root service with restrictive environment-file/log/socket permissions and restart-on-failure.
6. Run the real-server acceptance scenarios before using the production world. Test AI failure separately from Python outage; their behavior is different.

The isolated helper uses rootless direct Podman, a pinned `itzg/docker-minecraft-server` Java 25 image, `mc_ai_director_test_data`, pasta, restart policy `no`, UID/GID 1000, and loopback-only 25566/25576 publications. It never changes `mc_do_not_die`. Creation requires explicit owner EULA approval and defaults to online mode/enforced whitelist; offline fixtures are local-only. Generated environment files are private data, not shell scripts. New servers disable empty-server pausing with `PAUSE_WHEN_EMPTY_SECONDS=0`; production must likewise set `pause-when-empty-seconds=0`. The optional systemd user unit manages only the Python owner.

No third-party server API or client modification is allowed. Realms is excluded because this design requires operator-owned RCON/process/filesystem access.

RCON credentials grant arbitrary server command authority even though this application exposes only constrained functions. Keep them private, restrict outbound/provider access where practical, use HTTPS for hosted AI, and allow plain HTTP only for a trusted local provider/tunnel. Generated content must not become command grammar. Other datapacks/operators modifying the target chest/Ender Chest during a critical sequence or reusing the `keeper` namespace are unsupported.

### Observability

Structured logs include quest/generation/operation IDs, state changes, consumed/issued counts, recipient count, provider latency/error class, wait reasons, and review actions. No secrets or full private Ender Chest contents in routine logs. Review evidence is owner-only. Doctor exposes readiness, heartbeat age, chest identity, supported versions, pending count/oldest age, and review count.

Public messages explain pauses without stack traces. Notification IDs prevent duplication during ordinary retries; crash-adjacent messages may still be duplicated/missed, and must not control game state.

### Shutdown and coordinated restore

- Stop scheduling and accepting claims, drain or quarantine dispatched operations, checkpoint timers/SQLite, and request a verified `save-all flush` before orderly shutdown.
- Safest backup: stop director and server, then copy world (including chunks/playerdata/scoreboards/command storage), datapack/configuration, director database, and installation/backup identity together. Use SQLite's backup API or include required WAL state correctly.
- A live backup requires a certified quiesce/checkpoint procedure; do not copy independent stores at arbitrary times.
- Restore all stores from the same generation. Start paused and reconcile nonterminal operations. Any partial/mismatched restore requires review of affected committed issuance too; an old world can revive consumed items or erase delivered rewards.
- Preserve corrupt/mismatched files and show actionable errors. Never create an empty database/state after a load/integrity failure.
- Datapack/server upgrades are unsupported until validated on a copy, with no unresolved item evidence interpreted under another version. Version history alone does not establish consistent application backup state.

## 14. Cutover and implementation boundaries

Stop the prototype before deploying the target. Archive `director_state.json`; cancel any individual quest visibly. Migration itself consumes nothing and invents no unpaid rewards. Preserve all world/items and initialize the new database/installation identity explicitly.

Replace individual `Quest.player`, spawn-radius inventory checks, first-integer output parsing, arbitrary reward-command templates, model-selected tiers, and JSON quest persistence with shared objectives, typed datapack requests, server-derived UUID snapshots, and the SQLite ledger. Keep RCON and optional log context; they remain vanilla-compatible. Remove obsolete callsites/settings rather than keeping two quest formats or engines.

The intended deliverables are the revised Python director, a vanilla 26.3 datapack, configuration examples, deployment documentation, and real-server regression/acceptance evidence. No server plugin artifact, modified jar, custom Minecraft HTTP bridge, or parallel Paper implementation belongs in the repository.

Keep a tagged prototype release for rollback. Rollback requires stopping the target and resolving/archiving pending/review records first. Do not run the old and new systems against the same live world.

The README describes the shipped cutover, real smoke evidence, and remaining production certification limits. Official release availability and documented commands alone are not evidence of acceptance; the observed runtime checks below are narrower than the full section 15 release matrix.

## 15. Verification and release acceptance

A release requires the official 26.3 server running under Java 25, the exact 121.0 datapack loaded, real online clients, and observed inventories/state. Mocked RCON responses and unit tests alone do not prove command syntax, block-data/client synchronization, Ender Chest behavior, or crash persistence.

### Required acceptance scenarios

1. **Vanilla-only install:** official server starts, datapack loads without errors, protocol/doctor reports 26.3/121.0, and an unmodified client joins. No plugin/mod/third-party server API is present. Another release/snapshot/pack mismatch fails readiness without mutation.
2. **Shared objective:** multiple players see one factual objective, correct coordinates/reward, boss bar, and working non-op triggers. No individual/offline target blocks the quest.
3. **Generation/fallback:** exact valid model schema activates once; invalid ID/type/extra keys/control characters/oversized prose, timeout, missing credentials, quota error, and absent AI endpoint use one local fallback. Late output/restart never creates a second quest or repeats an uncertain provider call.
4. **Counting:** plain matching stacks across slots count; wrong/custom stacks do not. Withdrawals lower progress, surplus/pre-existing contents can count later, and milestone messages do not spam.
5. **Exact consumption:** partial stacks/excess deposits consume exactly the target, preserving all unrelated stack/component data. Insufficient inventory, no eligible recipients, or recipient-limit overflow changes nothing.
6. **Live inventory synchronization:** test click/drag/shift-click/hotbar swap/double-click/multiple viewers and a controlled hopper test around function execution. No stale client action duplicates consumed items. Confirm the declared single-function boundary, and document that physical anti-grief/hopper restrictions come from setup/rules, not nonexistent event interception.
7. **Eligibility snapshot:** survival/adventure online UUIDs excluding configured accounts receive one entitlement each; creative/spectator do not. Join after snapshot gets none; disconnect after snapshot retains pending. Rename preserves ownership.
8. **Ender Chest safety:** one exact reward stack enters the first empty slot; all existing stacks remain unchanged. Full inventory inserts nothing; freeing space and claiming succeeds. Test the actual 26.3 single-slot command semantics and reject broad-slot overwrite paths.
9. **Offline/repeated claim:** offline waits persist; login/claim/timer/replayed operation within one session cannot duplicate delivery. Pending entitlements process oldest first and do not block unrelated rewards/new quests.
10. **Crash matrix:** kill Python and server before/after intent commit, dispatch, each inventory write/receipt phase, checkpoint, SQLite acknowledgement, and notification. Unknown outcomes enter review rather than replay; every resolution works through the actual CLI with evidence/confirmation.
11. **Restore/corruption:** coordinated backup/restore resumes safely; mismatched DB/world/player/receipt restores pause and surface review. Corrupt DB/migration/storage/SNBT output fails closed without empty-state substitution.
12. **Lifecycle:** expiry/cancel preserve contents and grant no rewards; all-offline/unhealthy/downtime pause timers; cooldown avoids catch-up bursts; expiry versus dispatch uses the defined ordering.
13. **Outage guards:** stale Python heartbeat stops mutations and claims show paused; AI outage alone still produces fallback. Reload disables dispatch pending handshake; dropped/multipart RCON results do not authorize blind retries.
14. **Economy and bounds:** quantity clamps/tier thresholds/caps are correct; rewards persist unchanged through reload; fallback/admin starts obey activation allowance; call reservations survive restart; full/oversized evidence/recipient-limit requests mutate nothing.
15. **Security and limits:** ordinary players cannot administer or supply payout fields; UUID targeting ignores malicious/stale names; generated text cannot execute commands or chat actions; no public RCON/no logged credentials; documented spawn-protection/operator limitations are accurate.
16. **Operations and performance:** register/unregister preserve blocks/contents and force-load ownership; doctor/CLI review/confirm/pause/reload/shutdown work. Bounded slot scans and checkpoint batches cause no sustained tick degradation at the configured player bound; backup/restore drill needs no undocumented decisions.

Automated tests must protect consumer-visible boundaries, transitions, parsing, exact item counts, uniqueness, and reviewed recovery. Use deterministic seeds/clocks and isolated real-server fixtures where possible. Retain regressions for proven duplicate/overwrite/parser defects; do not test merely that mock command strings were forwarded.

### Definition of done

The system runs on the official 26.3 release and Java 25 with the exact vanilla datapack, all acceptance scenarios have observed evidence, installation instructions actually work, uncertainties are operable rather than hidden, obsolete prototype paths are removed, and the README describes shipped behavior without claiming untested compatibility. A documentation-only revision is not an implementation or compatibility certification.

## 16. Primary sources and verification limits

- [Mojang version manifest](https://piston-meta.mojang.com/mc/game/version_manifest_v2.json): release versus snapshot identification.
- [Official 26.3 metadata](https://piston-meta.mojang.com/v1/packages/4fe1aa1ef8da1cb95c5bad1fb98890ca56dd8ca3/26.3.json): release ID, Java major version 25, and official artifact URLs/checksums.
- [Minecraft Java Edition 26.3 release notes](https://www.minecraft.net/en-us/article/minecraft-java-edition-26-3): final data-pack version 121.0, slot-source/item command changes, and removed log lines.
- [OpenRouter Chat Completions API](https://openrouter.ai/docs/api/api-reference/chat/create-a-chat-completion): compatible provider endpoint.

### Runtime verification record and limits

The official 26.3 dedicated jar was SHA-1 verified as `33680f5f2ac32864d6d7cf5e56a705fdb3e05f4c` and run under Java 25 in the isolated Podman server. An unmodified official 26.3 rendering client shift-clicked six iron ingots into the delivery chest, observed exact consumption, and viewed three emeralds in its Ender Chest. Runtime UI defects (quoted SNBT text and oversized boss-bar label) were corrected and visually rechecked.

Live checks covered exact plain/custom/mixed stack preservation; stale/insufficient/no-recipient/recipient-cap refusal; 19-recipient receipt paging; 20 online players with 17 eligible recipients after creative/spectator/UUID exclusions; full/offline waits; first-empty-slot insertion; immutable payout/completion replay; watchdog pause; large Unicode multipart staging; oversized evidence and adjacent-hopper refusal; long configured expiry; exclusive owner; and all four confirmation-bound operator resolutions. A real lost payout response entered review without automatic reinsertion. Metadata-only player-restore quarantine, typed corrective payout, preserved unrelated slots, and consumed confirmation tokens were exercised.

An HTTP provider fixture observed exactly the configured model on four calls. Valid prose activated an AI quest; extra/invalid fields, HTTP 429, and timeout activated local candidates without retries. Each quest expired without changing the chest, and the actual managed owner exited cleanly on SIGINT.

Additional runtime checks used two unmodified official viewers for click, drag, shift-click, hotbar-swap, and double-click actions, followed by actual 20-recipient completion. Fourteen initial plain iron minus six consumed left exactly eight across current chest/player inventories; custom components were unchanged. The second client viewed three emeralds in its Ender Chest. Full pending delivery succeeded after freeing one slot; repeated claims did not add stacks. Registration/unregistration preserved items and pre-existing force-load ownership while removing only the newly owned ticket.

All-offline timers and restored downtime preserved remaining/elapsed time. A stopped complete world/SQLite pair was backed up, restored with corrected UID/GID ownership, and reconnected with matching checkpoint and zero reviews. An isolated mismatched database quarantined 26 issuance operations before dispatch; its controlled owner kill left the original paired ledger unaffected.

The official jar's RCON framing behavior explained intermittent lost responses. Waiting for the first response before sending the barrier passed a live 602-command, 300-round-trip burst on one connection. Regression tests cover no request pipelining, stopping a disconnected payout batch before additional intents, and preventing a postcommit read outage from reopening committed unregistration.

Protocol load fixtures are not official rendering clients. Offline testing cannot prove authenticated account-rename UUID continuity. No paid provider was called. The exhaustive multi-viewer click/drag race grid, every crash/save-window injection, full coordinated/mismatched/player-only backup matrix, 128-player load, and long soak are not certified by these runs. Section 15 remains the production release gate; these observed checks must not be represented as full acceptance certification.
