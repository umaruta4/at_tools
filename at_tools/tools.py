import importlib
import json
import os

import frappe

# Registry semua tool.
# install: fungsi yang dipanggil saat tool diaktifkan di site.
# hooks: modul yang punya variabel HOOKS (doc_events, doctype_js, dll), dikumpulkan ke file data generated hooks.
TOOLS = {
	"User Permission Tools": {
		"install": "at_tools.user_permission_tools.install.install",
		"hooks": "at_tools.user_permission_tools.hooks",
	},
	"Role Permission Enhancer Tools": {},
}


def get_generated_hooks_path():
	"""Lokasi file hasil Generate Hooks.

	Sengaja ditaruh di sites/.at_tools/, BUKAN di folder package app, supaya:
	- tidak ikut ke-commit ke repo at_tools (sites/ di luar repo app sama sekali, jadi tidak
	  butuh .gitignore apa pun di sini).
	- persisten lintas deploy, karena sites/ adalah direktori data bench yang dipertahankan
	  saat apps/ di-replace oleh git pull/deploy.
	"""
	return os.path.join(frappe.utils.get_bench_path(), "sites", ".at_tools", "generated_hooks.json")


def is_tool_enabled(tool):
	settings = frappe.get_single("AT Tools Settings")
	return any(row.tool == tool and row.enabled for row in settings.tools)


def _as_list(value):
	return value if isinstance(value, list) else [value]


def _merge(target, source):
	"""Gabungkan dict hooks secara rekursif. Nilai yang bentrok digabung jadi list tanpa duplikat."""
	for key, value in source.items():
		if isinstance(value, dict):
			_merge(target.setdefault(key, {}), value)
		elif key not in target:
			target[key] = value
		else:
			merged = list(dict.fromkeys(_as_list(target[key]) + _as_list(value)))
			target[key] = merged[0] if len(merged) == 1 else merged


def collect_hooks():
	"""Gabungkan HOOKS dari tool yang aktif di site ini saja."""
	merged = {}
	for tool, config in TOOLS.items():
		if not config.get("hooks") or not is_tool_enabled(tool):
			continue

		_merge(merged, importlib.import_module(config["hooks"]).HOOKS)

	return merged


def generate_hooks():
	"""Tulis file data generated hooks (JSON). Dipanggil dari tombol di AT Tools Settings."""
	path = get_generated_hooks_path()
	os.makedirs(os.path.dirname(path), exist_ok=True)
	with open(path, "w") as f:
		json.dump(collect_hooks(), f, indent="\t", sort_keys=True)
		f.write("\n")
	return path


def load_generated_hooks():
	"""Baca file data generated hooks. Dipanggil dari at_tools/hooks.py saat startup."""
	path = get_generated_hooks_path()
	try:
		with open(path) as f:
			return json.load(f)
	except (OSError, ValueError):
		# Belum pernah di-generate, atau file rusak.
		return {}
