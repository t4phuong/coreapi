# -*- coding: utf-8 -*-
from odoo import models, fields, api
import inspect

class ActionGenerateWizard(models.TransientModel):
    _name = 't4.coreapi.action.generate.wizard'
    _description = 'Generate API Actions Wizard'

    service_id = fields.Many2one('t4.coreapi.service', required=True)
    model_ids = fields.Many2many('ir.model', string='Models')

    def action_generate(self):
        self.ensure_one()
        CAaction = self.env['t4.coreapi.action'].sudo()
        for model_record in self.model_ids:
            target_model_name = model_record.model
            target_class = type(self.env[target_model_name])

            for method_name, func in inspect.getmembers(target_class, predicate=callable):
                if hasattr(func, '_is_endpoint'):
                    action_name = getattr(func, '_endpoint_name')
                    code_body = f"result = model.{method_name}()"

                    existing_action = CAaction.search([
                        ('service_id', '=', self.service_id.id),
                        ('name', '=', action_name)
                    ], limit=1)

                    vals = {
                        'name': action_name,
                        'model_id': model_record.id,
                        'code': code_body,
                        'service_id': self.service_id.id,
                    }

                    if existing_action:
                        existing_action.write(vals)
                    else:
                        CAaction.create(vals)
        return {'type': 'ir.actions.act_window_close'}
