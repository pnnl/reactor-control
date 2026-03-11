"""Utilities for managing MG2000 setup configuration."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


logger = logging.getLogger(__name__)

__all__ = ["ToolWebAddinConfig", "ensure_toolweb_addin"]


@dataclass(frozen=True)
class ToolWebAddinConfig:
    """Configuration for the ToolWEB add-in enforcement.

    Attributes:
        ini_path: Path to MG2000_SETUP.INI
        mgrcp_path: Path to MG2000_last_used_recipe.MGRCP
        addins_dir: Path to the MG2000 addins directory
        addin_name: Name of the add-in entry (e.g., TOOLWEB)
        addin_file: Expected filename for the add-in LLB
    """

    ini_path: Path
    mgrcp_path: Path
    addins_dir: Path
    addin_name: str = "TOOLWEB"
    addin_file: str = "TOOLWEB.LLB"


def ensure_toolweb_addin(config: ToolWebAddinConfig) -> bool:
    """Ensure ToolWEB add-in is present in MG2000 config files.

    This function updates both MG2000_SETUP.INI and MG2000_last_used_recipe.MGRCP
    to include TOOLWEB in the addIns list and configure settings.
    It should be run only when MG2000 is not running, since MG2000
    overwrites these files on exit.

    Args:
        config: ToolWebAddinConfig describing INI and add-in locations

    Returns:
        True if TOOLWEB is present or successfully added, False otherwise
    """
    if not isinstance(config, ToolWebAddinConfig):
        logger.error("config must be a ToolWebAddinConfig")
        return False
    if not config.addin_name or not isinstance(config.addin_name, str):
        logger.error("addin_name must be a non-empty string")
        return False
    if not config.addin_file or not isinstance(config.addin_file, str):
        logger.error("addin_file must be a non-empty string")
        return False
    if not config.ini_path.exists():
        logger.error(f"INI file not found: {config.ini_path}")
        return False
    if not config.addins_dir.exists():
        logger.error(f"Addins directory not found: {config.addins_dir}")
        return False
    addin_path = config.addins_dir / config.addin_file
    if not addin_path.exists():
        logger.error(f"ToolWEB add-in not found: {addin_path}")
        return False

    # Update MG2000_SETUP.INI
    try:
        ini_lines = config.ini_path.read_text(
            encoding="utf-8", errors="replace"
        ).splitlines()
    except (OSError, UnicodeError) as exc:
        logger.error(f"Failed to read INI file: {exc}")
        return False

    updated_ini_lines, ini_changed, valid = _ensure_toolweb_in_lines(
        ini_lines, config.addin_name
    )
    if not valid:
        return False
    if ini_changed:
        try:
            config.ini_path.write_text(
                "\n".join(updated_ini_lines) + "\n", encoding="utf-8"
            )
            logger.info("Updated MG2000_SETUP.INI to include TOOLWEB add-in")
        except (OSError, UnicodeError) as exc:
            logger.error(f"Failed to write INI file: {exc}")
            return False

    # Update MG2000_last_used_recipe.MGRCP if it exists
    if config.mgrcp_path.exists():
        try:
            mgrcp_lines = config.mgrcp_path.read_text(
                encoding="utf-8", errors="replace"
            ).splitlines()
        except (OSError, UnicodeError) as exc:
            logger.error(f"Failed to read MGRCP file: {exc}")
            return False

        updated_mgrcp_lines, mgrcp_changed, valid = _ensure_toolweb_in_mgrcp(
            mgrcp_lines
        )
        if valid and mgrcp_changed:
            try:
                config.mgrcp_path.write_text(
                    "\n".join(updated_mgrcp_lines) + "\n", encoding="utf-8"
                )
                logger.info("Updated MG2000_last_used_recipe.MGRCP to include TOOLWEB")
            except (OSError, UnicodeError) as exc:
                logger.error(f"Failed to write MGRCP file: {exc}")
                return False
    else:
        logger.warning(f"MGRCP file not found: {config.mgrcp_path}, skipping")

    return True


def _ensure_toolweb_in_mgrcp(
    lines: list[str], addin_name: str = "TOOLWEB"
) -> tuple[list[str], bool, bool]:
    """Ensure TOOLWEB is configured in MGRCP file.

    Also adds [ToolWeb config] section if not present.

    Args:
        lines: Raw MGRCP file lines
        addin_name: Add-in name to ensure

    Returns:
        Tuple of (updated_lines, changed, valid)
    """
    has_toolweb_section = False
    has_toolweb_in_addins = False
    has_storeprn_true = False
    recipe_index = -1

    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped.lower() == "[toolweb config]":
            has_toolweb_section = True
        elif (
            stripped.lower().startswith("addins ")
            and addin_name.lower() in stripped.lower()
        ):
            has_toolweb_in_addins = True
        elif stripped.lower().startswith("storeprn "):
            if "true" in stripped.lower():
                has_storeprn_true = True
            else:
                recipe_index = idx  # Will fix later
        elif stripped.lower().startswith("recipe ") and '"' in stripped:
            recipe_index = idx

    changed = False

    # Add [ToolWeb config] section if not present
    if not has_toolweb_section:
        # Find a good place to insert - after [DiagsLogging CFG] or at start
        insert_idx = 0
        for idx, line in enumerate(lines):
            if line.strip().lower() == "[diagslogging cfg]":
                insert_idx = idx + 1
                break

        toolweb_section = [
            "[ToolWeb config]",
            "id offset = 0",
            "nrToReport = 10",
            "idle value = 1",
            'idle string = "NaN"',
            "keepConnectionAlive = FALSE",
            "IP-port = 80",
            "",
        ]
        for i, new_line in enumerate(toolweb_section):
            lines.insert(insert_idx + i, new_line)
        changed = True
        logger.info("Added [ToolWeb config] section to MGRCP")

    # Add TOOLWEB to addIns if not present
    if not has_toolweb_in_addins:
        # Find addIns section and add TOOLWEB
        in_general = False
        addins_end_idx = -1
        for idx, line in enumerate(lines):
            stripped = line.strip()
            if stripped.upper() == "[GENERAL]":
                in_general = True
            elif (
                in_general
                and stripped.upper() == '--------------------------END = "GENERAL"'
            ):
                addins_end_idx = idx
                break

        if addins_end_idx >= 0:
            lines.insert(addins_end_idx, f'addIns 3 = "{addin_name}"')
            changed = True
            logger.info("Added TOOLWEB to addIns in MGRCP")

    # Set storePrn = TRUE
    if not has_storeprn_true:
        # Find and update storePrn line
        for idx, line in enumerate(lines):
            if line.strip().lower().startswith("storeprn "):
                lines[idx] = 'storePrn = "TRUE"'
                changed = True
                logger.info("Set storePrn = TRUE in MGRCP")
                break
        else:
            # Add storePrn if not found
            for idx, line in enumerate(lines):
                if line.strip().upper().startswith("[GENERAL]"):
                    # Find the next line after [GENERAL]
                    insert_idx = idx + 1
                    while insert_idx < len(lines) and "=" not in lines[insert_idx]:
                        insert_idx += 1
                    lines.insert(insert_idx, 'storePrn = "TRUE"')
                    changed = True
                    logger.info("Added storePrn = TRUE to MGRCP")
                    break

    return lines, changed, True


def _ensure_toolweb_in_lines(
    lines: list[str], addin_name: str
) -> tuple[list[str], bool, bool]:
    """Ensure TOOLWEB entry exists in the [GENERAL] addIns list.

    Also clears the recipe field to ensure ToolWEB is recognized by MG2000.

    Args:
        lines: Raw INI lines
        addin_name: Add-in name to ensure

    Returns:
        Tuple of (updated_lines, changed, valid)
    """
    in_general = False
    addins: list[tuple[int, str]] = []
    size_index: Optional[int] = None
    last_addin_index: Optional[int] = None
    recipe_index: int = -1
    storeprn_index: int = -1

    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            if stripped.upper() == "[GENERAL]":
                in_general = True
                continue
            if in_general:
                break
        if in_general:
            if stripped.lower().startswith("addins.<size"):
                size_index = idx
            elif stripped.lower().startswith("addins "):
                parts = stripped.split("=", 1)
                if len(parts) == 2:
                    key = parts[0].strip()
                    value = parts[1].strip().strip('"')
                    try:
                        index = int(key.split()[1])
                    except (IndexError, ValueError):
                        continue
                    addins.append((index, value))
                    last_addin_index = idx
            elif stripped.lower().startswith("recipe "):
                recipe_index = idx
            elif stripped.lower().startswith("storeprn "):
                storeprn_index = idx

    if not isinstance(addin_name, str) or not addin_name:
        logger.error("addin_name must be a non-empty string")
        return lines, False, False
    if last_addin_index is None:
        logger.error("[GENERAL] section or addIns entries not found in INI")
        return lines, False, False

    addin_values = [value.upper() for _, value in addins]
    if addin_name.upper() in addin_values:
        changed = False
        if recipe_index >= 0 and _recipe_has_value(lines, recipe_index):
            lines[recipe_index] = 'recipe = ""'
            logger.info("Cleared recipe field for ToolWEB compatibility")
            changed = True
        if storeprn_index >= 0 and not _storeprn_is_true(lines, storeprn_index):
            lines[storeprn_index] = 'storePrn = "TRUE"'
            logger.info("Set storePrn to TRUE for ToolWEB compatibility")
            changed = True
        return lines, changed, True

    next_index = max((index for index, _ in addins), default=-1) + 1
    insert_line = f'addIns {next_index} = "{addin_name}"'

    lines.insert(last_addin_index + 1, insert_line)

    if size_index is not None:
        size_line = lines[size_index]
        size_parts = size_line.split("=", 1)
        if len(size_parts) == 2:
            try:
                size_value = int(size_parts[1].strip().strip('"'))
            except ValueError:
                size_value = len(addins)
            size_value += 1
            lines[size_index] = f'addIns.<size(s)> = "{size_value}"'

    if recipe_index >= 0 and _recipe_has_value(lines, recipe_index):
        lines[recipe_index] = 'recipe = ""'
        logger.info("Cleared recipe field for ToolWEB compatibility")

    if storeprn_index >= 0 and not _storeprn_is_true(lines, storeprn_index):
        lines[storeprn_index] = 'storePrn = "TRUE"'
        logger.info("Set storePrn to TRUE for ToolWEB compatibility")

    return lines, True, True


def _recipe_has_value(lines: list[str], recipe_index: int) -> bool:
    """Check if recipe line has a non-empty value."""
    if recipe_index < 0 or recipe_index >= len(lines):
        return False
    line = lines[recipe_index].strip()
    if not line.lower().startswith("recipe "):
        return False
    parts = line.split("=", 1)
    if len(parts) != 2:
        return False
    value = parts[1].strip().strip('"')
    return value != ""


def _storeprn_is_true(lines: list[str], storeprn_index: int) -> bool:
    """Check if storePrn is set to TRUE."""
    if storeprn_index < 0 or storeprn_index >= len(lines):
        return False
    line = lines[storeprn_index].strip()
    if not line.lower().startswith("storeprn "):
        return False
    parts = line.split("=", 1)
    if len(parts) != 2:
        return False
    value = parts[1].strip().strip('"')
    return value.upper() == "TRUE"
