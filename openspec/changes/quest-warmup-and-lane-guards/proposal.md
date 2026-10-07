# Proposal

## Why

The live Director requested carrots as an opening communal quest although the player found wheat and nearby pumpkins, not carrots, at the selected spawn village. Opening quests need verifiable nearby supplies, and personal quests need a distinct, longer-term difficulty without competing for communal offerings in the shared chest.

## What Changes

- Make the first three completed communal quests and first three completed personal quests per player a local, low-quantity warm-up, independent of player strength.
- Use a 32-block horizontal radius around the configured selected-village quest hub for warm-up. Count actual block positions and mature harvestable resources, not whole chunk sections, palette presence, or unbounded underground resources.
- Verify Java 26.3 Anvil block-state decoding and exclude malformed, incomplete, changing, or unsupported observations. The earlier scanner totals are not accepted as proof of real local carrots.
- Bound each warm-up request by a conservative observed harvest quantity; select the existing catalog minimum, and defer when that minimum is unavailable. Do not require unavailable carrots when local wheat or pumpkins qualify.
- Reserve distinct item IDs across communal quests, every personal quest including offline targets, and pending offering operations. Enforce the guard in both directions and for both LLM and fallback creation.
- After personal warm-up, normally request the band immediately above communal difficulty when the target's own progression unlocks it. Occasionally request one further unlocked band as a clearly announced longer-term goal; never bypass progression for luck.
- Persist warm-up progress and personal assignment sequence, and credit each successful completion once even after restart or reward recovery.
- Safely retire untouched active quests that fail the new policy, including the unavailable opening quest, without consuming items or granting rewards. Preserve pending and uncertain operations unchanged.

## Capabilities

### New Capabilities

- `adaptive-offering-quests`: additional local warm-up, supply-evidence, conflict-prevention, and personal-goal requirements under the capability path already used by the existing quest changes. This path is not yet present in main specs; this additive delta supplements those changes rather than creating a differently named capability.

### Modified Capabilities

None of the currently published main capabilities change. The implemented baseline is described by `adaptive-offering-quests` and `greek-temple-shared-offerings` change artifacts; this change retains the latter's shared normal-chest contract.

## Impact

- `quest_supply.py`: accurate positional block decoding, bounded harvestable observations, item-yield accounting, and fail-closed evidence.
- `director.py`: candidate policy, state persistence, completion accounting, scheduling reservations, safe active-quest retirement, and explicit quest announcements.
- Existing Director tests and new isolated supply-observation regression coverage; README operating-contract documentation.
- Current Java 26.3 world and its quest JSON: backed-up in-place Director rollout after implementation and shipping, without regenerating terrain or resetting player/building progress.

## Non-Goals

- No temple/datapack edits, live-world regeneration, farm planting/harvesting, terrain clearing, or settlement identity changes.
- No ender-chest or player-inventory submission fallback; both lanes keep the configured normal chest and existing reward ownership.
- No navigation/pathfinding guarantee or automatic restoration of harvested resources.
- No model-authored commands, coordinates, item IDs, difficulty scores, or expanded reward economy.
