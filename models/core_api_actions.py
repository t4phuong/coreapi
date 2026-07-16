# -*- coding: utf-8 -*-
import inspect, logging
from odoo import models, fields, api, _
# pyrefly: ignore [missing-import]
from odoo.tools.safe_eval import safe_eval


_logger = logging.getLogger(__name__)

class ActionEndpointManager(models.Model):
    _name = 't4.coreapi.action.manager'
    _description = 'Action Endpoint Manager'

    name = fields.Char(
        string='Name', 
        default="Endpoint"
    )

    model_id = fields.Many2one(
        'ir.model', 
        string='Model', 
        domain=[('transient', '=', False)],
        ondelete='cascade'
    )
    
    def _generate_core_api_action(self):
        self.ensure_one()
        CAaction = self.env['t4.coreapi.action'].sudo()
        target_model_name = self.model_id.model
        
        target_class = type(self.env[target_model_name])
        
        for method_name, func in inspect.getmembers(target_class, predicate=callable):
            if hasattr(func, '_is_endpoint'):
                action_name = getattr(func, '_endpoint_name')

                code_body = f"result = model.{method_name}()"

                existing_action = CAaction.search([
                    ('endpoint_manager_id', '=', self.id),
                    ('name', '=', action_name)
                ], limit=1)

                vals = {
                    'name': action_name,
                    'model_id': self.model_id.id,
                    'code': code_body,
                    'endpoint_manager_id': self.id,
                }

                if existing_action:
                    existing_action.write(vals)
                else:
                    CAaction.create(vals)
    
    def action_generate_core_api_action(self):
        self.ensure_one()
        self._generate_core_api_action()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Endpoints have been synchronized for model %s.') % self.model_id.model,
                'type': 'success',
                'sticky': False,
                'next': {
                    'type': 'ir.actions.client',
                    'tag': 'reload',
                },
            }
        }


class IrActionsCoreApi(models.Model):
    _name = 't4.coreapi.action'
    _description = 'Action: Only Execute Python Code'
    _inherit = 'ir.actions.actions'

    type = fields.Char(default='t4.coreapi.action')

    endpoint_manager_id = fields.Many2one(
        't4.coreapi.action.manager', 
        string='Endpoint Manager', 
        ondelete='cascade')

    model_id = fields.Many2one(
        'ir.model', 
        string='Model', 
        ondelete='cascade')

    code = fields.Text(
        string='Python Code', 
        required=True)

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
