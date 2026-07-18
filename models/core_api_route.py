# -*- coding: utf-8 -*-

from odoo import models, fields, api

class CoreApiRoute(models.Model):
    _name = 't4.coreapi.route'
    _description = 'Core API Route'
    _rec_name = 'route_path'

    route_path = fields.Char(string='Route Path', required=True, default='/')
    
    allow_method = fields.Selection([
        ('GET', 'GET'),
        ('POST', 'POST'),
        ('PUT', 'PUT'),
        ('PATCH', 'PATCH'),
        ('DELETE', 'DELETE'),
    ], string='Allow Method', required=True, default='GET')
    
    version_id = fields.Many2one(
        't4.coreapi.version', 
        string='Version', 
        required=True,
        ondelete='cascade')

    service_id = fields.Many2one(
        't4.coreapi.service',
        related='version_id.service_id',
        store=True,
        string='Service'
    )

    role_id = fields.Many2one(
        't4.coreapi.role',
        string='Allowed Roles',
        help="Roles allowed to access this route when Auth Type is Protected."
    )

    api_action_id = fields.Many2one(
        't4.coreapi.action', 
        string='API Action', 
        ondelete='cascade'
    )

    display_route = fields.Char (
        string='Display Route',
        compute="_compute_display_route",
        store=True,
    )

    @api.depends("version_id", "route_path")
    def _compute_display_route(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url', 'http://localhost:8069')
        for record in self:
            version = record.version_id
            full_path = f"{version.version_code}/{record.route_path}".replace("//", "/") if version else ""
            record.display_route = f"{base_url}/{full_path.strip('/')}"

    _unique_route_per_version = models.Constraint(
        'UNIQUE(route_path, version_id)',
        'The route path must be unique per version!'
    )

    ###### CRUD ######
    @api.model
    def _normalize_route(self, route):
        return route.lstrip("/")
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("route_path"):
                vals["route_path"] = "/" + self._normalize_route(vals["route_path"])
        return super().create(vals_list)
    
    def write(self, vals):
        if vals.get("route_path"):
            vals["route_path"] = "/" + self._normalize_route(vals["route_path"])
        return super().write(vals)