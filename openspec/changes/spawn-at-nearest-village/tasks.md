# Tasks

## 1. Document regeneration behavior

- [x] 1.1 Update `README.md` with the Java 26.3 post-generation procedure: preserve the recorded original spawn, locate each supported village type, choose the nearest horizontal result, inspect a safe surface, set world spawn, flush, and verify persistence. Keep Director quest coordinates explicitly separate.
- [x] 1.2 Update `AGENTS.md` safety guidance so future regeneration work treats nearest-village spawn derivation as a required acceptance step and does not guess coordinates or mutate unrelated worlds.

## 2. Apply and verify the current live world

- [x] 2.1 Set the designated live world's spawn to the verified taiga-village surface at `[112, 72, 32]` with private RCON and flush the world.
- [x] 2.2 Verify persisted `level.dat` spawn metadata, overworld dimension, live service state, and zero unintended players.

## 3. Validate the contract

- [x] 3.1 Run OpenSpec validation and the existing deterministic test suite; confirm no settlement or village-generation behavior changed.
- [x] 3.2 Smoke the changed live-world surface with RCON/metadata evidence and record that client rendering remains a separate visual check, not proof supplied by mocked commands.
