# Part of T4 Core API. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class CoreApiVersion(models.Model):
    _name = 'core.api.version'
    _description = 'Core API Version'
    _order = 'sequence, code'

    name = fields.Char(required=True, translate=True)
    code = fields.Char(
        required=True,
        index=True,
        help='URL segment after /api/, e.g. v1 or v2.',
    )
    path_prefix = fields.Char(
        string='URL Prefix',
        compute='_compute_path_prefix',
        store=True,
        help='Public base path for this version, e.g. /api/v1.',
    )
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)
    description = fields.Text(translate=True)
    endpoint_count = fields.Integer(compute='_compute_endpoint_count')

    _code_unique = models.Constraint('unique(code)', 'API version code must be unique.')

    @api.depends('code')
    def _compute_path_prefix(self):
        """Build the public URL prefix from the version code."""
        for rec in self:
            code = (rec.code or '').strip().strip('/')
            rec.path_prefix = f'/api/{code}' if code else '/api'

    @api.depends('code')
    def _compute_endpoint_count(self):
        """Count gateway routes linked to this version."""
        endpoint_data = self.env['core.api.endpoint'].read_group(
            [('version_id', 'in', self.ids)],
            ['version_id'],
            ['version_id'],
        )
        counts = {
            row['version_id'][0]: row['__count']
            for row in endpoint_data
            if row.get('version_id')
        }
        for rec in self:
            rec.endpoint_count = counts.get(rec.id, 0)

    @api.constrains('code')
    def _check_code(self):
        """Reject empty or slash-containing version codes."""
        for rec in self:
            code = (rec.code or '').strip()
            if not code:
                raise ValidationError(_('API version code is required.'))
            if '/' in code:
                raise ValidationError(_('API version code must not contain slashes.'))

    @api.model
    def get_default_version(self):
        """Return the default active API version (v1, or the first active one)."""
        version = self.env.ref('t4_coreapi.core_api_version_v1', raise_if_not_found=False)
        if version and version.active:
            return version
        return self.search([('active', '=', True)], order='sequence, code', limit=1)

    def action_view_endpoints(self):
        """Open gateway routes filtered to this API version."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Gateway Routes'),
            'res_model': 'core.api.endpoint',
            'view_mode': 'list,form',
            'domain': [('version_id', '=', self.id)],
            'context': {'default_version_id': self.id},
        }

    @api.model
    def get_active_by_code(self, code):
        """Return an active version record for the given code, or empty recordset."""
        if not code:
            return self.browse()
        return self.sudo().search([('code', '=', code), ('active', '=', True)], limit=1)
