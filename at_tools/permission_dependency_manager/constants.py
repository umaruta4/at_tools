"""Shared constants for Permission Dependency Manager."""

# Permission types that can be configured for a dependency (order matters for the UI).
PERMISSION_TYPES = ("read", "select", "create", "write", "delete", "submit", "cancel", "amend")

# Permission Dependency stores the flags as perm_read, perm_select, ... because
# plain "delete" / "submit" / "cancel" fieldnames collide with Document methods.
FIELD_PREFIX = "perm_"

SUBMIT_PERMISSION_TYPES = ("submit", "cancel", "amend")

DEPENDENCY_DOCTYPE = "Permission Dependency"
SETTINGS_DOCTYPE = "Permission Dependency Settings"

DIRECT_LINK = "Direct Link"
CHILD_TABLE_LINK = "Child Table Link"
INDIRECT = "Indirect"
MANUAL = "Manual"

SOURCE_DETECTED = "Detected"
SOURCE_MANUAL = "Manual"

TABLE_FIELDTYPES = ("Table", "Table MultiSelect")

CLASS_MASTER = "Master"
CLASS_TRANSACTION = "Transaction"
CLASS_UNKNOWN = "Unknown"

DEFAULT_RECOMMENDATIONS = {
	CLASS_MASTER: ("read", "select"),
	CLASS_TRANSACTION: ("read",),
	CLASS_UNKNOWN: ("read",),
}

STATUS_SATISFIED = "satisfied"
STATUS_MISSING = "missing"
STATUS_PARTIAL = "partial"
STATUS_DISABLED = "disabled"

# Same list the native Role Permission Manager refuses to manage.
NOT_ALLOWED_DOCTYPES = ("DocType", "Patch Log", "Module Def")

ADMIN_ROLE = "Administrator"
# Roles the native manager hides from everyone except the Administrator user.
AUTOMATIC_ROLES = ("Guest", "All", "Desk User", "Administrator")

MANAGER_ROLE = "System Manager"
SAVEPOINT = "pdm_apply_dependencies"
