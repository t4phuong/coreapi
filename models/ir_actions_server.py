# -*- coding: utf-8 -*-
from odoo import models, fields

class IrActionsServer(models.Model):
    _inherit = 'ir.actions.server'

    endpoint_manager_id = fields.Many2one(
        'action.endpoint.manager', 
        string='Endpoint Manager', 
        ondelete='cascade'
    )