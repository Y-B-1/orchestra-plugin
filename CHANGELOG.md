# Changelog

Release 2.0.0 is described in docs/RELEASE-NOTES-2.0.0.md.

## Unreleased (2.0.1)

- Claude `PreToolUse` matcher now includes `Agent` and `Task` (`Bash|Edit|Write|MultiEdit|Agent|Task`), so workers cannot delegate in Claude Code. This supersedes the 2.0.0 note that the matcher covered only `Bash|Edit|Write|MultiEdit`.
- Test: `_MOD_TOOLS` in `orchestra_core/hooks.py` must equal `GUARDED` in `hooks/mod/orchestra.ts`, so the two lists cannot drift apart.
