# Part of T4 Core API. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.http import request


class CoreApiVersion(models.Model):
    _name = 'core.api.version'
    _description = 'Core API Version'
    _order = 'domain_id, sequence, code'

    name = fields.Char(required=True, translate=True)
    domain_id = fields.Many2one(
        'core.api.domain',
        string='Host Domain',
        required=True,
        ondelete='restrict',
        index=True,
        default=lambda self: self.env['core.api.domain'].get_default().id,
        help='Groups this version under a public hostname, e.g. ashaf.xyz/api/v1.',
    )
    domain_hostname = fields.Char(related='domain_id.hostname', store=True, readonly=True)
    domain_base_url = fields.Char(related='domain_id.base_url', readonly=True)
    code = fields.Char(
        required=True,
        index=True,
        help='URL segment after /api/, e.g. v1 or v2.',
    )
    path_prefix = fields.Char(
        string='API Path',
        compute='_compute_path_prefix',
        store=True,
        help='Path on the host, e.g. /api/v1.',
    )
    public_base_url = fields.Char(
        string='Public Base URL',
        compute='_compute_public_base_url',
        help='Full public base URL including host, e.g. https://ashaf.xyz/api/v1.',
    )
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)
    description = fields.Text(translate=True)
    endpoint_count = fields.Integer(compute='_compute_endpoint_count')

    _code_unique_per_domain = models.Constraint(
        'unique(domain_id, code)',
        'API version code must be unique per host domain.',
    )

    @api.depends('code')
    def _compute_path_prefix(self):
        """Build the API path from the version code."""
        for rec in self:
            code = (rec.code or '').strip().strip('/')
            rec.path_prefix = f'/api/{code}' if code else '/api'

    @api.depends('domain_id.base_url', 'path_prefix')
    def _compute_public_base_url(self):
        """Build the full public URL for this version."""
        for rec in self:
            base = (rec.domain_id.base_url or '').rstrip('/')
            path = (rec.path_prefix or '/api').rstrip('/')
            rec.public_base_url = f'{base}{path}' if base else path

    @api.depends('code')
    def _compute_endpoint_count(self):
        """Count gateway routes linked to this version."""
        if not self.ids:
            return
        endpoint_data = self.env['core.api.endpoint'].read_group(
            [('version_id', 'in', self.ids)],
            [],
            ['version_id'],
        )
        counts = {}
        for row in endpoint_data:
            version = row.get('version_id')
            if not version:
                continue
            counts[version[0]] = row.get('version_id_count', row.get('__count', 0))
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
        """Return the default active API version (v1 on default domain, or first active)."""
        default_domain = self.env['core.api.domain'].get_default()
        version = self.env.ref('t4_coreapi.core_api_version_v1', raise_if_not_found=False)
        if version and version.active:
            return version
        domain = [('active', '=', True)]
        if default_domain:
            domain.append(('domain_id', '=', default_domain.id))
        return self.search(domain, order='sequence, code', limit=1)

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
    def get_active_by_code(self, code, api_domain=None):
        """Return an active version for code on the given host domain."""
        if not code:
            return self.browse()
        api_domain = api_domain or self.env['core.api.domain'].get_default()
        domain_filter = [('domain_id', '=', api_domain.id)] if api_domain else []
        return self.sudo().search(
            domain_filter + [('code', '=', code), ('active', '=', True)],
            limit=1,
        )

    @api.model
    def resolve_from_api_subpath(self, subpath, api_domain=None):
        """Parse /api/<version>/… using the request host domain.

        Example on ashaf.xyz:
        - subpath ``v1/orders`` -> version v1 on ashaf.xyz domain, suffix orders
        """
        subpath = (subpath or '').strip('/')
        if not subpath:
            return self.browse(), ''

        if api_domain is None:
            api_domain = self.env['core.api.domain'].sudo().get_from_request(
                request.httprequest if request else None
            )

        parts = subpath.split('/')
        version = self.get_active_by_code(parts[0], api_domain=api_domain)
        if version:
            return version, '/'.join(parts[1:])
        return self.browse(), ''
