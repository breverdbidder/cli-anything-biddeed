{
    "name": "Deed Budget",
    "version": "18.0.1.0.0",
    "summary": "Minimal budget-vs-actual for Deed Projects analytic accounts",
    "description": """
Odoo 18 Community does not ship a Budget app (account_budget moved to
Enterprise). This module is our own code (LGPL-3, matching Odoo Community's
license) adding the smallest model needed for Deed Projects: a planned amount
per analytic account/date-range, compared against actual spend pulled from
account.analytic.line (populated automatically when journal entries carry an
analytic distribution). No Enterprise or Elastic-licensed code is used or
required.
    """,
    "author": "Everest Capital USA",
    "license": "LGPL-3",
    "category": "Accounting/Analytic",
    "depends": ["project", "account", "analytic"],
    "data": [
        "security/ir.model.access.csv",
        "views/deed_budget_line_views.xml",
    ],
    "installable": True,
    "application": False,
}
