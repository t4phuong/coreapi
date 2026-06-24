# Part of T4 Core API. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class CoreApiApplicationSecretWizard(models.TransientModel):
    _name = 'core.api.application.secret.wizard'
    _description = 'Application Credentials (shown once)'

    application_id = fields.Many2one('core.api.application', required=True, ondelete='cascade')
    client_id = fields.Char(readonly=True)
    client_secret = fields.Char(readonly=True)

    def action_confirm(self):
        """Mark credentials as viewed and close the popup."""
        self.ensure_one()
        self.application_id.sudo().write({'credentials_pending': False})
        self.application_id._clear_pending_secret()
        return {'type': 'ir.actions.act_window_close'}
