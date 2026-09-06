from odoo import api, models


class ProjectProject(models.Model):
    _inherit = "project.project"

    # Odoo 18 core (addons/project/models/project_project.py) renamed the old single
    # analytic_account_id field to account_id (Many2one account.analytic.account) and
    # ships a conditional _create_analytic_account() helper, but it isn't guaranteed to
    # fire on every plain project.project.create() call. We want it deterministic — every
    # Deed Project always gets an analytic account in the same RPC call that creates the
    # project (Worker's "create project -> analytic account" step, docs/infra/ODOO.md Test A).
    @api.model_create_multi
    def create(self, vals_list):
        AnalyticAccount = self.env["account.analytic.account"]
        for vals in vals_list:
            if not vals.get("account_id"):
                account = AnalyticAccount.create({
                    "name": vals.get("name", "Deed Project"),
                    "company_id": vals.get("company_id") or self.env.company.id,
                })
                vals["account_id"] = account.id
        return super().create(vals_list)
