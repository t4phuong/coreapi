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
        required=True,
        ondelete='cascade')

    route_ids = fields.One2many(
        't4.coreapi.route', 
        'version_id', 
        string='Routes')

    active = fields.Boolean(default=True)

    def action_inactive_version(self):
        for record in self:
            record.active = False

    total_routes = fields.Integer(
        string='Routes',
        compute='_compute_total_routes'
    )

    @api.depends('route_ids')
    def _compute_total_routes(self):
        for record in self:
            record.total_routes = len(record.route_ids)

    version_code = fields.Char (
        string='Version Code',
        compute='_compute_version_code',
        store=True
    )

    @api.depends('service_id', 'name')
    def _compute_version_code(self):
        for record in self:
            record.version_code = f"{record.service_id.code}/{record.name}"

    _unique_version_per_service = models.Constraint(
        'UNIQUE(name, service_id)',
        'Version name must be unique per service!'
    )