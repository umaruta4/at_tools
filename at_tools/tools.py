import importlib
import json
import os

import frappe

# Registry of all tools.
# install: function called when the tool is activated on a site.
# hooks: module with a HOOKS variable (doc_events, doctype_js, etc.), collected into the generated hooks data file.
TOOLS = {
	"User Permission Tools": {
		"install": "at_tools.user_permission_tools.install.install",
		"hooks": "at_tools.user_permission_tools.hooks",
	},
	"Role Permission Enhancer Tools": {
		"install": "at_tools.role_permission_enhancer_tools.install.install",
		"hooks": "at_tools.role_permission_enhancer_tools.hooks",
	},
}


def get_generated_hooks_path():
	"""Location of the Generate Hooks output file.

	Deliberately placed under sites/.at_tools/, NOT inside the app package folder, so that:
	- it never gets committed to the at_tools repo (sites/ is entirely outside this app's repo,
	  so no .gitignore entry is needed here).
	- it persists across deploys, since sites/ is the bench data directory that is kept intact
	  while apps/ gets replaced by git pull/deploy.
	"""
	return os.path.join(frappe.utils.get_bench_path(), "sites", ".at_tools", "generated_hooks.json")


def is_tool_enabled(tool):
	settings = frappe.get_single("AT Tools Settings")
	return any(row.tool == tool and row.enabled for row in settings.tools)


def _as_list(value):
	return value if isinstance(value, list) else [value]


def _merge(target, source):
	"""Recursively merge hooks dicts. Colliding values are merged into a deduplicated list."""
	for key, value in source.items():
		if isinstance(value, dict):
			_merge(target.setdefault(key, {}), value)
		elif key not in target:
			target[key] = value
		else:
			merged = list(dict.fromkeys(_as_list(target[key]) + _as_list(value)))
			target[key] = merged[0] if len(merged) == 1 else merged


def collect_hooks():
	"""Merge HOOKS only from tools that are enabled on this site."""
	merged = {}
	for tool, config in TOOLS.items():
		if not config.get("hooks") or not is_tool_enabled(tool):
			continue

		_merge(merged, importlib.import_module(config["hooks"]).HOOKS)

	return merged


def generate_hooks():
	"""Write the generated hooks data file (JSON). Called from the button in AT Tools Settings."""
	path = get_generated_hooks_path()
	os.makedirs(os.path.dirname(path), exist_ok=True)
	with open(path, "w") as f:
		json.dump(collect_hooks(), f, indent="\t", sort_keys=True)
		f.write("\n")
	return path


def load_generated_hooks():
	"""Read the generated hooks data file. Called from at_tools/hooks.py at startup."""
	path = get_generated_hooks_path()
	try:
		with open(path) as f:
			return json.load(f)
	except (OSError, ValueError):
		# Never generated yet, or the file is corrupted.
		return {}
