# Repository Instructions

## Coding Preferences

- Always write simpler code. Do not consider too many edge cases unless the user asks for them.
- Do not add dependency-install boilerplate.
- Do not wrap imports in `try`/`except ImportError` only to print setup or `pip install` instructions.
- Do not print messages about missing packages or how to install them unless the user explicitly asks for that behavior.
- Assume the developer will manage local environment and dependencies.
- Prefer failing normally over adding defensive setup guidance around imports.

## Scope

- These rules apply across the whole repository unless a more specific nested `AGENTS.md` overrides them.
