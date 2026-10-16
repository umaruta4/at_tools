"""Whitelisted endpoints used by the Role Permission Manager extension."""

import frappe
from frappe import _

from at_tools.permission_dependency_manager.constants import MANAGER_ROLE
from at_tools.permission_dependency_manager.services.dependency_service import PermissionDependencyService


def get_service() -> PermissionDependencyService:
	return PermissionDependencyService()


def parse_list(value):
	value = frappe.parse_json(value) if isinstance(value, str) else value
	if not isinstance(value, list):
		frappe.throw(_("Expected a list."), frappe.ValidationError)
	return value


@frappe.whitelist()
def get_dependencies(role: str, doctype: str):
	frappe.only_for(MANAGER_ROLE)
	return get_service().get_dependencies(role, doctype)


@frappe.whitelist()
def get_existing_permissions(role: str, doctypes):
	frappe.only_for(MANAGER_ROLE)
	return get_service().get_existing_permissions(role, parse_list(doctypes))


@frappe.whitelist(methods=["POST"])
def save_dependency_configuration(role: str, doctype: str, dependencies):
	frappe.only_for(MANAGER_ROLE)
	return get_service().save_configuration(role, doctype, parse_list(dependencies))


@frappe.whitelist(methods=["POST"])
def remove_dependency(role: str, doctype: str, dependency_doctype: str):
	frappe.only_for(MANAGER_ROLE)
	return get_service().remove_dependency(role, doctype, dependency_doctype)


@frappe.whitelist(methods=["POST"])
def apply_dependencies(role: str, doctype: str):
	"""Apply the *saved* configuration; the request carries no permission payload."""
	frappe.only_for(MANAGER_ROLE)
	return get_service().apply_dependencies(role, doctype)
