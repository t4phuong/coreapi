# -*- coding: utf-8 -*-
import inspect
import textwrap
from odoo import models, fields, api, _

class ActionEndpointManager(models.Model):
    _name = 'action.endpoint.manager'
    _description = 'Action Endpoint Manager'

    name = fields.Char(
        string='Name', 
        default="Endpoint"
    )

    model_id = fields.Many2one(
        'ir.model', 
        string='Model', 
        required=True,
        domain=[('transient', '=', False)],
        ondelete='cascade'
    )
    # service_id = fields.Many2one(
    #     'service.endpoints', 
    #     string='Service', 
    #     ondelete='cascade'
    # )
    generated_action_ids = fields.One2many(
        'ir.actions.server', 
        'endpoint_manager_id', 
        string='Server Actions',
        readonly=True
    )

    def _generate_endpoints(self):
        self.ensure_one()
        ActionServer = self.env['ir.actions.server'].sudo()
        target_model_name = self.model_id.model
        
        target_class = type(self.env[target_model_name])
        
        for method_name, func in inspect.getmembers(target_class, predicate=callable):
            if hasattr(func, '_is_endpoint'):
                action_name = getattr(func, '_endpoint_name')

                code_body = textwrap.dedent(f"""
                    res = model.{method_name}()
                    env['core.api.application'].set_api_response(res)
                """)

                existing_action = ActionServer.search([
                    ('endpoint_manager_id', '=', self.id),
                    ('name', '=', action_name)
                ], limit=1)

                vals = {
                    'name': action_name,
                    'model_id': self.model_id.id,
                    'state': 'code',
                    'code': code_body,
                    'type': 'ir.actions.server',
                    'endpoint_manager_id': self.id,
                    'binding_model_id': False,
                    'binding_type': 'action',
                }

                if existing_action:
                    existing_action.write(vals)
                else:
                    ActionServer.create(vals)

    def action_generate_endpoints(self):
        self.ensure_one()

        self._generate_endpoints()
        
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