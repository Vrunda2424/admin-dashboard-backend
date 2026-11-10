ROLES = ("super_admin", "admin", "manager", "analyst", "support_staff")
STATUSES = ("Active", "Inactive")

# The roles each role may create, edit, and delete. A role that is not listed here cannot manage users at all.
MANAGEABLE = {
    "super_admin": ROLES,
    "admin": ("manager", "analyst", "support_staff"),
}
