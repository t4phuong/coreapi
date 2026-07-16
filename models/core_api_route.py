# -*- coding: utf-8 -*-

from odoo import models, fields, api

class CoreApiRoute(models.Model):
    _name = 't4.coreapi.route'
    _description = 'Core API Route'

    name = fields.Char(string='Route', required=True, default='/')
    
    allow_method = fields.Selection([
        ('GET', 'GET'),
        ('POST', 'POST'),
        ('PUT', 'PUT'),
        ('PATCH', 'PATCH'),
        ('DELETE', 'DELETE'),
    ], string='Allow Method', required=True, default='GET')
    
    api_action_id = fields.Many2one(
        't4.coreapi.action', 
        string='API Action', 
        ondelete='cascade'
    )

    version_id = fields.Many2one(
        't4.coreapi.version',
        string='Version',
        ondelete='cascade',
        required=True
    )

    full_route = fields.Char (
        string='Full Route',
        compute="_compute_full_route",
        store=True,
    )

    @api.depends("version_id", "name")
    def _compute_full_route(self):
        for record in self:
            version = record.version_id
            record.full_route = f"{version.route}{record.name}"

    _unique_route_per_version = models.Constraint(
        'UNIQUE(name, version_id)',
        'The route must be unique per version!'
    )

    ###### CRUD ######
    @api.model
    def _normalize_route(self, route):
        return route.lstrip("/")
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name"):
                vals["name"] = "/" + self._normalize_route(vals["name"])
        return super().create(vals_list)
    
    def write(self, vals):
        if vals.get("name"):
            vals["name"] = "/" + self._normalize_route(vals["name"])
        return super().write(vals)

    ##### Route Finding #####
    @api.model
    def _match_routes(self, request_route):
        return self.search([
            ('full_route', '=', request_route),
        ], limit=1)
        