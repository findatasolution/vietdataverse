# CODEX.md

This file provides repository-specific guidance for Codex. Read it together with `AGENTS.md`; scoped `AGENTS.md` files take precedence inside their directories.

## Communication

Trao đổi với người dùng bằng tiếng Việt. Giữ code, comment và commit message bằng tiếng Anh theo convention hiện có.

## Documentation Close-out (Required)

Documentation is part of the definition of done. Before marking any task complete:

1. Identify every document affected by the change, including `BACKLOG.md`, `CLAUDE.md`, `CODEX.md`, scoped `CLAUDE.md` / `AGENTS.md`, README/API docs, runbooks, architecture notes, migration notes, and `.env.example` when applicable.
2. Update status, behavior, paths, commands, schemas, access rules, deployment state, and limitations in the same task. Documentation must describe the resulting system, not the state before the change.
3. Mark backlog items complete only after implementation and required verification succeed. If production deployment remains pending or blocked, record that state explicitly.
4. Replace stale statements instead of adding contradictory notes. Edit source documents rather than generated outputs, then rebuild generated documentation when required.
5. In the final handoff, name the documentation files updated. If no documentation content needed changing, explicitly state that the relevant documents were reviewed and remain accurate.

Do not close a task while related documentation is known to be stale.

## Core Working Rules

- Never display or commit values from `.env`, connection strings, API keys, passwords, or tokens.
- Read `BACKLOG.md` when implementing a referenced backlog item and use it as acceptance criteria.
- Read `.claude/rules/DESIGN.md` before UI/CSS/HTML changes.
- Treat `fe/partials/` as the source of truth and regenerate `fe/index.html` with `python3 fe/build.py` after partial changes.
- Verify changes in proportion to risk and distinguish code pushed, CI passed, and production deployment verified as separate states.
