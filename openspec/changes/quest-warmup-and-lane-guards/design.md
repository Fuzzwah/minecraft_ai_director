# Design

## Context

See proposal.md for motivation and the adaptive-offering-quests delta for acceptance behavior. `director.py` already owns `QUEST_CATALOG`, band thresholds, the communal average, personal profiles, candidate filtering, LLM validation, fallback, and durable JSON offering/reward intents. Both lanes consume the same configured normal chest. `quest_supply.py` observes saved Anvil files after a save boundary, but currently aggregates entire sections of intersecting chunks, ignores crop growth, and does not bound requests by observed yield.

The scanner's `_palette_counts` reads a continuous bit stream across 64-bit words and silently ignores out-of-range palette indices. Java packed-state layout and the mixed string/compound palette representations observed in the live world need exact decoding, not aggregate counts taken on trust. The earlier reported carrots are scanner output, not proof that maturity alone explains the player's observation. Existing tests inject a pre-built pumpkin `SupplySnapshot`; they do not validate the underlying real chunk decoder or resource positions.

The capability exists in implementation and in two unsynchronized change deltas, not yet in main specs. This change adds distinct requirements under the same capability path. The older adaptive delta's ender-chest references are historical and are superseded by the implemented shared-chest change; do not restore them or invent a parallel capability.

## Goals / Non-Goals

**Goals:** one bounded supply interpretation, one Python-owned selection policy shared by LLM/fallback, item uniqueness across the shared offering source, and durable lane progression independent of settlement enablement.

**Non-Goals:** changing the reward economy, rewriting settlement construction, pathfinding, automatic crop farming, resource respawn, historical-completion reconstruction from incomplete logs, or world regeneration. No implementation or live operation is part of proposal creation.

## Decisions

### 1. Decode positions before using crop evidence

Replace section-wide count-based selection with a positional iterator in `quest_supply.py`. Use actual Java 26.3 saved block-state formats: handle the supported string/compound representations and property keys, decode padded words according to the version rather than spilling an entry across word boundaries, and validate lengths and every decoded palette index. Unknown versions or layouts fail closed. Read each relevant region once per snapshot and reuse decoded sections; do not reread a region for each coordinate.

Translate each section index to world coordinates. Apply the horizontal disk filter `(x - hub_x)^2 + (z - hub_z)^2 <= radius^2` to blocks, containers, and drops, not merely their chunk coordinates. Warm-up uses radius 32 around configured `SPAWN_X/Z` at the selected village hub; later observations retain the existing configured wider radius. Minecraft world-spawn metadata is not silently substituted for Director configuration.

Use exposed surface harvestable resources for the warm-up rather than all vertical sections as proof of easy access. Verify surface/exposure from saved column state; exclude buried or unsupported states rather than implementing navigation. Normalize mature crop properties (age 7 for wheat/carrots/potatoes; age 3 for beetroot). Missing age is unknown, not ripe. Use conservative yield: one item per qualifying mature crop or pumpkin, nine wheat per qualifying hay bale. Do not count a melon block as a whole melon item, or count raw inputs as cooked/crafted outputs. Warm-up block-derived candidates use these directly obtainable farm resources; intact building logs do not become an opening instruction to dismantle the village. Exact nearby item stacks can supply other existing local catalog items if directly accessible and observed.

Retain source categories and available item counts. Target inventory possession alone does not satisfy warm-up locality. Do not double-count a chest payload or drop as a harvestable block. Establish the existing save boundary outside dry-run; verify relevant chunks are loaded and region identity/size/mtime stay stable during observation. Failure marks the bounded observation unavailable rather than using a partial positive count as a complete local set.

**Alternative rejected:** keeping section aggregate counts and adding an age check alone leaves radius spillover, underground resources, and packing mistakes capable of authorizing unavailable carrots.

### 2. Persist warm-up independently for the communal lane and each player

Add a communal completion count and a player-keyed personal completion-count map to `State`; counts saturate at three because only warm-up eligibility depends on them. Missing fields in existing saves initialize to zero, while invalid counter data fails state loading rather than erasing progress or pending operations. Add a player-keyed post-warm-up issued count for the predictable aspirational cadence.

Credit completion only when `process_pending_rewards` finishes the existing consumption and every required reward obligation. Increment the applicable count in the same atomic JSON state write that removes that completed pending record. A restart therefore sees either the outstanding intent with the old count or the fully completed state with the increment, never an independent counter update that can replay. This path must run with settlement integration disabled as well as enabled; currently the main loop invokes pending recovery only inside the manager branch, which must be corrected for this requirement. Dry-run never changes counters, sequence, or the saved file.

Use the existing catalog minimum as both minimum and maximum warm-up quantity; exclude items whose available conservative yield is below it. This produces two pumpkins or six wheat using current definitions, rather than random larger requests. Keep existing reward tiers; no larger rewards are introduced by this change.

**Alternatives rejected:** counting generated quests makes failure or restart shorten the warm-up; counting consumption before reward completion loses durable recovery semantics; reconstructing old history can falsely promote a novice.

### 3. Derive reservations from existing authoritative records

Compute a set of reserved item IDs from active communal/private/legacy records and all pending rewards, deduplicated by quest ID. An offline personal target still reserves its item. Keeping this derived avoids a second mutable reservation database that can drift from quest state.

Filter every new lane against this set before LLM/fallback. Retain the current communal-first scheduling preference when both are due, then assign personal lanes in a stable player order and update reservations after each durable assignment. New communal work must also respect personal reservations. Recheck reservations when accepting a model result and immediately before a completion intent; validation of a stale candidate list must not bypass the guard. Reject colliding completion before any inventory mutation, not by reducing the requested quantity or choosing whichever quest happens to tick first. Pending/uncertain records keep reservations until resolved and removed.

**Alternative rejected:** prompt-only instructions cannot enforce uniqueness or protect a restarted shared-chest operation.

### 4. Make personal progression hybrid with a fixed safe cadence

For post-warm-up selection, freeze a communal reference band at assignment time: use the active communal quest's `candidate_band`, otherwise the current communal policy band (local during communal warm-up; progression band of the eligible-player average afterward). Normal personal candidates are exactly one band above that reference, and only if the target's own profile confidently unlocks it. If there is no qualifying unreserved item or the next band does not exist, defer; do not silently replace the goal with another communal-tier request.

Every fifth successfully issued post-warm-up personal quest prefers two bands above the reference, still within the target's own unlocked ceiling. If that aspirational pool is empty, use the normal pool; if both are empty, defer without advancing issued count. Persist the sequence increment alongside quest assignment before announcement. This predictable cadence implements the selected hybrid without stochastic rerolls on every deferred tick. Long-term personal quantities stay within existing catalog limits and can be satisfied later or by a lucky find; the target need not already possess the item.

Warm-up takes precedence for each lane. Group-average strength must never promote a personal target. Existing assigned goals retain their difficulty when online membership or communal assignments later change; difficulty separation is a creation-time contract, not continuous repricing. At the highest band the guard may defer new personal work rather than invent an unsupported tier.

Persist the selected mode and reference band with each new quest so announcements and restart behavior do not recompute its meaning. Communal announcements address the group, not the `_communal` sentinel; personal announcements name the target and distinguish nearby warm-up from longer-term/aspirational work, always naming the shared normal chest.

**Alternative rejected:** quantity-only escalation does not provide the requested longer-term material goal; unbounded rare requests would violate progression safety.

### 5. Revalidate legacy active assignments once, without rewriting debt

Add a selection-policy version to quest metadata, with legacy saves defaulting to the old policy. Before any completion of an old-policy active quest, obtain trustworthy evidence and revalidate it against the new policy. Unknown evidence suspends that lane; it is not a reason to retire a quest. Reliable evidence that rejects an untouched assignment permits durable retirement, clear explanation, and a fresh safe selection. Retirement does not count as completion, consume deposited items, or issue compensation rewards.

Never retire or rewrite a quest that has a pending offering/reward intent; preserve its ID, snapshot, steps, ownership, commands, and uncertainty for recovery/reconciliation. For legacy duplicates without pending intents, preserve the communal assignment first and then personal assignments in stable player order; retire later duplicates before completing either. Pending item reservations take precedence over all untouched assignments. Mark accepted legacy assignments as revalidated so normal harvesting after creation does not repeatedly cancel valid active quests.

This addresses the existing opening carrot assignment during rollout rather than changing only future generation. No automatic crop edits or world resets are necessary.

**Alternative rejected:** wiping quest JSON loses pending rewards and ownership; leaving the old impossible quest indefinitely does not fix the reported user experience.

## Risks / Trade-offs

- Strict locality or crop maturity can leave only one available resource -> prioritize communal assignment and defer personal warm-up; never widen the radius implicitly.
- Real Anvil formats can differ from handcrafted fixtures -> validate saved Java 26.3 chunks against independent read-only RCON block-state checks, including packing boundaries and crop positions, before rollout.
- A farm can change after snapshot -> evidence constrains creation, not resource reservation in the world; continue exact chest fingerprint checks before consumption.
- No geometric scan proves walking access or authenticated player harvesting -> test the client surface if available and state that limit if not; exposed local supply is not a pathfinding claim.
- Legacy saves do not preserve historical successful completion totals -> conservative zero counters repeat easy warm-up rather than guessing progression.
- Strict higher-band goals may defer for novice or top-band players -> preserve progression safety and the existing catalog rather than inventing materials or weakening conflict prevention.
- Duplicate legacy work with uncertainty -> suspend competing work and require the existing offline reconciliation process, never replay consumption.

## Migration Plan

1. Publish and review this plan on primary `main`. Apply only in an implementation worktree synchronized with that planning commit.
2. Implement and verify the scanner, policy, durable counters, and legacy handling without using the live player's inventories as test fixtures. Use isolated Java 26.3 acceptance for any mutations; client-only verification remains explicit.
3. Ship reviewed code through the topic-branch PR workflow. For the designated current Podman world, stop the Director writer and preserve a matched world/config/quest JSON/SQLite backup; do not regenerate terrain or change world identity.
4. Synchronize the live-mounted primary source, preserve hub/chest coordinates, and run a read-only candidate preview against loaded saved village data. Compare reported farm/pumpkin evidence with actual block checks, not the old scanner totals.
5. Start only the one existing Director. Observe counter migration and safe retirement or suspension of untouched invalid quests; preserve pending records. Verify quest state and reservations after restart without triggering billable model calls for acceptance.
6. If migration or source evidence is uncertain, stop the writer and reconcile or restore the matching backup/config/code. Never combine restored quest progress with unverified world inventory changes.
