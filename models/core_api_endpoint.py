# Part of T4 Core API. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class CoreApiEndpoint(models.Model):
    _name = 'core.api.endpoint'
    _description = 'Core API Endpoint Catalog'
    _order = 'code'

    name = fields.Char(required=True, translate=True)
    code = fields.Char(
        required=True,
        index=True,
        help='Permission code used by @validate_core_api and route checks.',
    )
    route_pattern = fields.Char(
        string='Route Pattern',
        help='Example: /api/v1/orders. Used for automatic access checks.',
    )
    description = fields.Text(translate=True)
    active = fields.Boolean(default=True)

    _code_unique = models.Constraint('unique(code)', 'Endpoint code must be unique.')
