# -*- coding: utf-8 -*-
from odoo import models, fields, api

import logging
_logger = logging.getLogger(__name__)

class RequiredAction(models.Model):
    _name = 't4.coreapi.required.action'
    _description = 'Required Action'

    service_id = fields.Many2one(
        't4.coreapi.service', 
        string='Service', 
        ondelete='cascade')
        
    api_action_id = fields.Many2one(
        't4.coreapi.action',
        string='Required Actions',
        required=True)

    sequence = fields.Integer(
        string='Sequence',
        required=True,
        default=True)

class CoreApiService(models.Model):
    _name = 't4.coreapi.service'
    _description = 'Core API Service'

    name = fields.Char(
        string='Name', 
        required=True, 
        default='odoo')

    code = fields.Char(
        string='Service Code', 
        required=True)

    version_ids = fields.One2many(
        't4.coreapi.version', 
        'service_id', 
        string='Versions',
        context={"active_test": False})

    required_action_ids = fields.One2many(
        't4.coreapi.required.action', 
        'service_id', 
        string='Required Actions')

    _service_code_unique = models.Constraint(
        "UNIQUE(code)",
        "Service code must be unique!")



    
