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

    is_rate_limit_enabled = fields.Boolean(
        string='Enable Rate Limit',
        default=False)

    rate_limit_type = fields.Selection([
        ('service', 'Service Level'),
        ('user', 'User Level')
    ], string='Rate Limit Type', default='service', required=True)

    @api.onchange('privacy')
    def _onchange_privacy(self):
        for record in self:
            if record.privacy == 'public':
                record.rate_limit_type = 'service'

    rate_limit_calls = fields.Integer(
        string='Max Calls',
        default=100)

    rate_limit_period = fields.Integer(
        string='Period (Minutes)',
        default=1,
        help='Time window in minutes to check for max calls.')

    privacy = fields.Selection([
        ('public', 'Public'),
        ('private', 'Private')
    ], string='Privacy', default='private', required=True)

    jwt_secret = fields.Char(
        string='JWT Secret',
        default=lambda self: __import__('uuid').uuid4().hex,
        copy=False,
        help='Secret key used to sign JWT tokens for this service.'
    )

    instruction = fields.Html(
        string='Instruction',
        compute='_compute_instruction'
    )

    @api.depends('privacy', 'code', 'name')
    def _compute_instruction(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url', 'http://localhost:8069')
        for record in self:
            if record.privacy == 'public':
                record.instruction = f"""
                <h3>How to query {record.name} (Public)</h3>
                <p>This service is public. No authentication is required.</p>
                <p><strong>Headers:</strong></p>
                <ul>
                    <li><code>Content-Type: application/json</code></li>
                    <li><code>X-Odoo-Database: {self.env.cr.dbname}</code></li>
                </ul>
                <p><strong>Example Path:</strong> <code>{base_url}/api/{record.code}/v1/route</code></p>
                """
            else:
                record.instruction = f"""
                <h3>How to query {record.name} (Private)</h3>
                <p>This service requires authentication.</p>
                <p><strong>1. Get Token:</strong> Send a POST request to the <code>auth</code> service's <code>/login</code> route.</p>
                <p><strong>Headers:</strong></p>
                <ul>
                    <li><code>Content-Type: application/json</code></li>
                    <li><code>X-Odoo-Database: {self.env.cr.dbname}</code></li>
                </ul>
                <p><strong>Body (Raw JSON):</strong></p>
                <pre><code>{{\n  "username": "your_username",\n  "password": "your_password"\n}}</code></pre>
                
                <p><strong>2. Query API:</strong> Include the token in your subsequent requests.</p>
                <p><strong>Headers:</strong></p>
                <ul>
                    <li><code>Content-Type: application/json</code></li>
                    <li><code>X-Odoo-Database: {self.env.cr.dbname}</code></li>
                    <li><code>Authorization: Bearer &lt;your_token&gt;</code></li>
                </ul>
                <p><strong>Example Body (Raw JSON):</strong></p>
                <pre><code>{{\n  "key": "value"\n}}</code></pre>
                """

    client_ids = fields.One2many(
        't4.coreapi.client',
        'service_id',
        string='API Users'
    )

    _sql_constraints = [
        ('unique_code', 'UNIQUE(code)', 'Service code must be unique!')
    ]

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        auth_middleware = self.env.ref('t4_coreapi.action_t4_coreapi_default_auth_middleware', raise_if_not_found=False)
        if auth_middleware:
            for record in records:
                self.env['t4.coreapi.required.action'].create({
                    'service_id': record.id,
                    'api_action_id': auth_middleware.id,
                    'sequence': 10
                })
        return records

    role_ids = fields.One2many(
        't4.coreapi.role',
        'service_id',
        string='Roles'
    )

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

    def action_generate_jwt_secret(self):
        for record in self:
            record.jwt_secret = __import__('uuid').uuid4().hex




    
