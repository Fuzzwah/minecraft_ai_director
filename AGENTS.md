# Agent guide

## Project and code map

This project is a standard-library Python Minecraft Java Director. Python 3.10+
handles log monitoring, collect quests, constrained LLM decisions, RCON rewards,
and persistent template-based settlement construction. Read `README.md` for the
full configuration and admin contract before changing behavior.

- `director.py`: environment configuration, RCON client, log/player monitoring,
  adaptive communal/private quest generation, shared temple-chest offering
  transactions, vanilla rewards, quest JSON state, and settlement integration. Configuration is
  read at module import.
- `quest_supply.py`: standard-library Anvil supply observation, Java 26.3
  inventory parsing, bounded player strength profiles, and fail-closed candidate
  context. It never emits commands or accepts model-authored IDs/scores.
- `settlement.py`: `StructureManager`; trusted registry/config validation,
  plot inspection, placement/upgrades/removal, staged jobs, SQLite persistence,
  XP/unlocks, initialization, and constrained model actions.
- `settlement_admin.py`: admin CLI; calls the same manager, never an LLM.
- `config/structures.json`: approved building IDs, templates, palettes,
  footprints, stages, and progression relationships.
- `config/settlement.json`: world identity, geometry, protected regions,
  progression, and starter settings. Repository coordinates are examples.
- `datapack/director_buildings`: real compressed NBT assets; targets Java
  26.3, datapack format 121.0.
- `tests/test_director.py`, `tests/test_settlement.py`, `tests/support.py`:
  isolated unittest coverage, fake RCON, and decoding of the real bundled NBT.

No third-party Python packages or build step are required. Settlements are off
by default; enabling them requires both `DIRECTOR_SETTLEMENT_ENABLED=1` and
`settlement.enabled=true` in the selected configuration.

## Non-negotiable safety and persistence invariants

- Models choose validated IDs/actions, never commands, coordinates, template
  paths, arbitrary XP, or unvalidated reward objects. Python owns mutation.
- A plot position is its **minimum corner**, including the template floor.
  Rotation translates the template anchor; do not equate it with the plot
  corner. Facing: north `none`, east `clockwise_90`, south `clockwise_180`,
  west `counterclockwise_90`.
- First placement requires the entire plot to be air with supporting terrain.
  Upgrades, subsequent stages, and removal require exact recorded block states.
  Do not add terrain-clearing or overwrite fallbacks.
- Sensitive blocks (containers, signs, beds, furnaces, etc.), players, unloaded
  chunks, protected regions, and changed builds reject mutation. Keep the
  existing loaded-chunk/player guards on every mutating command and the
  per-block expected-state guards on removal.
- Vanilla RCON cannot atomically lock external world edits. Protect construction
  plots from players/plugins/other commands while jobs run.
- Installed templates are trusted admin assets. Keep NBT geometry/palette and
  registry definitions consistent; do not introduce entities/block entities or
  bypass exact-state inspection for unsupported blocks.
- On Java 1.21.1 and 26.3 the affirmative placement response is exactly
  `Loaded template "<resource>" at <x>, <y>, <z>`. Match the requested template
  and translated anchor. Do not accept guessed `Placed template` wording,
  generic success substrings, empty responses, or localized responses.
- SQLite and Minecraft cannot commit atomically. Persist mutation intent first;
  interrupted/unacknowledged operations protect the plot and must not be replayed
  blindly. Initialization's durable started flag prevents starter recreation.
- Quest completion persists reward debt before consuming offerings; idempotency
  keys prevent duplicate XP/building rewards. Communal and private quests use
  only the configured loaded normal chest; communal quests reward eligible online
  players at completion, while private quests reward only their single target.
  Never read or consume a private offering from an ender chest, player inventory,
  guessed coordinate, arbitrary item ID, or model-authored score. Migrate legacy
  private ender-chest submission state in memory and persist the shared-chest
  source without touching the old inventory. Preserve **both** quest JSON
  (`DIRECTOR_STATE`) and SQLite (`DIRECTOR_DATABASE`), plus the matching world
  and configuration. Never run two Director loops against the same quest JSON.
- Opening quests require verified mature/harvestable local supply within 32
  horizontal blocks of the selected village quest hub and supply-backed minimum
  quantities. Do not treat whole-section palette totals as nearby availability.
  Active communal/private quests and pending operations reserve distinct item
  IDs, including offline personal targets. Preserve reservations and lane
  warm-up progress across restarts; only fully successful completion advances
  progress once. Retire only untouched policy-invalid legacy assignments, never
  pending or uncertain operations; this upgrade does not regenerate the world.
- `world_id` is a stable world identity, not a retry switch. Do not delete the DB,
  reset initialization flags, change world IDs, or relocate occupied/reserved/
  protected plots to get past a failure.
- For uncertain state: stop Director/admin writers, back up world and state,
  inspect actual blocks/inventory and durable records, then reconcile only the
  verified operation offline. Existing reconciliation backups are not junk.
- `DIRECTOR_DRY_RUN=1` uses read-only RCON probes and an in-memory DB copy; it
  must neither mutate the world/inventories/rewards nor persistent state.
  Inspection still needs a reachable server and loaded chunks.

## Development and verification

From the repository root:

```bash
python3 -B -m unittest discover -v
python3 -B settlement_admin.py --help
```

Tests need no live server. Keep them deterministic and isolated; test observable
behavior, failures, ownership, boundaries, and durable recovery rather than
source text or implementation wiring. Use the actual bundled NBT for geometry
checks. When changing templates, update matching registry definitions and
validate rotations as well as unrotated footprints.

For RCON/world changes, also smoke the actual Java test server below. Start with
an admin dry-run and inspect plot availability before any live construction.
Village-temple generation and adaptive offerings target Java 26.3. The isolated
settlement server below also runs 26.3, but its existing construction plots do
not prove village generation: use a disposable 26.3 world with the generation
pack installed before first terrain generation. Do not use a startup or
construction retry as a recovery mechanism.

Previously verified on Java 1.21.1: dry-run immutability, staged workshop
construction, chest rejection, owned cottage-to-house upgrade, safe removal,
and world/SQLite persistence through restart. On the fresh Java 26.3 world:
starter initialization, exact shrine/storehouse blocks, idempotent initialization,
guarded removal preview with unchanged SQLite, and loaded chunks beyond the native
idle-pause threshold. These checks do **not** prove visual client rendering or
authenticated player quest completion; those require a Minecraft client.
Update `README.md` when the operating contract changes.

## Current designated deployment

The current player-facing Java 26.3 deployment is **`10.1.1.232:25555`**:
`mc_ai_director_default.service` and `mc_ai_director_default_keeper.service`,
with source mounted read-only from primary `main` at
`/home/fuz/code/minecraft_ai_director`. Ship through the reviewed topic-branch PR
workflow before synchronizing that checkout; never mount an implementation
worktree into the live Director.

### Live identity and configuration

The landmark world is deployed through PR #12; PR #13 records its acceptance.
Current world spawn and Director hub are **`76, 90, 298`**, and the normal offering
chest is **`76, 90, 304`**. The nearest village is plains at `64, ~, 288`; its
temple bounds are `64, 86, 288` through `88, 105, 312`. These are observed
coordinates, not defaults for another world. Inspect current state before use.

- Minecraft data: named volume `mc_ai_director_default_data`, mounted at `/data`.
- Keeper mounts that data read-only at `/minecraft` and
  `mc_ai_director_default_state` read-write at `/state`. Active quest JSON is
  `/state/director_state.json`; optional SQLite is `/state/director_settlement.sqlite3`.
- Quadlet sources:
  `/home/fuz/.config/containers/systemd/mc_ai_director_default.container` and
  `mc_ai_director_default_keeper.container` in the same directory. Edit these,
  not generated units under `/run/user/1000/systemd/generator/`.
- Private Keeper environment: `/home/fuz/code/minecraft_ai_director/director.env`.
  RCON comes from Podman secret `mc_ai_director_default_rcon`; never print full
  container environments, server properties, secrets, or private env files.
- Hub/chest overrides are in the Keeper Quadlet. Changing world spawn does not
  update those overrides; run `systemctl --user daemon-reload` after unit edits.
- Minecraft uses `OVERRIDE_SERVER_PROPERTIES=false`: existing
  `/data/server.properties` is authoritative. Merely adding image environment
  variables will not rewrite its settings. Keep `pause-when-empty-seconds=-1`;
  disabling image autopause alone does not disable Java's native idle pause.
- Current policy is survival/normal, online authentication, and settlements
  disabled. Preserve actual access policy and the existing LLM configuration;
  do not copy the isolated server's creative/DEMO settings into production.

The pre-landmark rollback generation, paired archives, checksums, private
configuration, and deployment evidence are under
`/home/fuz/mc-ai-director-backups/live-landmark-regeneration-20261008T221528Z/`.
Retain it and older reconciliation snapshots. It is not a substitute for a
fresh backup after subsequent play.

### Routine update procedure — preserve the world

1. Inspect live service/container status, players, mounts, and primary checkout
   changes. Use rootless Podman and `systemctl --user` as `fuz`, never
   `sudo podman`. Preserve unrelated files such as an untracked `registries.json`.
   Use **systemd** to manage this deployment, not the isolated server's wrappers
   or `podman restart` behind systemd's back.
2. Verify and merge the topic-branch PR before synchronizing primary `main`.
   Stop the Keeper before changing its mounted Python source. Fast-forward the
   primary checkout only; never force-reset it or mount an implementation worktree.
   A read-only bind mount still sees host edits. Python changes need a Keeper
   restart; documentation-only changes do not require either service to restart.
3. For world/configuration/datapack changes, stop Keeper, flush Minecraft, then
   stop Minecraft before taking complete paired data/state archives plus private
   configuration and deployment references. Use directory mode `0700`, archive
   and manifest mode `0600`, verify archive contents and SHA256 checksums, and
   record the seed, spawn, hub, chest, and source commit. Preserve quest JSON,
   SQLite (including any journal/WAL files), world identity, and recovery records.
4. Install reviewed runtime datapack/config **copies** explicitly while stopped;
   updating Git alone does not update the pack under `world/datapacks`.
   Ordinary updates never delete terrain, reset progression, move the offering
   chest, or change the seed. Updated village roots affect new village starts,
   not existing temples. Regeneration requires separate explicit authorization.
5. Start only stopped services. For a new Minecraft startup, require that
   startup's `Done ... For help` line, then verify RCON. A systemd `active`
   result or bound port alone is not readiness. If Minecraft was already running,
   use `rcon-cli list` rather than waiting for a startup line that will not recur.
6. Verify the changed path with Keeper stopped: loaded chunks, actual block
   states/container identity, current coordinates, and a read-only Director
   preview as appropriate. Use `DIRECTOR_DRY_RUN=1`, read-only world/state mounts,
   and API probes, **not a second Director loop or an LLM call**. Compare state
   checksums around the preview. A missing/below-minimum supply candidate means
   defer; never fabricate crops, widen the warm-up radius, or move the hub to
   manufacture a passing check.
7. After acceptance, restore any temporary admission policy and start exactly
   one Keeper writer. Check its startup log, effective hub/chest settings,
   authenticated RCON access, and both service states. For world changes, verify
   save/restart persistence before reopening. If mutation/state is uncertain,
   stop writers and restore the matched generation or reconcile offline; never
   retry placement, discard debt, or mix old world and new state.

**Prevent accidental Keeper activation:** Minecraft **Wants** Keeper, and Keeper
is `BindsTo`/`PartOf` Minecraft. Starting Minecraft can start the writer too.
For an update requiring a writer-stopped startup, use this maintenance sequence
(not for a status-only inspection):

```bash
systemctl --user stop mc_ai_director_default_keeper.service
systemctl --user mask --runtime mc_ai_director_default_keeper.service
podman exec mc_ai_director_default rcon-cli save-all flush
systemctl --user stop mc_ai_director_default.service
# Take and verify backups; install the authorized update while stopped.
systemctl --user start mc_ai_director_default.service
# Wait for this startup's readiness, inspect actual activation, run read-only checks.
# Only after acceptance (or verified rollback), restore the writer:
systemctl --user unmask --runtime mc_ai_director_default_keeper.service
systemctl --user daemon-reload
systemctl --user start mc_ai_director_default_keeper.service
```

Do not leave the runtime mask installed after completing maintenance. Stop log
following separately; detaching a log watcher must not stop Minecraft.

### Rootless storage and first-generation pitfalls

Resolve named-volume paths with `podman volume inspect --format '{{.Mountpoint}}'
<volume>` rather than guessing another user's container store. Host file tools
may report an inaccessible mapped directory as empty; this is **not** evidence
that world/state is absent. Inspect it through `podman unshare` or the correct
container, without dumping credential-bearing files. Never recursively chown a
volume to make a preview work.

The live containers use Podman's **default rootless user namespace** (empty
`HostConfig.UsernsMode`), unlike the isolated Keeper's `keep-id` mapping. A
verified mounted-world preview used that same default namespace and
`--network=container:mc_ai_director_default`, read-only volume mounts, and the
existing RCON secret. Explicitly requesting
`--userns=container:mc_ai_director_default` failed with crun `cannot setns ...
Invalid argument`; do not repeat it when both containers already use the default
namespace. Inspect the current mode before choosing flags; never compensate by
changing live volume ownership.

For **explicitly authorized regeneration only**, preserve the current seed and
generation/access policy unless the user separately requests changes. Install
the verified pack before first generation, gate normal player admission during
acceptance without disabling online authentication, and provision fresh player
and quest state (plus a fresh database/world ID if settlements are enabled).
Do not import old pending operations into new terrain.

Create **both** the new world parent and its datapacks child with the Minecraft
process's mapped UID/GID. This deployment's verified in-namespace identity is
`1000:1000`; inspect it again before use. Creating only the leaf with
`install -d -o 1000 -g 1000` leaves intermediate parents owned by namespace root.
That caused `AccessDeniedException: ./world/session.lock` before generation.
After moving the backed-up old world aside, the explicit creation is:

```bash
# DATA is the inspected data-volume mountpoint; server stopped, regeneration authorized.
podman unshare install -d -m 775 -o 1000 -g 1000 \
  "$DATA/world" "$DATA/world/datapacks"
podman unshare stat -c '%n uid=%u gid=%g mode=%a' \
  "$DATA/world" "$DATA/world/datapacks"
```

Check ownership **before** starting. If bootstrap fails, stop the service and
inspect actual files and the exact error. Only correct a proven setup defect in
the new, ungenerated directory; never repeatedly start, regenerate, or alter
existing world ownership as a recovery mechanism.

### Java 26.3 verification details

- Use `tools/nbt.py` and `quest_supply.AnvilWorldReader` for real saved data.
  Overworld regions are under `world/dimensions/minecraft/overworld/region/`.
  Spawn is `Data.spawn.pos` in `world/level.dat`; seed/generator are in
  `world/data/minecraft/world_gen_settings.dat` (`data.seed`), not an assumed
  older `level.dat` layout. Decode only required fields; avoid dumping private data.
- Locate all five village styles from the recorded pre-regeneration spawn and
  choose the nearest horizontal result. Derive temple/chest coordinates from
  the actual generated root and rotation, not repository example coordinates.
  Confirm solid support, two-block player clearance, stairs/road access, and
  chest-lid clearance before setting spawn or updating Keeper overrides.
- `setworldspawn <x> <y> <z>` works. Do not append a lone yaw: this version expects
  both yaw and pitch if orientation is supplied. The rule is
  `minecraft:respawn_radius`, **not** `minecraft:spawn_radius`; current value `0`
  keeps default respawns at the verified entrance. Preserve it on routine updates.
- For the vanilla `place template` command, the half-turn argument is `180`,
  not `clockwise_180`. Do not confuse command syntax with internal rotation names.
  Iron chains use `minecraft:iron_chain`, not `minecraft:chain`; unknown template
  IDs can disappear silently. Verify actual placed states, not just NBT decoding.
- Bare `execute if loaded ...` / `execute if block ...` returns `Test passed` or
  `Test failed`. An empty response from `... run say ...` is not proof of success.
  Check the normal chest's exact identity and contents through `data get block`.
- A successful status handshake at `10.1.1.232:25555` verifies Java 26.3/protocol
  777, not authenticated gameplay. Landmark client rendering, survival stair
  traversal, and chest opening were verified on an isolated vanilla client.
  Do not claim authenticated production joining or quest completion from those
  results, RCON, or mocked tests alone.

## Isolated test server on this host

Run rootless Podman as **`fuz`**, not `sudo podman` (root has a different container
store). Existing family servers/worlds are unrelated; do not modify them.

User Podman config `/home/fuz/.config/containers/containers.conf` sets
`[engine] cgroup_manager = "cgroupfs"`. This explicitly selects the backend
already used without a systemd user session, avoiding repeated fallback warnings
without filtering stderr or enabling lingering. It applies to all `fuz` Podman
commands, not root's configuration. No container restart is needed for this
CLI setting; `podman info --format '{{.Host.CgroupManager}}'` should show `cgroupfs`.

| Item | Value |
| --- | --- |
| Repository | `/home/fuz/orca/workspaces/minecraft_ai_director/village` |
| Test root | `/home/fuz/mc-director-village-test` |
| Minecraft container | `mc_director_village_test` |
| Director container | `mc_director_village_test_director` |
| Client connection | **`10.1.1.232:25568`, Minecraft Java 26.3** |
| RCON | **`127.0.0.1:25577`**, never public |
| World | `$TEST_ROOT/data/world` |
| Installed datapack | `$TEST_ROOT/data/world/datapacks/director_buildings` |
| Runtime registry/config | `$TEST_ROOT/config/structures.json`, `$TEST_ROOT/config/settlement.json` |
| Settlement database | `$TEST_ROOT/director_settlement.sqlite3` |
| Private environment | `$TEST_ROOT/server.env`, `$TEST_ROOT/director.env` |

The environment files contain generated credentials: never print, commit, or
copy their contents into chat/docs. The test root is mode 0700; env files are
0600. Quest state belongs under the test root at the configured `DIRECTOR_STATE`
path; it may not exist until the first save.

The server uses creative/peaceful superflat terrain, online authentication, a
whitelist (`CheekyHambone`), four player slots, and a 2 GB heap. Settlement plots
are near **120, -60, -40**, above grass at y=-61; chunks are force-loaded.
The fresh 26.3 world started with 0 XP (level 1, Camp), shrine and storehouse,
and three free plots. No quests or progression were imported from the old world.
**Inspect current state rather than assuming this remains true.**

The Director runs `DEMO_MODE=1`: no external LLM calls, quest interval 120 seconds.
AI-selected structure rewards require explicit LLM configuration and demo mode
disabled; do not enable billable calls implicitly.

The retained 1.21.1 world and paired configuration/Director state are under
`$TEST_ROOT/backups/20261006-before-26.3-fresh-world-94fb5220`. The current world ID
is `director-test-26.3-797c7e0c-d369-4ac8-ad1a-9bf05beea172`; keep it with this
world only. Rollback must restore the old world, identity, state, and server
version together. Never reuse old progression in the fresh world.

Keep `VERSION=26.3`, `ENABLE_AUTOPAUSE=false`, and
`PAUSE_WHEN_EMPTY_SECONDS=-1` in the private Minecraft environment. The latter
disables Java's native 60-second idle pause; the former autopause flag does not.
An idle-paused server accepted RCON but failed loaded-plot guards even with
force-load tickets. The mapped rootless volume ownership requires `podman unshare`
for moves while stopped; do not recursively chown the volume.

Port 25567 belongs to the unrelated `mc_hardcore` server. The user approved
25568 for this isolated server; do not stop family containers to reclaim 25567.

### Start and operate existing containers with Podman

Check status first with the inspect command below. Start only stopped containers.
If Minecraft is already running, verify readiness with
`/home/fuz/mc-director-village-test/server.sh console list` instead of waiting for
a new startup log line; leave a running Director alone.

```bash
export TEST_ROOT=/home/fuz/mc-director-village-test
podman start mc_director_village_test
podman logs --since 1m --follow mc_director_village_test
```

Wait for the **new startup's** `Done ... For help` line. Ctrl-C stops log following,
not the container. Then start and inspect the Director:

```bash
podman start mc_director_village_test_director
podman logs --since 1m --follow mc_director_village_test_director
```

Again, Ctrl-C only detaches the log viewer. Inspect both without dumping secrets:

```bash
podman inspect --format '{{.Name}}: {{.State.Status}}' \
  mc_director_village_test mc_director_village_test_director
```

Stop the Director **before** stopping/restarting Minecraft. For a restart:

```bash
podman stop --time 30 mc_director_village_test_director
podman restart --time 60 mc_director_village_test
podman logs --since 1m --follow mc_director_village_test
```

After the new Minecraft ready line, start the Director again. To stop both:

```bash
podman stop --time 30 mc_director_village_test_director
podman stop --time 60 mc_director_village_test
```

Containers/state persist independently of terminal sessions. Restart policies are
`unless-stopped`; **host-boot autostart is not installed**.

Equivalent wrappers are `$TEST_ROOT/server.sh` and `$TEST_ROOT/director.sh`;
these accept `start`, `stop`, `restart`, `status`, and `logs`:

```bash
"$TEST_ROOT/server.sh" console list
"$TEST_ROOT/server.sh" console whitelist add YourMinecraftName
"$TEST_ROOT/director.sh" admin show settlement
"$TEST_ROOT/director.sh" admin list structures
"$TEST_ROOT/director.sh" admin list plots
DIRECTOR_DRY_RUN=1 "$TEST_ROOT/director.sh" admin remove structure civic_center
```

The admin wrapper loads the private environment and invokes host Python with
`-B`; it does not start another Director loop. The example is a guarded removal
**preview only** requiring the shrine to remain unchanged and unoccupied. Keep
`DIRECTOR_DRY_RUN=1`; do not remove a starter as a smoke check. Cottage construction
is locked at starting XP. For deliberate live construction, select an unlocked
structure and compatible free plot; `--wait` advances stages in the admin process.
Otherwise the running Director or admin `tick` advances durable jobs.
Removal is admin-only.

### Recreate a missing container, without replacing its state

Only use these commands if the corresponding container is absent. They depend
on the existing private env/config files, installed datapack, and host paths;
they are not a fresh-world provisioning recipe. Never remove the world/database
or replace credentials just to recreate a container. After creation, follow the
startup/readiness sequence above.

```bash
export TEST_ROOT=/home/fuz/mc-director-village-test
export REPO=/home/fuz/orca/workspaces/minecraft_ai_director/village

podman create --name mc_director_village_test \
  --network slirp4netns:port_handler=rootlesskit \
  --restart=unless-stopped --env-file "$TEST_ROOT/server.env" \
  --publish 10.1.1.232:25568:25565/tcp \
  --publish 127.0.0.1:25577:25575/tcp \
  --volume "$TEST_ROOT/data:/data:Z" --stop-timeout 60 \
  docker.io/itzg/minecraft-server@sha256:783d2712019a3996b4168752517a08d3448ef8995879b200316c3888f98dc394

podman create --name mc_director_village_test_director \
  --init --stop-signal SIGINT --restart=unless-stopped \
  --network=host --userns=keep-id --user 1000:1000 \
  --env-file "$TEST_ROOT/director.env" \
  --env PYTHONDONTWRITEBYTECODE=1 \
  --volume "$REPO:/app:ro" --volume "$TEST_ROOT:$TEST_ROOT" \
  --workdir /app --stop-timeout 30 \
  docker.io/library/python@sha256:d3fef00fbd9ab948d206fe74c1bdd8105f535e5bd90a6074558c31c328ae48b7 \
  python3 -u director.py
```

Keep `slirp4netns:port_handler=rootlesskit`: the host's default `pasta` backend
previously failed to rebind ports on restart. Keep Director `--init` and
`--stop-signal SIGINT`: Python as PID 1 previously ignored SIGTERM and required a
forced kill. Both choices were verified with the running deployment.

The Director's repository mount is read-only, but sees host source edits;
restart the Director to load changed Python code. Runtime config and datapack
are **copies**, not live repository mounts. Explicitly deploy reviewed changes
to the test root, retaining its world identity and test coordinates; reload the
datapack as needed. Stop writers and back up before changing durable definitions.
Do not blindly copy repository example settlement coordinates over host config.
