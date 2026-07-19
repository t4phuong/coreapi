# -*- coding: utf-8 -*-
import inspect, logging
from odoo import models, fields, api, _
# pyrefly: ignore [missing-import]
from odoo.tools.safe_eval import safe_eval


_logger = logging.getLogger(__name__)

class IrActionsCoreApi(models.Model):
    _name = 't4.coreapi.action'
    _description = 'Action: Only Execute Python Code'
    _inherit = 'ir.actions.actions'

    type = fields.Char(default='t4.coreapi.action')

    model_id = fields.Many2one(
        'ir.model', 
        string='Model', 
        ondelete='cascade')

    code = fields.Text(
        string='Python Code', 
        required=True)

    service_id = fields.Many2one(
        't4.coreapi.service',
        string='Service',
        ondelete='cascade')

    _unique_action_name_per_service = models.Constraint(
        "UNIQUE(name, service_id)",
        "Action name must be unique per service!"
    )

    @api.model
    def run(self):
        self.ensure_one()
        model = self.env[self.model_id.model] if self.model_id.model else None

        eval_context = {
            "env": self.env,
            "model": model,
            "result": None,
            **self.env.context
        }

        safe_eval(self.code.strip(), eval_context, mode="exec")
        
        return eval_context.get('result')