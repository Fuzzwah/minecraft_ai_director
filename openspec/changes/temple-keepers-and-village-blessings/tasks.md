# Tasks

This is a planning-only change. All boxes remain unchecked until implementation and the stated evidence exist. Tasks 1.1-1.3 are real Java 26.3 feasibility gates, not permission to replace visible rituals with silent inventory mutation. Planning and publication do not authorize server changes or deployment.

## 1. Prove target-version discovery and NPC control

- [ ] 1.1 Decode generated Java 26.3 village starts/pieces against the committed manifest and prove altar, entry, and chest transforms for all 32 roots and four rotations using real saved data and disposable-server read-only block probes; record unsupported/ambiguous cases without guessing provenance.
- [ ] 1.2 Prove a real adult villager can naturally approach the existing temple altar and return to normal work/sleep/fleeing behavior; observe successful stairs traversal plus blocked-route and threat interruption with no teleportation, permanent NoAI, or sacrifice on failure.
- [ ] 1.3 Prove a non-yielding guarded Java 26.3 function exchange can check live inventory/reserves/capacity, secure compensation before debit, preserve components, and expose an operation completion marker; exercise full inventory, changed snapshot, repeated operation ID, lost acknowledgment, and server restart without resource loss or duplicate debit.
- [ ] 1.4 Record the gate evidence and exact supported control/item schema in README development guidance; verify each claim against the observed disposable-server output and identify client-only observations separately. Do not activate autonomous NPC scheduling unless all gates pass.

## 2. Implement the loaded-temple registry and altar identities

- [ ] 2.1 Add stable world/dimension/location Keeper records and incremental saved-candidate discovery with live loaded/altar/chest/clearance verification; verify real-template behavioral tests reject arbitrary chests, ambiguous geometry, wrong rotation, and unloaded sources while finding multiple valid temples.
- [ ] 2.2 Add persistent Keeper names/personality archetypes, first-entry membership, and local introductions using verified live positions; verify two visitors and a restart retain one identity, reentry does not reenroll or duplicate assignments, and no physical Keeper or implicit LLM request is created.
- [ ] 2.3 Implement report/suspend/resume for missing, replaced, or obstructed chests and a distinct unloaded pause; verify other temples continue, chest contents/player edits are unchanged, admin repairs resume the existing identity, and uncertain debt is not replayed.
- [ ] 2.4 Bound discovery/interaction work per poll while eventually revisiting all generated candidates, including loaded villages without players; verify a throwaway multi-temple runtime scenario discovers reload transitions without force-load tickets or missed-activity payouts.
- [ ] 2.5 Document temple identity, first-entry behavior, discovery delays, local dialogue, suspension diagnostics, and non-repair in README; smoke the documented read-only inspection/preview path against a disposable world without state changes.

## 3. Cut player quests over to Keeper ownership safely

- [ ] 3.1 Version quest JSON and migrate the verified original source's quests, counters, recipient snapshots, reservations, and reward debt into its Keeper; verify legacy round-trip/restart tests preserve identities and uncertain operations, unknown mappings block rather than guess, and new Keepers do not inherit old progress.
- [ ] 3.2 Scope active communal/personal lanes, timestamps, warm-up, issuance sequence, and item reservations per Keeper; verify one player can hold two Keepers' personal quests, two chests can request the same item, and offline/pending work still reserves items within its own chest.
- [ ] 3.3 Evaluate candidates at the issuing temple hub and preserve bounded local yields, first-three warm-up, progression unlocks, personal aspiration, and equal LLM/fallback limits; verify differing village crops, radius boundaries, malformed/changing/unloaded evidence, and no-safe-candidate deferral with existing supply regressions.
- [ ] 3.4 Replace global source resolution with immutable dimension-qualified issuer sources throughout consumption and recovery; verify wrong-temple and split-chest offerings do not complete a quest, unrelated metadata remains intact, and chest removal/lost responses cannot redirect or replay consumption.
- [ ] 3.5 Select communal recipients from eligible online members of the issuer while retaining target-only personal rewards and frozen pending snapshots; update affected observable ownership tests and verify travelling members receive communal rewards while nonmembers do not.
- [ ] 3.6 Preserve successful same-tick replacement, failed-probe cooldown behavior, exact-once progression, and optional SQLite settlement credit; verify restart recovery advances only its Keeper lane once and settlements-disabled operation remains functional. Remove obsolete global runtime aliases/callers after migration.
- [ ] 3.7 Update README quest, source, membership, supply, migration, and backup contracts; smoke a disposable two-Keeper player API scenario covering first entry, separate assignments, issuer-only consumption, travelling-member rewards, and restart persistence.

## 4. Implement actual-inventory NPC quests and rituals

- [ ] 4.1 Define trusted supported food and profession-goods rules from verified Java 26.3 possession behavior, with nutrition values and explicit protected working-stock floors; verify reserve boundary tests reject trade-only goods, essential planting stock, unsupported components, and insufficient surplus.
- [ ] 4.2 Assign local adult villagers deterministically by UUID and prevent overlapping or simultaneous rituals; verify overlap, transported distant villagers, death/transformation, and restart scenarios do not cause cross-Keeper or substitute-villager debits.
- [ ] 4.3 Integrate bounded native altar visits, live arrival revalidation, local acknowledgment, and cancellation during danger/unloading/trading or blocked access; smoke successful and interrupted real-villager rituals, observing unchanged inventory on every aborted approach.
- [ ] 4.4 Integrate the proven server-side exchange with durable intent, component-preserving compensation-before-debit, capacity checks, queryable operation markers, and reconciliation; verify repeated IDs and lost-response/restart scenarios cannot repeat compensation, debit, or completion credit.
- [ ] 4.5 Keep NPC requests and goods outside player chest/quest accounting and bound per-villager demand as population grows; verify a same-item player/NPC scenario leaves the player chest unchanged and population increase cannot bypass working reserves or ritual budgets.
- [ ] 4.6 Document supported NPC goods, protected stocks, ritual cadence, interaction limits, and uncertain-operation recovery in README; compare the documented compensation/reserve example with the observed real-villager inventory before and after a completed exchange.

## 5. Add surplus distribution and unconditional recovery assistance

- [ ] 5.1 Distribute additional food only after donor compensation, to verified low-stock local villagers with capacity using separately guarded grants; verify changed/full recipient inventory and failed distribution cannot repeat the original sacrifice or spill player loot.
- [ ] 5.2 Implement modest unconditional food and healing assistance with persistent recipient/village budgets and deterministic overlapping-temple ownership; verify poor villagers can recover without sacrifice, healthy recipients are excluded from food grants, and reload/restart cannot duplicate assistance or create catch-up payouts.
- [ ] 5.3 Document need thresholds, budget caps, and food-positive versus working-stock protections in README; smoke a disposable poor-village scenario with actual inventories and observe bounded assistance followed by a safe compensated ritual without reducing protected reserves.

## 6. Add local healing, protection, and defensive wards

- [ ] 6.1 Record exactly-once village benefit credit from fully successful player and NPC completions, independent of optional settlements; verify failed/partial/uncertain/dry-run work earns no credit and recovery cannot credit another village or count the same completion twice.
- [ ] 6.2 Implement bounded injury-prioritized healing and temporary protective effects with persisted capped expiry; verify non-donors are eligible, repeated completions cannot exceed caps, and restart resumes remaining duration rather than restarting the full blessing.
- [ ] 6.3 Implement the approved-hostile weakness/slowness ward within verified local bounds using guarded Java 26.3 functions; smoke a real attacker inside/outside the boundary, verify players/friendly entities are excluded, and ensure no entity spawning/deletion, terrain edits, or gamerule changes occur.
- [ ] 6.4 Enforce overlap caps and stop new effect refresh on suspension/unloading without globally clearing unrelated effects; verify two adjacent wards do not amplify strength, travelling members do not move village benefits, and existing finite effects expire naturally.
- [ ] 6.5 Document exact effect IDs, hostile targets, radius, duration/strength caps, and protection limits in README; exercise the documented combat/healing scenario on a disposable server and do not claim invulnerability, resurrection, or guaranteed population growth.

## 7. Verify end-to-end operation and release readiness

- [ ] 7.1 Extend read-only preview across discovery, enrollment, migration, player work, NPC exchange, assistance, and blessings; run it with read-only world/state mounts and compare world, quest JSON, SQLite, and effect/inventory state to prove dry-run immutability.
- [ ] 7.2 Run `python3 -B -m unittest discover -v`, `python3 -B tools/village_temples.py --check`, `python3 -B settlement_admin.py --help`, and strict OpenSpec validation after integration; preserve behavioral failure/recovery tests and remove obsolete incidental wording/source-text tests instead of repinning them.
- [ ] 7.3 Smoke the complete multi-temple loop on disposable Java 26.3: two first-entry memberships, issuer-only player turn-ins, NPC food and profession-goods exchanges, low-stock assistance, healing/ward combat, one damaged temple, chunk unload/reload, and server/Director restart; retain exact observed inventory, ownership, and persistence evidence.
- [ ] 7.4 Verify local Keeper introductions, distinct identities, villager walking/altar rituals, and blessing presentation in a vanilla Java 26.3 client; report authenticated-client limitations separately from RCON or isolated offline-client proof.
- [ ] 7.5 Reconcile the earlier active `adaptive-offering-quests` delta lineage and review the backed-up migration/deployment/rollback instructions; verify the review does not reintroduce ender-chest/global-source behavior or require regeneration for this runtime feature.

## Workflow follow-up

- Review and merge implementation through the topic-branch PR workflow before any primary-checkout synchronization or separately authorized deployment.
- Deploy only after complete matched backups and writer-stopped acceptance; use the design's maintenance/rollback plan, preserve both persistent stores and world identity, and never regenerate terrain as part of this runtime update.
- Synchronize/archive the completed change only after implementation acceptance, preserving the latest Keeper-specific player capability and reporting any unverified client surface.
