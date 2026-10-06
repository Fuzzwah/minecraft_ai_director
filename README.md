# Minecraft AI Director

Standard-library Python Director for a Minecraft Java server. It monitors server
logs, detects online players over RCON, generates constrained collect quests,
consumes offerings at spawn, and grants application-controlled rewards.

Settlement construction extends the same trust boundary: the model requests
approved building IDs; Python owns coordinates, templates, validation, scheduling,
and world mutation. Model responses are never executed as commands.

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

A local `director.env` is Git-ignored but is not loaded automatically. Keep it
owner-only (`chmod 600 director.env`) and load it with
`set -a; source ./director.env; set +a` in Bash before starting the Director.
Never commit API keys or RCON credentials.

Settlement integration is **off by default**. Existing quests, item rewards,
player detection, log monitoring, and LLM quest generation do not require it.

## Safely enable settlements

1. Back up the Minecraft world and Director state.
2. Install `datapack/director_buildings` into the world's `datapacks` directory.
   Its real compressed NBT templates target **Java 1.21–1.21.1**, pack format 48.
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

## Spec-driven development with OpenSpec

[Fission-AI OpenSpec](https://github.com/Fission-AI/OpenSpec) is development-only
tooling; it adds no Python runtime dependencies. Requires Node.js 20.19+.
The project was initialized with OpenSpec **1.14.1**, the core workflow,
Oh My Pi commands, and vendor-neutral shared agent skills:

```bash
npm install -g @fission-ai/openspec@1.14.1
openspec init --tools oh-my-pi,agents --profile core --no-animation
```

Project context and safety rules are in `openspec/config.yaml`. Accepted
capabilities belong in `openspec/specs/`; proposals and implementation artifacts
belong in `openspec/changes/`. No feature proposal is created by setup.

In Oh My Pi, use `/opsx-explore` to investigate an idea, then
`/opsx-propose <idea-or-change-name>` to draft requirements, design, and tasks.
Review the plan before `/opsx-apply`; use `/opsx-update` to revise it,
`/opsx-sync` to synchronize delta specs, and `/opsx-archive` after completion.
Other assistants can use the matching `.agents/skills/openspec-*` skills.
Restart the assistant session if newly generated commands are not discovered.

Useful terminal commands:

```bash
openspec list
openspec list --specs
openspec validate --all --strict --no-interactive
openspec doctor
openspec update
```

`openspec update` refreshes generated skills and commands. Keep project-specific
guidance in `openspec/config.yaml` and `AGENTS.md`, not in generated files.
OpenSpec planning does not deploy datapacks, create temples, enforce player
protection, or start servers. Those actions need explicit implementation and
deployment steps targeting the correct world and Minecraft version.

Setup was smoke-checked with `openspec doctor` and an isolated temporary change:
project context/rules reached artifact instructions, strict validation passed,
and the planning workflow reached the implementation-ready state. The temporary
change was removed; no feature implementation or live-world verification occurred.

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
The server's affirmative template response is
`Loaded template "<resource>" at <x>, <y>, <z>`; acknowledgement must match the
requested template and translated placement anchor exactly. Unrecognized or
mismatched acknowledgements still protect the plot rather than replaying it.
Visual client rendering and authenticated player quest completion require a
Minecraft client; RCON inspection does not prove those surfaces.

## Test server on this host

An isolated rootless Podman deployment is installed outside the repository at
`/home/fuz/mc-director-village-test`. It does not use an existing family world.

- **Connect with Minecraft Java 1.21.1 to `10.1.1.232:25567`.**
- Creative, peaceful, fresh superflat world; 4 player slots and a 2 GB Java heap.
- Online account authentication and whitelist are enabled; `CheekyHambone` is
  whitelisted. Add other accounts explicitly with the console control below.
- RCON is published only on `127.0.0.1:25577`. Generated credentials are in
  owner-only `server.env` and `director.env`, not in this repository.
- The settlement is near `120, -60, -40`; plots use the air layer above the
  flat grass terrain. Registered chunks stay force-loaded.
- The test state contains the shrine, storehouse, staged workshop, and a Tier 2
  house. Workshop and house ownership is assigned to `CheekyHambone`;
  `residential_2` remains available. Test XP is 300, settlement level 3.
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
DIRECTOR_DRY_RUN=1 "$TEST_ROOT/director.sh" admin construct cottage_tier_1 residential_2 --owner CheekyHambone
```

Lifecycle controls are `start`, `stop`, and `restart` on each script. Stop the
Director before stopping/restarting Minecraft; start Minecraft before the
Director. Wait for Minecraft's `Done ... For help` log line before starting
the Director. Containers and world/Director state persist after this session;
host-boot autostart is not installed.

The Minecraft container uses `slirp4netns` port forwarding: this avoids the
host's observed `pasta` restart/rebind failure. The Director container uses an
init process and SIGINT shutdown so state connections close cleanly.

The host's user Podman config, `/home/fuz/.config/containers/containers.conf`,
sets `[engine]` with `cgroup_manager = "cgroupfs"`. This explicitly selects the
existing fallback backend when no systemd user session is available, preventing
the repeated systemd/linger/fallback warnings without suppressing other warnings.
It applies to all Podman commands run as `fuz`; no container restart is needed.