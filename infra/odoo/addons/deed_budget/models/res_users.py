from odoo import models


class ResUsers(models.Model):
    _inherit = "res.users"

    def deed_generate_own_api_key(self, scope, name):
        """RPC-callable wrapper around res.users.apikeys._generate().

        Odoo's external API (execute_kw) refuses to call any method whose name
        starts with "_", which blocks the private _generate() directly. This
        thin public wrapper is our own code (LGPL-3), not a modification of
        core. _generate() always issues the key to self.env.user regardless of
        the recordset it's called on (same self-service semantics as the "New
        API Key" button under Settings > Users) — so this must be invoked
        while authenticated AS the technical/worker user the key is for, not
        by an admin acting on their behalf. See infra/odoo/bootstrap.py.
        """
        return self.env["res.users.apikeys"]._generate(scope, name)
