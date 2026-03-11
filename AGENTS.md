# AGENTS.md

## Project Overview
This project is a Python-based control system for a lab reactor.

## Key Documentation

### Project Documentation (Read these first to understand the project)
- **Current Status & Next Steps:** `docs/project_status.md`
- **System Architecture:** `docs/architecture_overview.md`
- **Directory Structure:** `docs/directory_structure.md`
- **Development Workflow:** `docs/development_workflow.md`

### Agent-Specific Documentation (Read before working)
- **Agent Instructions:** `.opencode/instructions.md` - Core rules, phase constraints, safety protocols
- **Coding Conventions:** `.opencode/conventions.md` - Naming, formatting, type hints, docstrings
- **Development Environment:** `.opencode/environment.md` - Project setup, paths, dependencies, tools

## Important Locations & Commands
- **Source Code:** The main package is located in `src/`.
- **Device Configuration:** All device settings (COM ports, baud rates) are in `src/core/config.py`. Modify this file for hardware changes.
- **Hardware Specs:** Detailed hardware manuals and protocols are in the `hardware_manuals/` directory.

---

## Hardware Testing Safety

**CRITICAL: Do not run any test code or scripts that communicate with hardware unless user explicitly confirms.**

This system controls physical instrumentation (mass flow controllers, thermocouples, etc.). Running tests may send commands to hardware and affect ongoing experiments or equipment states.

- Always ask for explicit confirmation before running: `python tests/test_*.py`
- When reviewing code, do not suggest running hardware tests
- When validating code, do not run tests without confirmation
- Default to "dry-run" or mock analysis when possible

---

## Agent System Overview

This project uses OpenCode's native agent system. Agents are defined in `opencode.json` and their detailed instructions live in `.opencode/agents/*.md`.

### Primary Agents (Tab to switch)
| Agent | Purpose | Can Edit Files? |
|-------|---------|-----------------|
| `coder` | Implements code features and device drivers | ✅ Yes |
| `architect` | Designs systems and plans major features | ❌ No (read-only) |

### Subagents (Invoke with @mention)
| Agent | Purpose | Can Edit Files? |
|-------|---------|-----------------|
| `@reviewer` | Reviews code for quality, correctness, and conventions | ❌ No |
| `@debugger` | Investigates errors and identifies root causes | ❌ No (bash only) |
| `@validator` | Validates scientific/numerical code changes | ❌ No (bash only) |
| `@historian` | Summarizes learnings and updates memory/foundations | ✅ Yes (memory files only) |

---

## Agent Operational Protocol

### On Session Start
1. Read `.opencode/memory.md` to load short-term memory from previous session.
2. Read `docs/project_status.md` to understand current phase and its limitations.
3. Identify which **primary agent** is appropriate for the current task.

### Before Any Action
- Adhere to the rules in `.opencode/instructions.md`.
- Follow the conventions in `.opencode/conventions.md`.
- Respect the `tools` restrictions defined in `opencode.json` for your current agent.

### For Specific Information
- **Coding style, naming, formatting:** `.opencode/conventions.md`
- **Build commands, environment, data paths:** `.opencode/environment.md`

---

## Trigger-Based Agent Selection

| Situation | Action |
|-----------|--------|
| **Planning/Designing** | Switch to `architect` agent (Tab) |
| **Writing/Implementing Code** | Switch to `coder` agent (Tab) |
| **After Code Changes** | Invoke `@reviewer` for review |
| **Encountering Errors** | Invoke `@debugger` for root cause analysis |
| **Modifying Scientific/Numerical Code** | Invoke `@validator` before and after changes |
| **End of Phase** | Invoke `@historian` to update `.opencode/memory.md` |

---

## Workflow Guidelines

1. **Modify existing code:** Follow best practices and conventions.
2. **Add new features:** Create new files with descriptive names.
3. **Add new devices:** Inherit from base classes, verify against hardware manuals.
4. **Test changes:** Run relevant test scripts in `tests/`.
5. **Document:** Add comprehensive docstrings and update `docs/` as appropriate.
6. **Safety:** Always consider hardware safety implications of all changes.

---

## Agent Capabilities Reference

Detailed persona instructions for each agent are located in:
- `.opencode/agents/coder.md`
- `.opencode/agents/architect.md`
- `.opencode/agents/reviewer.md`
- `.opencode/agents/debugger.md`
- `.opencode/agents/validator.md`
- `.opencode/agents/historian.md`

These files define **behavioral traits** and **negative constraints** for each agent. The `opencode.json` file **enforces** tool restrictions.

---

## Session Closing Checklist

Before ending a work session, ensure the following documentation is updated:

1. **Required updates**
   - `docs/project_status.md`
   - `.opencode/memory.md`
2. **If impacted by the session**
   - `docs/directory_structure.md`
   - `.opencode/foundations.md`
   - Other relevant `.opencode/*.md` files
3. **Context Management**
   - Prune the *.md files if there is extraneous information about Phases that have been completed
