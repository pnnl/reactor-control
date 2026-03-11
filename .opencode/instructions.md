# Agent Instructions for reactor-control Project

version: 1.0
last_updated: 2025-01-20
changelog:
  - 1.0: Initial creation of core rules for reactor-control project.

---

## Purpose

This codebase exists to provide a clear, reproducible, and extensible software platform for automated reactor experimentation and emissions‑control research. Its primary goal is to enable scientists and engineers to design, execute, and analyze experiments with precision, safety, and long‑term maintainability.

The system emphasizes transparency, modularity, and deterministic behavior. All components — from hardware‑control routines to data‑processing pipelines — must be designed so that collaborators can understand, reproduce, and extend the work years into the future.

Every contribution to this project should reinforce these principles: clarity of intent, scientific rigor, operational safety, and architectural stability. All agents, tools, and workflows must align with this overarching mission.

---

These are the non-negotiable, global rules for working on this project. They must be followed at all times, by all agents.

## 1. Core Mandate: Phased Development and Hardware Safety

Your primary objective is to assist in the phased development of the reactor-control codebase for automated reactor experimentation.

- **Workspace:** Work in the main project directory: `C:\Users\labuser\reactor_control`
- **Hardware Safety:** Device configuration (`src/core/config.py`) controls COM ports, baud rates, and timeouts. Changes to this file directly affect physical hardware connections. Exercise extreme caution.

## 2. Rule Priority & Overrides

### Rule Priority (Highest to Lowest)

1. Safety rules in this file (`instructions.md`).
2. Current phase constraints in `docs/project_status.md`.
3. Active agent instructions (`.opencode/agents/*.md`).
4. Agent tool restrictions enforced by `opencode.json`.
5. Code conventions in `.opencode/conventions.md`.

### Emergency Override

If the user explicitly states `[OVERRIDE: <rule>]`, you may proceed but MUST log the override in `.opencode/memory.md` with a justification.

## 3. The Phase Plan is Law

All work must align with `docs/project_status.md`.

- **Check Your Phase:** Before taking any action, read `docs/project_status.md` to confirm the current active phase.
- **Do Not Jump Ahead:** You are strictly forbidden from starting work on a new phase without explicit user permission. If a request seems to cross a phase boundary, you must ask for confirmation.

## 4. Agent Activation Protocol

This project uses OpenCode's native agent system defined in `opencode.json`.

### Primary Agents (Switch with Tab)

| Agent | Purpose |
|-------|---------|
| `coder` | Implements code features and device drivers |
| `architect` | Designs systems and plans major features (read-only) |

### Subagents (Invoke with @mention)

| Agent | Purpose |
|-------|---------|
| `@reviewer` | Reviews code quality, correctness, and conventions |
| `@debugger` | Investigates errors and identifies root causes |
| `@validator` | Validates scientific/numerical changes |
| `@historian` | Updates memory and foundations |

### Switching Rules

- **To switch primary agents:** Ask user to switch manually
- **To invoke subagents:** Use `@agent_name` in your message
- **Tool restrictions are enforced:** Each agent's `tools` block in `opencode.json` determines what actions permitted. Do not attempt to circumvent these restrictions.

## 5. The "Think-First" Protocol

Before proposing any code modification, you MUST use a thinking block to verify your logic.

- **Internal Monologue:** In this block, use diverse reasoning throughout your proposed action.
- **Verification Checklist:** Your monologue MUST check your plan against the rule priority list.

## 6. The "Read-First" Protocol

- **Read Before Writing:** Always use the read tool on a file before using write or edit.
- **Understand the Hardware:** When implementing device drivers, read the relevant hardware manuals in `hardware_manuals/` and study existing device implementations in `src/devices/`.
- **Check Configuration:** Before modifying device-related code, verify the current settings in `src/core/config.py`.

## 7. Critical Code Safety & Definition of Done

- **Device Code (`src/devices/`):** Your work is not done until you have:
  1. Inherited from appropriate base class (`SerialDevice` or `CommunicationProtocol`)
  2. Implemented all required abstract methods
  3. Added comprehensive docstrings
  4. Created hardware tests in `tests/`
  5. Updated `devices/__init__.py` `__all__` list
  6. Verified protocol against hardware manuals in `hardware_manuals/`
  7. **Note:** Do NOT run hardware tests without explicit user confirmation

- **Configuration Changes (`src/core/config.py`):** Your work is not done until you have:
  1. Verified the hardware connection details (COM ports, baud rates)
  2. Checked that all existing device implementations still work
  3. Updated documentation in `docs/` if structure changes

- **Operations/Experiments Code:** Your work is not done until you have explicitly confirmed that error handling is robust and fails safely (does not leave equipment in unsafe state).

## 8. Context Management

- **Context Sweep:** When you start a new task, check the current directory and all parent directories for `.agent.md` or `.spec.md` files.

## 9. Documentation Updates

Follow the development workflow in `docs/development_workflow.md`:

- **After completing a major feature or phase:** Update `docs/project_status.md`
- **When adding new devices:** Update `docs/project_status.md` and `docs/directory_structure.md`
- **When changing configuration structure:** Update `docs/directory_structure.md`

## 10. Formatting and Communication Standards

- **Use LaTeX** for complex mathematical formulas.
- **Use Markdown tables** when comparing old vs. new logic or device protocols.

## 11. Compliance & Auditing

### Compliance Checkpoint

At the end of any code-modifying action, you must output:
- [ ] Phase verified: [Phase X]
- [ ] Agent active: [Name]
- [ ] Think-First block used: Yes/No
- [ ] Device protocol verified against hardware_manuals/: Yes/No

### Violation Reporting

If you detect a rule violation (by yourself or in existing code), log it in `.opencode/memory.md` under a `## Violations` section with:
- Rule violated
- Context
- Suggested remediation

## 12. Device-Specific Guidelines

When implementing or modifying device drivers:

1. **Protocol Validation:** Always verify communication commands against the device manual in `hardware_manuals/`
2. **Error Handling:** Device communication must fail gracefully. Always return `None` or `False` on errors, never raise exceptions that could crash the control system
3. **Timeouts:** Respect timeout settings from `config.py`. Never use infinite waits
4. **Connection State:** Always track connection state (`self.is_connected`) and validate before sending commands
5. **Logging:** Use instance-level loggers with class name for easy debugging
6. **Testing:** Create tests that verify basic communication (connect, identify, read, write) before implementing complex operations
