"""Command plugin discovery via module scanning.

Drop a new .py file (or package with cli.py) into aishell/commands/ that
defines a click.Group, and it auto-registers as a top-level subcommand.

Convention:
    - Single-file command:  commands/myprovider.py  →  exports a click.Group
    - Package command:      commands/mypackage/cli.py  →  exports a click.Group

Skill metadata (optional):
    - Export a SKILL dict alongside the Click group for richer discoverability.
    - Modules without SKILL get a basic entry auto-generated from Click metadata.
    - See docs/plans/SKILLS_PLAN.md for the full convention.
"""

import importlib
import logging
import pkgutil

import click

logger = logging.getLogger(__name__)

# Skill registry: {name: {skill_dict}}
_registry = {}


def _skill_from_click_group(group):
    """Generate minimal SKILL dict from Click group introspection."""
    capabilities = []
    for cmd in group.commands.values():
        if cmd.help:
            # Take first sentence of help text
            first_line = cmd.help.strip().split("\n")[0]
            capabilities.append(first_line)

    return {
        "name": group.name,
        "description": group.help or f"{group.name} commands",
        "capabilities": capabilities,
        "examples": [],
        "tools": [],
    }


def discover_commands(parent_group):
    """Scan aishell/commands/ for Click groups and register them on parent_group.

    Also collects SKILL metadata into _registry for `aishell skills`.
    """
    import aishell.commands as commands_pkg

    for finder, modname, ispkg in pkgutil.iter_modules(commands_pkg.__path__):
        if modname.startswith("_"):
            continue

        try:
            if ispkg:
                module = importlib.import_module(f"aishell.commands.{modname}.cli")
            else:
                module = importlib.import_module(f"aishell.commands.{modname}")

            # Find the first click.Group or click.Command in the module
            cmd = None
            for attr_name in dir(module):
                obj = getattr(module, attr_name)
                if isinstance(obj, click.BaseCommand):
                    parent_group.add_command(obj)
                    cmd = obj
                    logger.debug("Registered command: %s", obj.name)
                    break

            # Collect skill metadata
            if cmd is not None:
                skill = getattr(module, "SKILL", None)
                if skill is not None:
                    _registry[cmd.name] = skill
                elif isinstance(cmd, click.Group):
                    _registry[cmd.name] = _skill_from_click_group(cmd)

        except Exception as e:
            logger.warning("Failed to load command module '%s': %s", modname, e)


def list_skills():
    """Return all registered skills as list of (name, skill_dict)."""
    return sorted(_registry.items())


def get_skill(name):
    """Return skill dict by name, or None if not found."""
    return _registry.get(name)
