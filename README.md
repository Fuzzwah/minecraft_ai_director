# Minecraft AI Director

Server-wide cooperative collection quests for **official vanilla Minecraft Java Edition 26.3**, Java 25, datapack 121.0. No plugins, server/client mods, resource pack, or third-party server API. Python 3.11+ uses only its standard library; the owner service requires Linux advisory locks and Unix peer credentials.

The director selects a bounded, catalog-approved objective. Players contribute to one registered Overworld chest. A synchronous datapack function rechecks the exact chest state, consumes only the required plain items, and freezes eligible online survival/adventure UUIDs. Each recipient gets the quest's frozen reward in one empty personal Ender Chest slot. Full/offline inventories retain durable pending entitlements; claims cannot change the reward or grant another copy.

AI chooses among persisted candidates and supplies bounded title/flavor strings, never commands, objective quantities, recipients, or rewards. Invalid responses, quota errors, and timeouts select a deterministic local candidate. No automatic provider/model retry. `DEMO_MODE=1` bypasses HTTP, **not real inventory mutations**.

## Current Podman deployment

The fresh playable server is `mc_ai_director`, with the director in `mc_ai_director_owner`. Both are running with `unless-stopped` restart policies. All other Minecraft containers were stopped without deleting their containers or volumes; unrelated services were left running.

| Resource | Deployment value |
| --- | --- |
| LAN / Tailscale connection | `10.1.1.232:25565` / `100.108.49.90:25565` |
| Minecraft / RCON publication | `0.0.0.0:25565` / `127.0.0.1:25575` |
| World / director state volumes | `mc_ai_director_data` / `mc_ai_director_state` |
| Vanilla runtime | Official 26.3, Java 25, survival, normal difficulty, 4 GiB Java heap, 20 players |
| Access | Online mode; enforced whitelist: `Fuzzywah`, `BeatiBubbles`, `CheekyHambone`; no operators granted |
| Collection chest | Overworld `-28 65 -80`, inside the columned offering temple |
| Personal reward access | Ender Chest directly beside it at `-29 65 -80` |
| Configuration | `.runtime/live/server.env`, `.runtime/live/director.env`, `.runtime/live/director.json` |

The named world volume is fresh, not a copy of the fixture or an existing world. The collection area's chunk `[-2, -5]` has an operator-created force-load ticket; registration intentionally records `forceload_owned=0`, so unregistering does not remove that ticket. The director mounts the world volume read-only for the verified server jar and allowlisted log events, and writes its ledger only to its separate state volume. It runs as UID/GID 1000 with capabilities dropped, a read-only root filesystem, and no public administrative listener. Environment files are private (0600); do not commit, print, or shell-source them.

Generation currently uses **local/demo selection**, with real gameplay and reward delivery. No provider credentials or model were supplied, so paid AI calls are not enabled. To enable an explicitly chosen provider, set `demo_mode` to `false` in the live JSON and supply `LLM_URL`, `LLM_MODEL`, and `LLM_API_KEY` through the private director environment; changing container environment requires recreating only the owner container with its existing state volume and identical mounts. Do not start a second owner. See the production configuration and recovery sections below.

The live profile sets `cooldown_seconds=0`: completion schedules the next shared quest immediately while the community/chest remain ready and the daily allowance remains. The twelve-quests-per-UTC-day cap still applies, and full/offline old rewards do not block unrelated new quests. `share_chat=true` enables bounded, untrusted player-chat context. Chat cannot execute console commands, change rewards, or invent objectives. With local/demo generation there are no provider calls; chat context is available for future explicitly configured AI generations.

From this checkout:

```sh
podman exec mc_ai_director_owner python3 /app/director.py --config /director.json admin doctor
podman logs --follow mc_ai_director
podman logs --follow mc_ai_director_owner
podman exec mc_ai_director rcon-cli 'whitelist add YourAccount'

# Graceful stop: checkpoint the director before saving/stopping Minecraft.
podman stop --time 60 mc_ai_director_owner
podman stop --time 90 mc_ai_director

# Start Minecraft first; wait for its "Done" log before starting the owner.
podman start mc_ai_director
podman start mc_ai_director_owner
```

Verified on this deployment: LAN status reports 26.3/protocol 777; official artifact hash, datapack 121.0, registered chest, log source, and SQLite integrity pass. Empty-community quest dispatch is rejected. A coordinated clean stop/start preserved installation/chest/checkpoint with zero reviews. Authenticated players subsequently joined and completed quests. With zero cooldown, the six-iron quest completed for two recipients and automatically scheduled an oak-log quest; its completion automatically scheduled copper. The temple preserved the registered chest, crafting table, and furnace, and the owner confirmed its live appearance. `community_offline` is expected when nobody eligible is online. Rootless host-boot startup, account rename, and full production certification remain unverified.

## Isolated Podman test server

`tools/test_server.py` manages a separate rootless `itzg/docker-minecraft-server` container in the same direct-Podman style as `mc_do_not_die`. It never manages that existing container or volume.

| Resource | Test value |
| --- | --- |
| Container / persistent volume | `mc_ai_director_test` / `mc_ai_director_test_data` |
| Minecraft / RCON publication | `127.0.0.1:25566` / `127.0.0.1:25576` |
| New-container image default | `docker.io/itzg/minecraft-server@sha256:783d2712019a3996b4168752517a08d3448ef8995879b200316c3888f98dc394` |
| Runtime | VANILLA 26.3, Java 25, UID/GID 1000, pasta, restart policy `no` |
| Private configuration | `.runtime/test-server.env`, `.runtime/director-test.env`, mode 0600 |

Existing containers are preserved rather than recreated to enforce these defaults. During verification the existing test container was externally recreated using `docker.io/itzg/minecraft-server:latest` and manually managed properties; its official 26.3 server jar was still SHA-1 verified. The helper's pinned image applies to new container creation, not retroactive replacement. The final isolated test state is stopped, with the director operator-paused and its volume/ledger retained.

The owner must accept the Minecraft EULA explicitly when creating the server:

```sh
EULA=TRUE python3 tools/test_server.py start
python3 tools/test_server.py logs
python3 tools/test_server.py install-pack
python3 tools/test_server.py director run
```

Creation defaults to online mode with enforced whitelist. Add trusted accounts through the vanilla console, for example `python3 tools/test_server.py rcon 'whitelist add YourAccount'`. For **local disposable fixtures only**, create with `start --offline-fixtures`; never expose this mode publicly. Existing container modes/settings are not silently replaced. Installing the pack refuses an enabled runtime; pause the owner first.

In another terminal:

```sh
python3 tools/test_server.py director admin doctor
python3 tools/test_server.py director admin chest register 2 64 2
python3 tools/test_server.py director admin start minecraft:iron_ingot 6
python3 tools/test_server.py director admin history
python3 tools/test_server.py director admin pause --reason 'maintenance'
```

Place an **empty single chest** at the chosen coordinates before registration. Adjust the example coordinates to your world. Default managed testing is local/demo generation. The helper reads generated environment files as data; do not shell-source them. For director global options, use the argument separator:

```sh
python3 tools/test_server.py director -- --config /absolute/path/profile.json run
```

`stop`, `restart`, `status`, `logs`, and `rcon <command>` operate only on the isolated server. Ctrl-C gracefully checkpoints/stops the director, not the Minecraft server. Data persists across container stop/start. No volume deletion command is supplied.

## Production installation

1. Obtain the official **26.3** dedicated server and run it with **Java 25**. Verify Mojang's artifact; the server SHA-1 for this release is `33680f5f2ac32864d6d7cf5e56a705fdb3e05f4c`. Do not use `latest`, a snapshot, Paper, or an old NBT schema.
2. Keep `online-mode=true`, enable/enforce the whitelist, and use trusted players. Enable RCON with a long unique password. Publish/firewall RCON only on a private interface or loopback/tunnel. Vanilla has no separate `rcon.ip` property. An RCON password grants arbitrary console authority.
3. Set `pause-when-empty-seconds=0`: heartbeats/load ticks must continue with no players. Review spawn protection; setting it to zero affects the whole server, while operators bypass it. This system does not provide region protection or prevent griefing.
4. Build the generated pack with `python3 tools/build_datapack.py`, then copy `datapack/` to `<world>/datapacks/keeper/`. Pause/checkpoint the owner before installing/upgrading/reloading; run `reload` and check enabled datapacks. Initial load is disabled and preserves journals. The bridge also initializes its objectives if the load tag was deferred by an empty-server pause.
5. Copy `director_config.example.json` to a private configuration location. Set absolute database/socket paths and, optionally, the path of your verified official server jar. A jar hash verifies that configured artifact, not cryptographic attestation of a remote process. Create private state/socket parent directories and restrict secret files to 0600.
6. Supply `RCON_HOST`, `RCON_PORT`, `RCON_PASSWORD`, `MINECRAFT_HOST`, and `MINECRAFT_PORT` in the service environment. Defaults target local vanilla ports 25575/25565. Secrets are environment-only, never JSON or model context.
7. Run `python3 director.py --config /absolute/path/director.json run`, then use the same configuration path for all `admin` calls. Register the empty chest, inspect `doctor`, and perform acceptance drills on a separate world before production use.

Optional AI environment:

```text
LLM_URL=https://openrouter.ai/api/v1/chat/completions
LLM_MODEL=<exact model identifier you choose>
LLM_API_KEY=<provider credential>
DEMO_MODE=0
```

No paid model is selected implicitly. `LLM_URL` and `LLM_MODEL` must both be configured. HTTPS is required except for loopback HTTP providers; redirects and embedded URL credentials are rejected. `DEMO_MODE=1` uses deterministic local objectives.

`deploy/minecraft-ai-director.service` is an optional **systemd user** unit. It assumes this checkout at `~/minecraft_ai_director`, configuration at `~/.config/minecraft-ai-director/director.json`, and a private `director.env` beside it. Adjust paths before installation. The unit uses a restrictive umask and restarts on failure; uncertain operations still require review. It does not create or manage Minecraft.

### Collection-area rules

One registered Overworld single chest; no double chest, adjacent hopper, or nearby hopper minecart. Only vanilla plain stacks of catalog items count; custom components remain untouched. Registration owns only newly added force-load tickets. Unregistration preserves the chest/items and removes only its own ticket. Automated/replaced/invalid chests pause dispatch rather than repair blocks. Operators and other datapacks changing inventories during the critical function are unsupported.

## Players and operators

Players use:

```text
/trigger keeper_quest
/trigger keeper_status
/trigger keeper_claim
/trigger keeper_help
```

Status/claim details are private to the triggering player; the boss bar and quest announcements are community-wide. Claims ask for existing entitlements, not arbitrary reward amounts. Login and normal polling retry pending delivery; the oldest eligible pending entitlement is attempted first. Rewards use one empty slot, never merge into or overwrite existing stacks. Spectators, creative players, configured excluded UUIDs, and players outside the frozen completion set receive no new entitlement.

The owner-only Unix socket accepts typed administration from the same OS UID. One database owner lock is acquired before RCON; separately configured writers targeting the same world are unsupported. Administrative commands require a running owner, including `doctor` and history.

```sh
python3 director.py --config /path/director.json admin --help
python3 director.py --config /path/director.json admin doctor
python3 director.py --config /path/director.json admin rewards <uuid>
python3 director.py --config /path/director.json admin review <operation-id>
python3 director.py --config /path/director.json admin resolve <operation-id> commit --reason 'receipt verified'
python3 director.py --config /path/director.json admin confirm <single-use-token>
```

Also available: `chest register/unregister`, `pause`, `resume`, `start`, confirmation-bound `start-override`, `cancel`, `history`, `reload-config`, and `quarantine`. Use each command's `--help` for exact arguments. `commit`, `abort`, `compensate`, and `void` are explicit resolutions, not automatic retries. Compensation requires typed exact item/count deltas and preserves unrelated inventory. Confirmation tokens are actor/revision-bound and single-use. `resume` cannot bypass unresolved review.

After an **independent player-file restore**, preview `admin quarantine <committed-operation-id> --reason ...`, then confirm. This changes only issuance metadata and pauses dispatch; it never restores historical inventories. A world nonce cannot detect player-only rollback automatically.

## Durability and backups

SQLite schema 2 records immutable candidates, objectives/rewards, recipient UUIDs, operations, receipts/evidence, pending entitlements, confirmation tokens, daily caps, and audit history. Existing schema migration is backed up before alteration. Legacy prototype JSON/state or old spawn settings are rejected; there is no import that fabricates entitlements. Corruption fails closed instead of deleting/resetting the database. Audit/receipt history is not automatically pruned.

Minecraft chunks, player files, command storage, and SQLite are **not one atomic transaction**. The datapack records `RUNNING` before inventory writes. An applied immutable receipt supports safe same-operation queries/replay within the verified session; interrupted/uncertain results enter review. No universal exactly-once guarantee across rollback is claimed.

For a coordinated backup:

1. `admin pause --reason 'coordinated backup'`; retain the reported checkpoint/doctor data.
2. Gracefully stop the owner, then the Minecraft server, so no files are changing.
3. Back up the **entire** world (including player data, command storage, scoreboards/chunks) and the complete SQLite state together. Preserve the shared checkpoint identity and deployment/configuration record. Include SQLite WAL/SHM if present; do not copy only a live main database file.
4. Restore that pair together with both processes stopped, preserving the Minecraft process's filesystem UID/GID and writable permissions (especially `world/session.lock`). Rootless `podman cp` can change ownership: discover the owned test volume with `podman volume inspect --format '{{.Mountpoint}}' mc_ai_director_test_data`, then use `podman unshare chown -R 1000:1000 <that-mountpoint>/world` for this UID/GID-1000 deployment. Never apply it to another server's volume. Start Minecraft, then the owner; inspect `doctor`, receipts/review, and only then explicitly resume.

A mismatched checkpoint/world restore starts paused and quarantines affected issuance. Never infer a refund from historical chest contents, wipe a current Ender Chest, delete receipts to retry, or restore only SQLite/player files as though the pair were atomic. Keep secrets out of backup manifests and restrict backup access.

## Bounds, privacy, and verification

Logical requests are at most 16 KiB, transported in physical frames at most 1400 bytes. Responses/evidence pages are bounded; inventories use full typed evidence rather than lossy projections. A stack above 4 KiB or operation evidence above 1 MiB is refused before consumption. Public projections are at most 6 KiB. Snapshot/receipt pages contain at most 16 players; the hard player/exclusion bound is 128, with default completion recipient cap 20. Exceeding the configured recipient cap refuses completion without trimming recipients or consuming items.

Model context contains at most five candidates, participant count, and twenty pseudonymous allowlisted recent summaries; forty summaries are retained only in memory. Join/leave events derive from snapshots. Optional `log_path` supplies bounded vanilla death/advancement observations; missing logs do not block gameplay. Raw log lines, server identity metadata, inventory evidence, RCON credentials, and command templates are not forwarded. `doctor` reports source health and `event_source.chat_enabled`. Do not point the source at client logs.

Player chat is **opt-in** with JSON `share_chat=true` or `SHARE_CHAT=1`; default collection is off. `share_events=false` suppresses all provider event sharing. Only exact current player identities on public vanilla chat lines are accepted; private messages, console echoes, slash commands, stale/unknown senders, controls, and messages above 256 printable Unicode characters are discarded. Sender labels are salted pseudonyms; known player names and UUID/IP literals in content are redacted. Quoted chat remains untrusted narrative/candidate-selection context, never command authority. Chat is not added to SQLite/audit logs, but vanilla itself still logs public messages. Arbitrary secrets or personal details people type cannot be reliably detected: enabling chat sharing with a hosted provider discloses the remaining message content to that provider. Collection restarts at EOF after startup/rotation/outage; history is not replayed.

Observed on the official 26.3 server/artifact: an unmodified official client shift-clicked a six-iron offering and saw three emeralds in its Ender Chest; exact mixed/custom-stack preservation; stale-state refusal; full/offline payout waits; same-operation replay; 20 online players with 17 filtered frozen recipients; 19-recipient paging; large Unicode request transport; oversized evidence/hopper refusal; watchdog pause; exclusive owner lock; all operator resolutions, metadata-only quarantine, typed compensation, and consumed confirmation tokens. Exact-model HTTP fixtures proved valid AI selection and invalid/429/timeout local fallback, expiry without chest changes, and graceful owner shutdown.

Two unmodified official clients also held the chest open through click, drag, shift-click, hotbar-swap, and double-click actions. A 20-recipient quest consumed six of fourteen plain iron: eight remained across current chest/player inventories, with the custom stack unchanged; the second client viewed its three-emerald reward. Full-inventory pending delivery succeeded after freeing one slot, and repeated claims added nothing. Registration/unregistration preserved contents and pre-existing tickets, while removing a newly owned ticket. All-offline and restored-downtime timers remained unchanged. A complete world/SQLite pair was backed up/restored with a matching checkpoint and no reviews; an isolated mismatched ledger quarantined 26 issuance operations before dispatch without changing the original ledger.

Official 26.3 RCON bytecode revealed its strict one-input-frame-per-read behavior. The transport now waits for the first response before sending its read-only barrier, rather than pipelining requests. A live 602-command/300-lossless-round-trip burst completed on one connection. Connection loss stops the remaining payout batch; only the already-dispatched unknown operation enters review. A postcommit snapshot outage cannot reopen a durably committed chest registration.

The multiplayer load fixtures speak the official protocol but are **not official rendering clients**. Offline fixtures cannot prove authenticated UUID continuity across account rename. A real paid provider, exhaustive multi-viewer click/drag race matrix, every crash/save-window injection, full backup matrix, 128-player load, and long soak are **not certified** by these runs. Section 15 of `docs/project_design.md` retains the production acceptance gates; use a disposable world until those gates are completed for your deployment.

```sh
python3 -m unittest discover -s tests -v
```

Tests cover deterministic state/rules/provider/protocol/event boundaries; they do not replace real vanilla gameplay verification.

## Source map

- `director.py`, `mc_director/cli.py`: owner lifecycle and typed local administration.
- `mc_director/engine.py`, `state.py`, `rules.py`: durable scheduling, inventory intents, review, entitlements and caps.
- `mc_director/bridge.py`, `rcon.py`, `snbt.py`: validated protocol, bounded RCON, lossless typed NBT.
- `mc_director/llm.py`, `events.py`: bounded provider calls and privacy-preserving optional context.
- `tools/build_datapack.py`, `datapack/`: reproducible vanilla pack and synchronous inventory functions.
- `tools/test_server.py`: isolated rootless Podman management and private test environment.
- `director_config.example.json`, `deploy/`: production configuration/service examples.
- `docs/project_design.md`: detailed rules, recovery contract, and production acceptance gates.

Release references: [official 26.3 metadata](https://piston-meta.mojang.com/v1/packages/4fe1aa1ef8da1cb95c5bad1fb98890ca56dd8ca3/26.3.json), [Mojang release notes](https://www.minecraft.net/en-us/article/minecraft-java-edition-26-3).
