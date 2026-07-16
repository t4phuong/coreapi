# -*- coding: utf-8 -*-
import inspect
from odoo import models, fields, api, _
# pyrefly: ignore [missing-import]
from odoo.tools.safe_eval import safe_eval
# pyrefly: ignore [missing-import]
from odoo.http import request

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

                code_body = f"model.{method_name}()"

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
        ondelete='cascade'
    )

    model_id = fields.Many2one('ir.model', string='Model', required=True, ondelete='cascade')
    code = fields.Text(string='Python Code', required=True)

    @api.model
    def run(self):
        self.ensure_one()
        ctx = self.env.context

        if self.model_id.model not in self.env:
            raise ValueError(f"Model {self.model_id.model} not found.")
        
        model = self.env[self.model_id.model]
    
        eval_context = {
            # core Odoo
            "env": self.env,
            "model": model,
    
            # HTTP / API context
            "request_method": ctx.get("core_api_method"),
            "route": ctx.get("core_api_route"),
            "endpoint": ctx.get("core_api_endpoint_code"),
    
            # payload
            "body": ctx.get("core_api_body"),
            "params": ctx.get("core_api_params"),
    
            # active records (quan trọng)
            "active_model": ctx.get("active_model"),
            "active_id": ctx.get("active_id"),
            "active_ids": ctx.get("active_ids"),
    
            # optional convenience
            "application_id": ctx.get("core_api_application_id"),
        }

        safe_eval(
            self.code.strip(), 
            eval_context, 
            mode="exec")

        return eval_context.get('action', False)

