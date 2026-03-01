# Multi-Agent Codenames - Current State and Action Plan

## Scope

This document is the new detailed reference for project cleanup and organization.
It intentionally does not modify the existing `README.md` or `docs/README.md`.

## What Has Been Implemented Now

- Added `config/game_config.py` as the central configuration source.
- Set the default model to `gemini-3-flash-preview`.
- Wired defaults for CLI and Web setup paths.
- Kept evaluation wiring postponed as the last phase.

## Current Project Reality (Code-First View)

- Main runtime entry is `main.py` with three modes: `server`, `cli`, `eval`.
- Web mode is implemented via FastAPI in `server/app.py` and `server/routes.py`.
- CLI mode is implemented in `cli/game_cli.py`.
- Core game orchestration is in `game/game_manager.py`.
- AI roles are implemented in:
  - `agents/card_creator.py`
  - `agents/spymaster.py`
  - `agents/operative.py`

## Key Gaps and Inconsistencies

- Docs and implementation are not fully aligned in several places.
- Some runtime defaults are now unified through `config/game_config.py`, but model wiring is still partial.
- Evaluation path is intentionally postponed to the final step.

## New Config File Structure

File: `config/game_config.py`

Current exported sections:

- `MODELS`
  - `default = "gemini-3-flash-preview"`
  - `available`
  - `by_agent` (future optional specialization)
- `GAME_DEFAULTS`
  - `board_size`, `difficulty`, `language`, `category`
- `PLAYER_DEFAULTS`
  - `human_team`, `human_role`
- `AI_DEFAULTS`
  - `model`, `temperature_overrides`
- `SERVER_DEFAULTS`
  - `host`, `port`, `debug`
- `CLI_DEFAULTS`
  - `mode`, `lang`, `size`, `difficulty`, `team`, `role`, `category`
- `EVAL_DEFAULTS`
  - `mode`, `games`, `size`, `difficulty`, `lang`

## Current Config Consumers (Wired)

These paths now consume defaults from `config/game_config.py`.

| File | Should read from `config/game_config.py` |
|---|---|
| `main.py` | `SERVER_DEFAULTS.port`, `CLI_DEFAULTS.*`, `EVAL_DEFAULTS.games` |
| `server/routes.py` | `GAME_DEFAULTS.*`, `PLAYER_DEFAULTS.*` |
| `static/app.js` | Uses `/api/config/defaults` response to prefill setup UI |

## Commands Pulling Defaults from Config (Current)

- `uv run python main.py --mode server`
  - Uses default port from `SERVER_DEFAULTS`.
- `uv run python main.py --mode cli`
  - Uses defaults from `CLI_DEFAULTS` when flags are omitted.
- `uv run python main.py --mode eval --games N`
  - Uses `EVAL_DEFAULTS.games` when omitted.
  - Full evaluation refactor remains the last integration step.

## Next Steps (Ordered)

1. Keep `config/game_config.py` as the authoritative defaults document.
2. Extend model-default wiring into game manager and agent constructors.
3. Add minimal tests for defaults loading and override precedence.
4. Leave evaluation integration (`evaluation/evaluator.py`) to the last phase.

## Quality Baseline Proposal (Later)

After config adoption is stable, add a minimum quality baseline:

- `tests/` for smoke tests of game creation and turn flow.
- CI workflow to run tests and static checks on push/PR.
- `.pre-commit-config.yaml` for formatting and linting before commits.

## Notes

- Existing old documentation remains untouched as requested.
- This file is the detailed source for cleanup decisions and rollout order.
