# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.tools.safe_eval import safe_eval

class IrActionsServer(models.Model):
    _inherit = 'ir.actions.server'

    endpoint_manager_id = fields.Many2one(
        'action.endpoint.manager', 
        string='Endpoint Manager', 
        ondelete='cascade'
    )

class IrActionsCoreApi(models.Model):
    _name = 'ir.actions.core_api'
    _description = 'Action: Only Execute Python Code'
    _inherit = 'ir.actions.actions'

    type = fields.Char(default='ir.actions.core_api')

    endpoint_manager_id = fields.Many2one(
        'action.endpoint.manager', 
        string='Endpoint Manager', 
        ondelete='cascade'
    )

    model_id = fields.Many2one('ir.model', string='Model', required=True, ondelete='cascade')
    code = fields.Text(string='Python Code', required=True)

    _unique_name = models.Constraint(
        'UNIQUE(enpoint_manager_id, name)',
        'unique name with manager',
    )

    @api.model
    def run(self, action_id):
        self.unsure_one()
        
        actions_server = self.env['ir.actions.server'].sudo()

        eval_context = actions_server._get_eval_context(self)

        safe_eval(self.code.strip(), eval_context, mode="exec", nocopy=True)

        return eval_context.get('action', False)