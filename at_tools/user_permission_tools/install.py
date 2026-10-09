def install():
	"""Called from AT Tools Settings when User Permission Tools is enabled on this site.

	No-op: this tool used to add custom fields to Employee, but now stores everything on its
	own DocType (User Permission Setting) instead, which needs no install step. Kept (rather
	than removed) so the TOOLS registry entry in tools.py doesn't need to special-case tools
	without an install step.
	"""
	pass
