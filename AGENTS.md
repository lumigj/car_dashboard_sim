# Repository Instructions

## Coding Preferences

- Always write simpler code. Do not consider too many edge cases unless the user asks for them.
- Follow the "let it crash" principle: do not catch non-business exceptions, and do not add non-business null checks.
- Do not add dependency-install boilerplate.
- Do not wrap imports in `try`/`except ImportError` only to print setup or `pip install` instructions.
- Do not print messages about missing packages or how to install them unless the user explicitly asks for that behavior.
- Assume the developer will manage local environment and dependencies.
- Prefer failing normally over adding defensive setup guidance around imports.
- Treat user-authored changes as intentional. If code differs from a previous AI edit, do not change it back unless the user explicitly asks for that reversal.

## Review guidelines

- Don't log PII.

## Scope

- These rules apply across the whole repository unless a more specific nested `AGENTS.md` overrides them.
