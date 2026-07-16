# -*- coding: utf-8 -*-
from odoo import api, models, fields

class CoreApiVersion(models.Model):
    _name = 't4.coreapi.version'
    _description = 'Core API Version'

    name = fields.Char(
        string='Version Name', 
        required=True, 
        default='v1')
    
    service_id = fields.Many2one(
        't4.coreapi.service', 
        string='Service', 
        ondelete='cascade', 
        required=True)

    route_ids = fields.One2many(
        't4.coreapi.route', 
        'version_id', 
        string='Routes')

    active = fields.Boolean(default=True)

    total_routes = fields.Integer(
        string='Routes',
        compute='_compute_total_routes'
    )

    @api.depends('route_ids')
    def _compute_total_routes(self):
        for record in self:
            record.total_routes = len(record.route_ids)

    route = fields.Char (
        compute='_compute_route',
        store=True
    )

    @api.depends('service_id', 'name')
    def _compute_route(self):
        for record in self:
            record.route = f"{record.service_id.code}/{record.name}"

    _unique_version_per_service = models.Constraint(
        'UNIQUE(name, service_id)',
        'Version name must be unique per service!'
    )

    #### CRUD
    @api.model
    def _match_routes(self, route):
        return self.search([
            ('route', '=', route),
        ], limit=1)
