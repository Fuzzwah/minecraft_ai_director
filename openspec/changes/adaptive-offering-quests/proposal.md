# Proposal

## Why

The current Keeper temple is visually discoverable but has no offering container, while the Director checks the named player's inventory at world spawn. The quest generator also chooses from a static item catalog without observing the spawn village or player progression, so a new player can receive an unavailable carrot quest in a village that only supplies pumpkins.

A fresh live world needs a reliable communal offering workflow, private player-owned submissions, and difficulty that starts with local village resources before progressing toward endgame materials.

## What Changes

- Add one empty Keeper offering chest and one ender chest to every newly generated Keeper temple across all 32 normal and abandoned Java 26.3 town-center roots.
- Treat the normal temple chest as the communal quest submission point; consume only the active communal quest's requested item from it.
- Treat each target player's ender-chest inventory as that player's private quest submission point; consume only the target player's requested item from that inventory.
- Replace the single global quest slot with one active communal quest and one active private quest per eligible online player, with durable state and crash-safe consumption/reward recovery.
- Add read-only supply discovery for the spawn village and nearby generated chunks, including harvestable resources and container contents, plus target-player inventory and ender-chest availability for private quests.
- Add bounded per-player progression scoring based on observable Minecraft progression signals, use the average score for communal quests, and gate item pools from village-local resources through early, established, Nether, End, and netherite tiers.
- Pass only filtered, observed, progression-appropriate candidates to the LLM; make deterministic fallback use the same candidates and skip quest creation when no safe candidate exists.
- Update quest announcements and completion handling to describe depositing offerings, reward all online players for communal completion, and reward only the target player for private completion.
- Regenerate only the designated Java 26.3 live world after implementation and isolated verification, using a new random seed, a matched rollback snapshot, fresh Director state, and a new settlement world identity.
- Update tests, README, AGENTS.md, and OpenSpec requirements with the container, state, progression, persistence, and live cutover contracts.

## Capabilities

### New Capabilities

- `adaptive-offering-quests`: Communal and private offering quests with supply-aware candidate selection, progression-scaled difficulty, durable container transactions, and distinct reward ownership.

### Modified Capabilities

- `village-temple-generation`: Generated temples gain the validated Keeper offering chest and ender chest while preserving one-temple-per-village, road connectivity, Java 26.3 compatibility, and persistence requirements.
- `live-world-regeneration`: The designated live cutover uses a new random seed, fresh quest/settlement state, and acceptance checks for temple containers and the new quest workflow.

## Non-Goals

- Retrofitting temples or containers into already generated villages.
- A runtime scanner that adopts every village into Director settlement ownership.
- Protected or unbreakable temple blocks, automatic player-build restoration, or terrain clearing.
- Letting the LLM emit commands, coordinates, chest slots, item IDs outside Python-owned candidates, arbitrary rewards, or progression scores.
- Adding server mods, client mods, third-party Python packages, or changing the Java 1.21.1 settlement construction pack.
- Reusing the old live world or attaching old quest/building records to regenerated terrain.
