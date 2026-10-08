# Minecraft AI Director

Standard-library Python Director for a Minecraft Java server. It monitors server
logs, detects online players over RCON, generates constrained collect quests,
consumes offerings at spawn, and grants application-controlled rewards.

Settlement construction extends the same trust boundary: the model requests
approved building IDs; Python owns coordinates, templates, validation, scheduling,
and world mutation. Model responses are never executed as commands.

## Long-lived live server

Connect to **`10.1.1.232:25555`** with Minecraft Java **26.3**. The persistent
server is `mc_ai_director_default`, with companion `mc_ai_director_default_keeper`.
The names are retained for continuity; this server no longer uses host port 25565.
The Director loads source from the primary `main` checkout at
`/home/fuz/code/minecraft_ai_director`, not an implementation worktree.

```bash
systemctl --user stop mc_ai_director_default_keeper.service
systemctl --user restart mc_ai_director_default.service
systemctl --user start mc_ai_director_default_keeper.service
podman exec mc_ai_director_default rcon-cli list
podman logs -f mc_ai_director_default_keeper
```

World/server data and Director state persist in `mc_ai_director_default_data`
and `mc_ai_director_default_state`; RCON is not published on the host.
The separate hardcore server uses port 25567.

Matched rollback snapshots are stored under `/home/fuz/mc-ai-director-backups/`
with a checksum manifest. Take a fresh snapshot immediately before the future
regeneration if the existing world has been played since its last backup.

**Village-temple deployment requires regenerating this live world**, but only
after the generation feature is implemented and verified for Java 26.3.
Preserve both existing volumes as a rollback snapshot before regeneration.
Install the generation datapack before creating the replacement world; use fresh
Director state, recompute spawn, and verify generated temples before playtesting.
The existing construction templates alone do not add temples to vanilla villages.

Regeneration is a destructive cutover. Stop the Director writer first, flush and
snapshot the complete Minecraft and Director volumes as one matched pair, then
create a new random-seed world with the verified Java 26.3 temple pack already
installed. Provision a new quest JSON, settlement database, and settlement
`world_id`; never reuse old records with new terrain. If any placement, spawn,
container, Director, persistence, or uncertainty check fails, stop both writers
and restore the matched snapshot instead of retrying or mixing state.

### Set world spawn after regeneration

The temple pack does not change Minecraft's world-spawn metadata. During a live
world regeneration, record the original overworld spawn before replacement.
After the new Java 26.3 world has generated terrain and the temple pack is
enabled, locate every supported village type from that recorded position and
choose the smallest horizontal distance:

```bash
export ORIGINAL_SPAWN_X=0 ORIGINAL_SPAWN_Y=72 ORIGINAL_SPAWN_Z=0
for TYPE in plains desert savanna snowy taiga; do
  podman exec mc_ai_director_default rcon-cli \
    "execute positioned $ORIGINAL_SPAWN_X $ORIGINAL_SPAWN_Y $ORIGINAL_SPAWN_Z run locate structure minecraft:village_$TYPE"
done
```

Do not accept a guessed coordinate or a failed/localized locate response. Load
and inspect the selected village column, confirm a solid support block and clear
air above it, then set the world spawn one block above that support. Do not
clear terrain, force an unsafe spawn, or proceed when the target chunk/state is
uncertain. Flush the world and verify the persisted spawn metadata before
starting normal play:

```bash
podman exec mc_ai_director_default rcon-cli 'setworldspawn <x> <y> <z>'
podman exec mc_ai_director_default rcon-cli 'save-all flush'
```

For the current regenerated live world, the nearest result is the plains village
at `[352, ~, -832]`. Its verified support is
`[352, 73, -832] = minecraft:smooth_stone`, with clear air at `[352, 74, -832]`,
so the persisted world spawn is `[352, 74, -832]`. This changes only the
default world spawn. Beds and respawn anchors remain authoritative for players
who have set them. The Director's quest/turn-in coordinates
(`SPAWN_X`, `SPAWN_Y`, `SPAWN_Z`) are a separate contract and are not changed by
this world-spawn adjustment.

## Run the existing Director

Requires Python 3.10+ and a Java server with RCON enabled. Keep RCON private.

```bash
export RCON_HOST=127.0.0.1
export RCON_PORT=25575
export RCON_PASSWORD='your-server-password'
export MINECRAFT_LOG=/path/to/server/logs/latest.log
export SPAWN_X=0 SPAWN_Y=64 SPAWN_Z=0
export DEMO_MODE=1
python3 director.py
```

For an OpenAI-compatible endpoint, set `LLM_URL`, `LLM_MODEL`, and optionally
`LLM_API_KEY`, then unset `DEMO_MODE`. Existing quest state remains in
`DIRECTOR_STATE` (default `director_state.json`). Older saves are loaded with
stable quest IDs and empty settlement rewards.

Settlement integration is **off by default**. Existing quests, item rewards,
player detection, log monitoring, and LLM quest generation do not require it.

## Adaptive temple offerings

The Java 26.3 temple datapack adds one integrated Greek-inspired temple and one
empty normal offering chest to every supported normal and abandoned town-center
root. It adds no ender chest. The Python Director never accepts chest
coordinates, item IDs, quantities, lanes, scores, or rewards from the model.
Configure the generated temple's offering chest explicitly:

| Variable | Default |
| --- | --- |
| `MINECRAFT_WORLD` | `/minecraft/world` |
| `OFFERING_CHEST_X/Y/Z` | unset; communal quests decline until configured |
| `SPAWN_SUPPLY_RADIUS` | `64` blocks |

Both communal and private quests use the configured loaded normal offering
chest. A communal quest rewards all eligible online players at completion; a
private quest retains exactly one target player and rewards only that target.
Offerings are persisted as prepared, uncertain, or completed intents; a lost RCON
response stops the Director for reconciliation and never replays consumption or
rewards. Ender-chest, player-inventory, and arbitrary-chest fallbacks are not
supported. Persisted private quests from the removed ender-chest contract are
migrated to the shared chest without reading or consuming legacy ender items.

Candidate items are Python-owned. The first **three successfully completed
communal quests**, and the first **three personal quests per target**, are an
easy warm-up regardless of player strength. Warm-up uses a **32-block horizontal
radius** around the configured village quest hub (`SPAWN_X/Z`), not entire
intersecting chunks or a silently changed Minecraft world spawn.

Only verified surface harvestable resources and directly accessible nearby item
stacks count. Wheat, carrots, and potatoes must have age 7; beetroot must have age
3. Conservative yields are one item per mature crop or pumpkin and nine wheat
per hay bale. Whole melon blocks do not prove whole melon item supply, and
building logs do not become warm-up harvest instructions. For example, six
mature wheat plants or two nearby pumpkins can support an opening quest; absent
or immature carrots cannot. Warm-up requests use the catalog minimum exactly and
never exceed observed supply. Player inventory possession alone cannot replace
nearby evidence. Missing, unloaded, malformed, or changing observations defer the
lane instead of widening its radius or inventing resources.

Active communal quests, all personal quests (including offline targets), and
pending offering/reward operations reserve distinct item IDs. New assignments
respect reservations in both directions. If wheat and pumpkins are already
reserved and nothing else qualifies, another personal warm-up waits; it does
not request the same item or jump to harder materials.

After communal warm-up, communal difficulty uses the eligible-player average.
After personal warm-up, a normal personal goal is one material band above the
communal reference, but only if that target's own progression unlocks it. Every
fifth issued post-warm-up personal quest prefers one further unlocked band as a
longer-term aspirational goal; if none qualifies it uses the normal goal, or
defers if that pool is also empty. A lucky find can complete a goal without
already owning the requested material when it is assigned; luck never unlocks
an otherwise unsafe band. Assigned goals retain their difficulty when group
membership changes. Later local observations use `SPAWN_SUPPLY_RADIUS`; warm-up
never uses that wider radius.

The LLM and fallback receive the same filtered candidates and quantity bounds.
Communal announcements address the group; personal announcements identify the
target and distinguish nearby warm-up from longer-term goals. Direct rewards
retain the existing economy and ownership.

The quest JSON durably stores lane completion counts and personal assignment
sequence independently of settlements. Only fully successful consumption and
reward completion advances warm-up, exactly once; generation, retirement,
deferral, failure, uncertainty, and dry-run do not. Counts missing from old saves
start conservatively at zero, without guessing historical completions.
Pending settlement XP or structure obligations remain pending while settlement
integration is disabled; partial vanilla rewards do not count as completion.

**In-place upgrade:** stop the single Director writer and preserve a matched
world/configuration/quest JSON/SQLite backup before installing reviewed code.
Keep the current world, world identity, quest hub, and chest coordinates. Before
completing old-policy active quests, the Director revalidates trustworthy local
evidence: untouched invalid or colliding quests can be retired with an
explanation and replaced without consuming offerings or granting rewards.
Unknown evidence suspends the affected quest rather than declaring its resource
absent. Pending and uncertain operations remain intact and retain reservations;
they require the existing recovery/reconciliation process. Accepted old quests
are revalidated once, not cancelled again after normal harvesting.

Do not regenerate terrain or delete quest state for this update. Preserve JSON
and SQLite with their matching world, and never restore state against unverified
inventory changes. Observation and offering commands target Java 26.3.

Earlier temple acceptance evidence: the disposable Java 26.3 server loaded the temple pack before
first generation, generated supported village roots with the Greek composition,
one empty normal chest, and no ender chest, placed controlled roots in all four
rotations, and retained them across a save/restart. RCON verified Java 26.3
protocol/data versions and exact container NBT. Standard-library Director probes
read the real saved village supply and consumed a partial pumpkin stack while
preserving its slot. Unit tests cover communal all-online and private target-only
rewards, shared-chest legacy migration, restart persistence, and lost-response
uncertainty. A rendered client workflow was not verified: the
cached official client reached Java 26.3 but its authentication token returned
HTTP 401, so no client joined the offline acceptance server.

Warm-up acceptance on an isolated Java 26.3 server: independent RCON block checks
and the saved-world observer agreed on six mature wheat and three exposed
pumpkins within 32 blocks; immature carrots, a pumpkin at distance 33, and a
buried pumpkin were excluded. Real same-cycle selection assigned two pumpkins
to the group and six wheat to the player, using distinct item IDs. Both quests
completed against the actual shared chest, preserved an unrelated five-stick
stack, and granted the connected player four experience levels. Minecraft and
the actual Director loop were restarted: both completion counters remained one,
the player's saved levels remained four, and an injected lost-consumption reply
left its exact uncertain record protected without replay. Migration of a copy
of existing quest state retired the old carrot/building-log assignments without
count credit and preserved unrelated inventory, SQLite identity, and recovery
debt. No production rollout or world regeneration was performed for this proof.

The existing official client rendered the disposable farm and distinct
group/target warm-up announcements; inspected screenshots remain under ignored
`.runtime/warmup-client-game/`. This connection used only the isolated server's
offline mode. A separate cached-token session-authentication attempt returned
HTTP 403, so authenticated production joining, village walking access, and
harvesting there remain unverified. Copied production village data no longer
produced phantom carrots; its verified local wheat yield was below the opening
minimum, which correctly defers assignment rather than fabricating supply.

Current-world rollout: [PR #8](https://github.com/Fuzzwah/minecraft_ai_director/pull/8)
was merged and installed from primary `main` on `10.1.1.232:25555`. With both
writers stopped, complete paired data/state archives and a private checksummed
manifest were saved under
`/home/fuz/mc-ai-director-backups/live-quest-warmup-20261007T042848Z/`.
The existing carrot10 and private building-log6 quests were retired without
consumption, rewards, or completion credit. A writer-stopped read-only preview
preserved quest JSON and chest contents and found one mature wheat plus two
string items: no opening item reaches its minimum, so assignment correctly
defers until verified local harvestable yield is sufficient. Do not widen the
radius, invent supply, or move the hub/chest to bypass that result.

The world-generation record, persisted spawn `352, 74, -832`, normal chest
`356, 74, -835`, and structure/settlement configuration checksums were unchanged.
The single Director was restarted and retained the migration without repeating
retirement; both live services were active with zero players. No terrain
regeneration, state reset, billable acceptance call, or uncertain replay occurred.
Starting Minecraft also activates its wanted Keeper service; explicitly stop
that writer again before a writer-stopped preview rather than assuming it stayed
stopped. Authenticated production client access remains unverified.

## Landmark village temples

The bundled `datapack/director_village_temples` now authors sandstone-and-gold
landmarks rather than the previous 5×5 rooms. Each occupies a **25×25 plaza**,
with a three-block raised terrace, seven-block-wide staircase, four tall front
columns, carved twin obelisks, layered gable and gold sun motif, hanging lanterns,
and a recessed stone idol behind the altar. The single empty normal offering
chest is centered in the sanctuary, with clear lid space and walking access.
No resource pack, custom textures, embedded entities, or additional containers
are required. Fine hieroglyphs and sculpture in the reference are approximated
with vanilla carved blocks.

All 32 normal/abandoned roots across the five village styles use this silhouette.
Desert roots use base sandstone stairs/slabs and masonry instead of smooth/cut
sandstone, because vanilla desert abandonment processors can turn the latter
into cobwebs. Vanilla pool weights, projections, processors, and village
placement rules remain unchanged. Root bounds expand; road connectors move to
the outer edge matching their original facing, retaining height and connection
metadata. Ancillary connectors move to the ground-level perimeter. Rotation
validation checks supported stair access from every road to both altar and chest.

Rebuild from the pinned Java 26.3 server archive, or inspect committed assets:

```bash
python3 -B tools/village_temples.py --archive /path/to/server-26.3-core.jar
python3 -B tools/village_temples.py --check
```

This is a **generation-asset change, not a live-world retrofit**. Existing
temples, the configured offering chest, quest state, and settlement starter
templates are untouched. Installing the reviewed pack affects newly generated
village starts only. Replacing an existing temple needs a separately planned,
backed-up world edit; do not regenerate the player world or move the Director's
chest coordinates merely to apply this visual redesign.

Isolated Java 26.3 verification generated villages in all five styles with
downstream vanilla pieces. An official vanilla client rendered the landmark,
walked from the plaza up the stairs in survival mode without jumping, and opened
its empty offering chest. The final template's non-air palette states passed
real-server checks in all four rotations, and the final naturally generated
stairs, hanging lights, and empty chest survived a server restart. These checks
used a loopback-only offline test server, not an authenticated production
session. Preview captures are retained under ignored `.runtime/landmark-smoke/`;
no production rollout was performed.

## Safely enable settlements

1. Back up the Minecraft world and Director state.
2. Install `datapack/director_buildings` into the world's `datapacks` directory.
   Its real compressed NBT templates target **Java 26.3**, datapack format 121.0.
   Reload datapacks as an administrator. For another Minecraft version, verify
   datapack compatibility before enabling construction.
3. Edit `config/settlement.json`. Assign a unique, stable `world_id` to this
   server world. State is scoped by world identity and settlement ID, not by the
   model. Keep this identity with the world backup; do not reuse it for another
   world or point the same configuration at a different RCON server.
4. Replace example coordinates with administrator-reviewed plots. Positions
   are the **minimum corner** of each plot, including the template floor.
   Prepare an empty air volume above solid supporting terrain. The Director
   does not level terrain, clear forests, or replace existing builds.
5. Register every protected volume in `protected_regions`, and protect the
   construction plots from external edits while construction is active.
6. Set settlement `enabled` to `true`. Leave `initialize_on_first_run` false
   unless you want the configured starters. Enable the runtime separately:
   `DIRECTOR_SETTLEMENT_ENABLED=1`.
7. Run an admin dry-run against the actual server before requesting construction.

Environment paths:

| Variable | Default |
| --- | --- |
| `DIRECTOR_STRUCTURES` | `config/structures.json` |
| `DIRECTOR_SETTLEMENT` | `config/settlement.json` |
| `DIRECTOR_DATABASE` | `director_settlement.sqlite3` |
| `DIRECTOR_DRY_RUN` | `0` |

Example protected volume, using inclusive bounds in the settlement dimension:

```json
{"min": {"x": 200, "y": 64, "z": 200},
 "max": {"x": 220, "y": 90, "z": 220}}
```

Plots cannot overlap one another or protected volumes. `protected: true` also
disables an individual plot. Protection lists are administrator-maintained:
vanilla RCON cannot discover a WorldGuard/plugin protection database.

## Admin controls and first vertical slice

No LLM is involved in these operations:

```bash
python3 settlement_admin.py list structures
python3 settlement_admin.py list plots
python3 settlement_admin.py show settlement

# Changes SQLite progression only; does not mutate the Minecraft world.
python3 settlement_admin.py grant settlement-xp 100

# Inspect real loaded plots and print all stage/announcement/title commands.
DIRECTOR_DRY_RUN=1 python3 settlement_admin.py construct workshop_tier_1 \
  --owner CheekyHambone --reason 'Trial of Iron'

# After reviewing the dry-run and backing up:
python3 settlement_admin.py construct workshop_tier_1 workshop_east \
  --owner CheekyHambone --reason 'Trial of Iron' --wait

python3 settlement_admin.py upgrade residential_1 house_tier_2 --owner CheekyHambone
python3 settlement_admin.py remove structure residential_1
python3 settlement_admin.py initialize
python3 settlement_admin.py tick
```

Global `--registry`, `--config`, `--database`, and `--dry-run` options precede
the subcommand. Omitting a construction plot selects the first compatible free
plot deterministically. `--wait` advances stages in the admin process; otherwise
the running Director or repeated `tick` commands advance the durable queue.
Do not run multiple Director loops against the same quest JSON file.

Removal is an explicit admin operation, unavailable to the model. It removes
only an unchanged recorded Director building using individually guarded block
commands. Player edits, sensitive blocks, occupants, and uncertain jobs reject
removal. An already manually dismantled, verified-empty plot can also be released.

`DIRECTOR_DRY_RUN=1` executes only read-only RCON probes. It prints placement,
announcement, title, or removal commands, but sends none of them and leaves
persistent state unchanged. It also prevents quest inventory consumption and
vanilla rewards in the Director. Dry-run XP grants are previews: they do not
unlock buildings for a subsequent command. Read-only inspection still requires
a reachable server and loaded chunks; there is no fake-clear fallback.

## Registry, progression, ownership, and rewards

`config/structures.json` is the approved template registry. Bundled buildings:
Keeper Shrine, Storehouse, staged Workshop, Cottage, and House Tier 2.
Footprints and approved palettes match the bundled NBT assets.

Facing maps to Java rotations: north `none`, east `clockwise_90`, south
`clockwise_180`, west `counterclockwise_90`. Placement translates the template
origin so rotated blocks stay inside the configured plot.

Level thresholds in `config/settlement.json` are cumulative XP. Level unlocks
accumulate; building `unlocks` contribute capability names to Director context.
The current levels are Camp (0), Hamlet (100), Village (300), Town (700).
Capabilities are persisted through structure instances and exposed, not yet
implemented as additional reward/quest systems.

Buildings are unique settlement-wide unless `repeatable: true` is configured.
Repeatable houses are limited to one instance of that structure per owner.
Upgrades require an explicit `progression.upgrades_from` relationship, a higher
tier, an unlocked target, the same plot, and matching ownership. The admin may
omit the owner to retain the existing owner.

Quest tiers still use the original item/experience reward economy. Configured
settlement XP is awarded automatically. The model may additionally choose exact
offered structure reward objects, never arbitrary XP amounts. Structure choices
are offered only on tier 3 by default; blocked/locked rewards remain pending.
XP is granted before construction so the same quest can unlock its building.

```json
{"type": "structure", "structure_id": "workshop_tier_1"}
```

```json
{"type": "settlement_xp", "amount": 30}
```

Compact model context includes settlement level/XP, occupied buildings and
owners, available plots, unlocked structures, capabilities, and recent quests.
Event-driven settlement decisions support only these strict action forms:

```json
{"action": "construct_building", "structure_id": "workshop_tier_1",
 "owner": "CheekyHambone", "reason": "Completed the Trial of Iron"}
```

```json
{"action": "upgrade_building", "plot_id": "residential_1",
 "target_structure": "house_tier_2", "owner": "CheekyHambone",
 "reason": "Service to the settlement"}
```

Unknown IDs, offline/invalid owners, extra keys, templates, coordinates, and
commands are rejected. Template strings come only from trusted configuration.

## Scheduling, persistence, and recovery

`settlement.py` centralizes registry validation, RCON inspection and placement,
SQLite persistence, progression, initialization, and constrained actions.
SQLite stores settlements/configuration, plot status/geometry, structure
instances (including owner, tier, reason and quest ID), construction history
(including rejected/failed actions), jobs, XP ledger, quest history, and events.
Level is derived from persisted XP and thresholds rather than duplicated state.

Workshop stages are foundation → frame → complete. `delay_seconds` is the
delay **after** each stage. Deadlines persist; `tick()` performs due stages
without sleeping. Stage/completion events provide hooks for later particles,
sounds, or other application-controlled effects. Completion announces the
building and shows a title after the successful structure record is committed.
World inspection is synchronous and can take time: every block in the plot is
checked through RCON. Keep plots small.

Initialization validates and reserves all starter plots atomically before
placing anything. Its persistent started flag prevents recreation, including
after partial failure. `initialized` becomes true only when all starters finish.
Explicit admin `initialize` works even when automatic initialization is disabled.

Quest completion persists reward debt before consuming offerings. Settlement
XP and construction use idempotency keys; retries/restarts do not repeat them
or vanilla rewards. A blocked structure reward is retried when the obstruction
or unlock is resolved. Preserve both the quest JSON and SQLite database.

**RCON and SQLite cannot commit atomically.** The application persists mutation
intent first. Interrupted or unacknowledged placements/removals leave plots
protected and are never blindly replayed. Interrupted inventory consumption or
vanilla reward dispatch also remains marked uncertain in quest state.

For an uncertain operation: stop all Director/admin processes, back up state,
inspect the actual world/inventory and the job/reward record, then reconcile
that specific record offline. Do not delete the database or reset initialization
to retry. Failed partial removals must be manually dismantled before a verified
empty plot can be released. Changing geometry or template definitions for
occupied/reserved/protected plots is rejected rather than silently relocating
the building.

## Safety limits

- Every first placement checks the **entire plot** is air. Upgrades and later
  stages require the exact recorded block states and reject changed builds.
- Every mutating command includes loaded-chunk and full-plot player guards.
  Removal additionally guards each block's expected state.
- Containers, signs, beds, furnaces, smokers, beacons, enchanting tables, anvils,
  and other sensitive blocks are never considered expendable. Their presence
  rejects placement/upgrades/removal. Bundled templates intentionally contain
  none of these, and do not include entities or block-entity payloads.
- Managed palettes currently support air, cobblestone, oak planks, glass,
  torches, and oak logs with complete axis states. Unsupported palettes fail
  configuration validation. Extending palettes requires exact-state inspection
  support, not a bypass flag.
- English vanilla affirmative command responses are required. Empty, localized,
  unsupported, or ambiguous responses fail closed.
- Vanilla RCON cannot lock world edits across inspection and template placement.
  External commands/plugins or players reaching into a plot between those
  operations remain a race. Protect plots from edits during construction.
- Installed templates are trusted administrator assets. Do not replace them
  with larger structures, entities, or block entities without validating and
  updating the registry. RCON cannot attest the server's actual template files.

## Verification

```bash
python3 -m unittest discover -v
```

Tests use mocked RCON and actual bundled NBT geometry; no live server is needed.
They cover registry/plot rejection, rotations, protected blocks and occupants,
XP/unlocks, ownership/upgrades, initialization, queued stages across restart,
invalid model actions, dry-run immutability, placement/removal failures, and
durable quest reward recovery.

Live Java 1.21.1 checks also exercised a server-connected dry-run with unchanged
SQLite bytes, staged workshop construction, protected-chest rejection, an owned
cottage-to-house upgrade, safe removal, and persisted buildings across restart.
Live Java 26.3 checks verified fresh-world initialization, exact shrine/storehouse
blocks, idempotent starter initialization, and a guarded removal dry-run with
unchanged SQLite bytes. Loaded-plot guards also passed after more than 60 seconds
without players. The server's affirmative template response remains
`Loaded template "<resource>" at <x>, <y>, <z>`; acknowledgement must match the
requested template and translated placement anchor exactly. Unrecognized or
mismatched acknowledgements still protect the plot rather than replaying it.
Visual client rendering and authenticated player quest completion require a
Minecraft client; RCON inspection does not prove those surfaces.

## Test server on this host

An isolated rootless Podman deployment is installed outside the repository at
`/home/fuz/mc-director-village-test`. It does not use an existing family world.

- **Connect with Minecraft Java 26.3 to `10.1.1.232:25568`.**
- Creative, peaceful, fresh superflat world; 4 player slots and a 2 GB Java heap.
- Online account authentication and whitelist are enabled; `CheekyHambone` is
  whitelisted. Add other accounts explicitly with the console control below.
- RCON is published only on `127.0.0.1:25577`. Generated credentials are in
  owner-only `server.env` and `director.env`, not in this repository.
- The settlement is near `120, -60, -40`; plots use the air layer above the
  flat grass terrain. Registered chunks stay force-loaded.
- The fresh 26.3 world starts with the shrine and storehouse, three available
  plots, and **0 XP, level 1 (Camp)**. No old quests, buildings, or XP were imported.
  Inspect current state before acting; player activity can change it.
- The Director runs in **DEMO mode**: collect quests and configured settlement
  XP, with no external LLM calls. Quest interval is 120 seconds. Building controls
  remain available through the admin CLI; AI-selected building rewards require
  a configured LLM and `DEMO_MODE=0`.

```bash
TEST_ROOT=/home/fuz/mc-director-village-test
"$TEST_ROOT/server.sh" status
"$TEST_ROOT/director.sh" status
"$TEST_ROOT/server.sh" logs
"$TEST_ROOT/director.sh" logs
"$TEST_ROOT/server.sh" console whitelist add YourMinecraftName
"$TEST_ROOT/director.sh" admin show settlement
"$TEST_ROOT/director.sh" admin list plots
DIRECTOR_DRY_RUN=1 "$TEST_ROOT/director.sh" admin remove structure civic_center
```

The removal example is a **preview only**; never omit `DIRECTOR_DRY_RUN=1`
for this smoke check. It requires an unchanged, unoccupied shrine. A cottage
construction preview is locked at the fresh world's starting XP.

For human testing, join as a whitelisted account, read the Keeper's collect
quest, and carry the requested items in your inventory within six blocks of
`120, -60, -40`. Confirm consumption, completion chat/title, vanilla rewards,
and settlement XP. DEMO mode does not select structure rewards.

The previous 1.21.1 world and its paired Director/configuration state are retained
at `/home/fuz/mc-director-village-test/backups/20261006-before-26.3-fresh-world-94fb5220`.
The new world uses a distinct world ID and seed. Rollback must restore the old
world, world identity, Director state, and matching server version together;
never attach the old database to the fresh world. Port 25567 now belongs to the
unrelated `mc_hardcore` server; leave it alone.

Lifecycle controls are `start`, `stop`, and `restart` on each script. Stop the
Director before stopping/restarting Minecraft; start Minecraft before the
Director. Wait for Minecraft's `Done ... For help` log line before starting
the Director. Containers and world/Director state persist after this session;
host-boot autostart is not installed.

The Minecraft container uses `slirp4netns` port forwarding: this avoids the
host's observed `pasta` restart/rebind failure. The Director container uses an
init process and SIGINT shutdown so state connections close cleanly.

Keep `PAUSE_WHEN_EMPTY_SECONDS=-1` in the Minecraft environment. Java 26.3's
native `pause-when-empty-seconds` otherwise defaults to 60; RCON connectivity and
force-load tickets alone did not make paused chunks available to construction.
`ENABLE_AUTOPAUSE=false` disables only the image's separate autopause mechanism.
The rootless Minecraft volume has mapped ownership; move it with
`podman unshare` while stopped rather than changing ownership recursively.

The host's user Podman config, `/home/fuz/.config/containers/containers.conf`,
sets `[engine]` with `cgroup_manager = "cgroupfs"`. This explicitly selects the
existing fallback backend when no systemd user session is available, preventing
the repeated systemd/linger/fallback warnings without suppressing other warnings.
It applies to all Podman commands run as `fuz`; no container restart is needed.