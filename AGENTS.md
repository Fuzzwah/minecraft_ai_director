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
Village-temple generation and adaptive offerings target Java 26.3; the existing
settlement construction test server remains Java 1.21.1 and must not be used as
proof of temple generation. Do not use a startup or construction retry as a
recovery mechanism.

Previously verified on Java 1.21.1: dry-run immutability, staged workshop
construction, chest rejection, owned cottage-to-house upgrade, safe removal,
and world/SQLite persistence through restart. On the fresh Java 26.3 world:
starter initialization, exact shrine/storehouse blocks, idempotent initialization,
guarded removal preview with unchanged SQLite, and loaded chunks beyond the native
idle-pause threshold. These checks do **not** prove visual client rendering or
authenticated player quest completion; those require a Minecraft client.
Update `README.md` when the operating contract changes.

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
