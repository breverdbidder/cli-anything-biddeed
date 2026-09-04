from odoo import api, fields, models


class DeedBudgetLine(models.Model):
    _name = "deed.budget.line"
    _description = "Deed Project budget line (planned vs actual, per analytic account)"
    _order = "date_from desc, id desc"

    name = fields.Char(required=True)
    analytic_account_id = fields.Many2one(
        "account.analytic.account", string="Analytic Account", required=True, ondelete="cascade"
    )
    company_id = fields.Many2one(
        related="analytic_account_id.company_id", store=True, readonly=True
    )
    currency_id = fields.Many2one(
        related="company_id.currency_id", store=True, readonly=True
    )
    date_from = fields.Date(required=True)
    date_to = fields.Date(required=True)
    planned_amount = fields.Monetary(required=True, currency_field="currency_id")
    actual_amount = fields.Monetary(
        compute="_compute_actual_amount", currency_field="currency_id", store=False
    )
    variance_amount = fields.Monetary(
        compute="_compute_actual_amount", currency_field="currency_id", store=False
    )

    @api.depends("analytic_account_id", "date_from", "date_to", "planned_amount")
    def _compute_actual_amount(self):
        # account.analytic.line is populated automatically by Odoo whenever a journal
        # item carries an analytic_distribution referencing this analytic account —
        # this is the Community-safe "actuals" ledger (no account_budget/Enterprise
        # dependency; see infra/odoo/addons/deed_budget/__manifest__.py).
        AnalyticLine = self.env["account.analytic.line"]
        for line in self:
            actual = 0.0
            if line.analytic_account_id:
                domain = [
                    ("account_id", "=", line.analytic_account_id.id),
                    ("date", ">=", line.date_from),
                    ("date", "<=", line.date_to),
                ]
                groups = AnalyticLine.read_group(domain, ["amount:sum"], [])
                actual = groups[0]["amount"] if groups else 0.0
            line.actual_amount = -actual  # analytic lines on cost are negative; report as positive spend
            line.variance_amount = line.planned_amount - line.actual_amount
