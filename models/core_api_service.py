# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
import inspect
# pyrefly: ignore [missing-import]
from odoo.fields import Domain
from dateutil.relativedelta import relativedelta
# pyrefly: ignore [missing-import]
from odoo.addons.t4_coreapi.exceptions import (
    APIBadRequest,
    APIUnauthorized,
    APITooManyRequests, 
)
# pyrefly: ignore [missing-import]
from odoo.addons.t4_coreapi.utils import endpoint
import logging
_logger = logging.getLogger(__name__)

class CoreApiMiddleware(models.Model):
    _name = 't4.coreapi.middleware'
    _description = 'API Middlewares'
    _order = 'sequence'

    service_id = fields.Many2one(
        't4.coreapi.service', 
        string='Service',
        ondelete='cascade')
        
    api_action_id = fields.Many2one(
        't4.coreapi.action',
        string='Required Actions',
        domain="['|', ('service_id', '=', service_id), ('service_id', '=', False)]",
        required=True)

    sequence = fields.Integer(
        string='Sequence',
        required=True,
        default=True)

class CoreApiService(models.Model):
    _name = 't4.coreapi.service'
    _description = 'Core API Service'

    ############## Elemental fields ####################
    name = fields.Char(
        string='Name', 
        required=True, 
        default='odoo')

    code = fields.Char(
        string='Service Code', 
        required=True)

    active = fields.Boolean(
        string='Active',
        default=True,
        copy=False,
        help='Whether this API is active or not.')

    status = fields.Selection([
        ('ok', 'OK'),
        ('warning', 'Warning')
    ], string='Status', compute='_compute_status')

    def _compute_status(self):
        for record in self:
            if record.rate_limit_action == 'warning' and record.is_rate_limit_enabled:
                time_limit = fields.Datetime.now() - relativedelta(minutes=record.rate_limit_period or 1)
                count = self.env['t4.coreapi.rate.limit.log'].search_count([
                    ('service_id', '=', record.id),
                    ('create_date', '>=', time_limit)
                ])
                record.status = 'warning' if count >= (record.rate_limit_calls or 100) else 'ok'
            else:
                record.status = 'ok'

    middleware_ids = fields.One2many(
        't4.coreapi.middleware',
        'service_id',
        string='Middlewares')

    ############################# Actor Fields ####################################
    client_ids = fields.One2many(
        't4.coreapi.client',
        'service_id',
        string='API Users'
    )

    role_ids = fields.One2many(
        't4.coreapi.role',
        'service_id',
        string='Roles'
    )
    ############################### Model & Action Fields ####################################
    action_ids = fields.One2many(
        't4.coreapi.action', 
        'service_id', 
        string='Actions')

    model_ids = fields.Many2many(
        'ir.model',
        string='Models'
    )
    ################################## Version & Routes ####################################    
    current_version_id = fields.Many2one(
        't4.coreapi.version',
        string='Current Version',
        store=True)

    version_id = fields.Many2one(
        't4.coreapi.version',
        compute='_compute_version_id',
        search='_search_version_id',
        ondelete='cascade',
        required=True,
        compute_sudo=True)

    def _search_version_id(self, operator, value):
        domain = Domain('id', operator, value)
        return Domain('id', 'in', self.env['t4.coreapi.version']._search(domain).select('service_id'))

    @api.depends('current_version_id')
    @api.depends_context('version_id', 'service_id')
    def _compute_version_id(self):
        context_version_id = self.env.context.get('version_id', False)
        version_id = self.env['t4.coreapi.version'].browse(context_version_id).exists() if context_version_id else False
        
        for record in self:
            if version_id and version_id.service_id == record:
                record.version_id = version_id
            else:
                record.version_id = record.current_version_id
    
    version_ids = fields.One2many(
        't4.coreapi.version', 
        'service_id', 
        string='Versions')

    route_ids = fields.One2many(
        related='version_id.route_ids', 
        readonly=False,
        context={'version_id': version_id})

    ################################# Security Part ####################################
    privacy = fields.Selection([
        ('public', 'Public'),
        ('private', 'Private')
    ], string='Privacy', default='private', required=True)

    is_rate_limit_enabled = fields.Boolean(
        string='Enable Rate Limit',
        default=False)

    allow_multiple_sessions = fields.Boolean(
        string='Allow Multiple Sessions',
        default=False)

    token_expiration = fields.Integer(
        string='Token Expiration (Hours)',
        default=24,
        help='Token validity duration in hours.'
    )

    rate_limit_calls = fields.Integer(
        string='Max Calls',
        default=100)

    rate_limit_period = fields.Integer(
        string='Period (Minutes)',
        default=1,
        help='Time window in minutes to check for max calls.')

    rate_limit_action = fields.Selection([
        ('warning', 'Warning'),
        ('block', 'Block')
    ], string='Rate Limit Action', default='block', required=True)

    rate_limit_type = fields.Selection([
        ('service', 'Service Level'),
        ('user', 'User Level'),
        ('session', 'Session Level')
    ], string='Rate Limit Type', default='service', required=True)

    # constraint on privacy
    @api.onchange('privacy')
    def _onchange_privacy(self):
        for record in self:
            if record.privacy == 'public':
                record.rate_limit_type = 'service'

    ################################# Instruction Part ####################################
    instruction = fields.Html(
        string='Instruction',
        compute='_compute_instruction'
    )

    @api.depends('privacy', 'code', 'name', 'version_id')
    def _compute_instruction(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url', 'http://localhost:8069')
        for record in self:
            version_str = f" - {record.version_id.name}" if record.version_id else ""
            version_path = f"/{record.version_id.name}" if record.version_id else ""
            
            if record.privacy == 'public':
                record.instruction = f"""
                <div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px; border-left: 5px solid #28a745;">
                    <h3 style="color: #28a745; margin-top: 0;">How to query {record.name} (Public){version_str}</h3>
                    <p style="font-size: 14px;">This service is public. No authentication is required.</p>
                    <div style="margin-top: 15px;">
                        <strong style="color: #495057;">Headers:</strong>
                        <ul style="background: #e9ecef; padding: 10px 10px 10px 30px; border-radius: 5px; font-family: monospace;">
                            <li>Content-Type: application/json</li>
                            <li>X-Odoo-Database: {self.env.cr.dbname}</li>
                        </ul>
                    </div>
                    <div style="margin-top: 15px;">
                        <strong style="color: #495057;">Example Path:</strong>
                        <div style="background: #e9ecef; padding: 10px; border-radius: 5px; font-family: monospace;">
                            {base_url}/api/{record.code}{version_path}/route
                        </div>
                    </div>
                </div>
                """
            else:
                record.instruction = f"""
                <div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px; border-left: 5px solid #007bff;">
                    <h3 style="color: #007bff; margin-top: 0;">How to query {record.name} (Private){version_str}</h3>
                    <p style="font-size: 14px;">This service requires authentication.</p>
                    
                    <h4 style="color: #495057; margin-top: 20px;">1. Get Token:</h4>
                    <p style="font-size: 13px; color: #6c757d;">Send a POST request to the <code>auth</code> service's <code>/login</code> route.</p>
                    <div style="margin-top: 10px;">
                        <strong style="color: #495057;">Headers:</strong>
                        <ul style="background: #e9ecef; padding: 10px 10px 10px 30px; border-radius: 5px; font-family: monospace;">
                            <li>Content-Type: application/json</li>
                            <li>X-Odoo-Database: {self.env.cr.dbname}</li>
                        </ul>
                    </div>
                    <div style="margin-top: 10px;">
                        <strong style="color: #495057;">Body (Raw JSON):</strong>
                        <pre style="background: #212529; color: #f8f9fa; padding: 10px; border-radius: 5px;"><code>{{
  "username": "your_username",
  "password": "your_password"
}}</code></pre>
                    </div>
                    
                    <h4 style="color: #495057; margin-top: 20px;">2. Query API:</h4>
                    <p style="font-size: 13px; color: #6c757d;">Include the token in your subsequent requests.</p>
                    <div style="margin-top: 10px;">
                        <strong style="color: #495057;">Headers:</strong>
                        <ul style="background: #e9ecef; padding: 10px 10px 10px 30px; border-radius: 5px; font-family: monospace;">
                            <li>Content-Type: application/json</li>
                            <li>X-Odoo-Database: {self.env.cr.dbname}</li>
                            <li>Authorization: Bearer &lt;your_token&gt;</li>
                        </ul>
                    </div>
                    <div style="margin-top: 10px;">
                        <strong style="color: #495057;">Example Path:</strong>
                        <div style="background: #e9ecef; padding: 10px; border-radius: 5px; font-family: monospace;">
                            {base_url}/api/{record.code}{version_path}/route
                        </div>
                    </div>
                </div>
                """

    ################################# Meta Data Fields ####################################
    session_count = fields.Integer(string='Session Count', compute='_compute_session_count')
    def _compute_session_count(self):
        for record in self:
            record.session_count = self.env['t4.coreapi.auth.session'].search_count([('service_id', '=', record.id)])

    log_count = fields.Integer(string='Log Count', compute='_compute_log_count')
    def _compute_log_count(self):
        for record in self:
            record.log_count = self.env['t4.coreapi.rate.limit.log'].search_count([('service_id', '=', record.id)])

    action_count = fields.Integer(string='Action Count', compute='_compute_action_count')
    def _compute_action_count(self):
        for record in self:
            record.action_count = self.env['t4.coreapi.action'].search_count([('service_id', '=', record.id)])

    client_count = fields.Integer(string='Client Count', compute='_compute_client_count')
    def _compute_client_count(self):
        for record in self:
            record.client_count = self.env['t4.coreapi.client'].search_count([('service_id', '=', record.id)])

    version_count = fields.Integer(string='Version Count', compute='_compute_version_count')
    def _compute_version_count(self):
        for record in self:
            record.version_count = len(record.version_ids)

    def _generate_core_api_action(self):
        target_model_names = self.model_ids.mapped('model')
        CAaction = self.env['t4.coreapi.action'].sudo()
        
        for model_name in target_model_names:
            target_class = type(self.env[model_name])
            model_record = self.env['ir.model'].search([('model', '=', model_name)], limit=1)
            for method_name, func in inspect.getmembers(target_class, predicate=callable):
                if hasattr(func, '_is_endpoint'):
                    action_name = getattr(func, '_endpoint_name')
                    code_body = f"result = model.{method_name}()"
                    existing_action = CAaction.search([
                        ('service_id', '=', self.id),
                        ('name', '=', action_name)
                    ], limit=1)

                    vals = {
                        'name': action_name,
                        'model_id': model_record.id,
                        'code': code_body,
                        'service_id': self.id,
                    }

                    if existing_action:
                        existing_action.write(vals)
                    else:
                        CAaction.create(vals)
    
    def action_generate_core_api_action(self):
        self._generate_core_api_action()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Endpoints have been synchronized.'),
                'type': 'success',
                'sticky': False,
            }
        }

    ################################ Endpoints Functions ################################
    @endpoint("Default Auth: Rate Limit")
    def check_rate_limit(self, auth_info):
        service = auth_info.get('service')
        if not service:
            service = self.env.context.get('service')
        if not service.is_rate_limit_enabled:
            return

        client = auth_info.get('client')
        session = auth_info.get('session')

        time_limit = fields.Datetime.now() - relativedelta(minutes=service.rate_limit_period)
        domain = [('service_id', '=', service.id), ('create_date', '>=', time_limit)]
        
        if service.rate_limit_type == 'session':
            if not session:
                raise APIBadRequest(_('Session ID is required.'))
            domain.append(('session_id', '=', session.id))
        elif service.rate_limit_type == 'user':
            if not client:
                raise APIUnauthorized(_('User ID is not found.'))
            domain.append(('client_id', '=', client.id))

        log_count = self.env['t4.coreapi.rate.limit.log'].sudo().search_count(domain)

        if log_count >= service.rate_limit_calls:
            if service.rate_limit_action == 'warning':
                pass
            else:
                raise APITooManyRequests("Rate limit exceeded.")

        vals = {'service_id': service.id}
        if client:
            vals['client_id'] = client.id
            vals['session_id'] = session.id

        self.env['t4.coreapi.rate.limit.log'].sudo().create(vals)

    ################################# Constraints Part & CRUD ####################################
    def _default_middlewares(self):
        self.env['t4.coreapi.middleware'].create([
            {
                'service_id': self.id,
                'api_action_id': self.env.ref('t4_coreapi.action_t4_coreapi_default_auth_middleware').id,
                'sequence': 1,
            },
            {
                'service_id': self.id,
                'api_action_id': self.env.ref('t4_coreapi.action_t4_coreapi_default_rate_limit').id,
                'sequence': 5,
            }
        ])
    
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if not self.env.context.get('no_auto_version'):
            for record in records:
                record._default_middlewares()
                self.env['t4.coreapi.version'].create({
                    'name': 'v1',
                    'service_id': record.id,
                })
        return records
    
    _service_code_unique = models.Constraint(
        "UNIQUE(code)",
        "Service code must be unique!")


    
