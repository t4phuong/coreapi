# Part of T4 Core API. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class CoreApiDeviceSecretWizard(models.TransientModel):
    _name = 'core.api.device.secret.wizard'
    _description = 'Device Credentials (shown once)'

    device_id = fields.Many2one('core.api.device', required=True, ondelete='cascade')
    client_id = fields.Char(readonly=True)
    client_secret = fields.Char(readonly=True)

    def action_confirm(self):
        self.ensure_one()
        self.device_id.sudo().write({'credentials_pending': False})
        self.device_id._clear_pending_secret()
        return {'type': 'ir.actions.act_window_close'}
