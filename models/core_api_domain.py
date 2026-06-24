# Part of T4 Core API. See LICENSE file for full copyright and licensing details.

from urllib.parse import urlparse

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.http import request

from odoo.addons.t4_coreapi.utils.security import get_request_hostname


class CoreApiDomain(models.Model):
    _name = 'core.api.domain'
    _description = 'Core API Host Domain'
    _order = 'sequence, name'

    name = fields.Char(required=True, translate=True)
    hostname = fields.Char(
        string='Hostname',
        index=True,
        help='Public host name for this API group, e.g. api.afhaa.com or ashaf.xyz. '
             'Point DNS to this Odoo server. Leave empty on the default domain.',
    )
    is_default = fields.Boolean(
        string='Default Domain',
        default=False,
        help='Used when the request host does not match any configured hostname '
             '(e.g. localhost or web.base.url).',
    )
    base_url = fields.Char(
        string='Base URL',
        compute='_compute_base_url',
        help='Public API root for this host, e.g. https://ashaf.xyz.',
    )
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)
    description = fields.Text(translate=True)
    version_ids = fields.One2many('core.api.version', 'domain_id', string='API Versions')
    version_count = fields.Integer(compute='_compute_version_count')

    _hostname_unique = models.Constraint(
        'unique(hostname)',
        'API hostname must be unique.',
    )

    @api.depends('hostname', 'is_default')
    def _compute_base_url(self):
        """Build the public base URL from hostname or web.base.url."""
        web_base = (
            self.env['ir.config_parameter'].sudo().get_param('web.base.url') or ''
        ).rstrip('/')
        parsed = urlparse(web_base)
        scheme = parsed.scheme or 'https'
        for rec in self:
            host = (rec.hostname or '').strip().lower()
            if host and not rec.is_default:
                rec.base_url = f'{scheme}://{host}'
            else:
                rec.base_url = web_base

    @api.depends('version_ids')
    def _compute_version_count(self):
        """Count API versions linked to this domain."""
        for rec in self:
            rec.version_count = len(rec.version_ids)

    @api.constrains('hostname', 'is_default')
    def _check_hostname(self):
        """Validate hostname format and require it on non-default domains."""
        for rec in self:
            host = (rec.hostname or '').strip().lower()
            if rec.is_default:
                if host:
                    raise ValidationError(_('The default API domain must not have a hostname.'))
                continue
            if not host:
                raise ValidationError(_('Non-default API domains require a hostname.'))
            if '/' in host or ' ' in host:
                raise ValidationError(_('Hostname must not contain slashes or spaces.'))
            if host.startswith('http://') or host.startswith('https://'):
                raise ValidationError(_('Enter only the hostname, without http:// or https://.'))

    @api.constrains('is_default')
    def _check_single_default(self):
        """Allow only one default API domain."""
        defaults = self.search([('is_default', '=', True)])
        if len(defaults) > 1:
            raise ValidationError(_('Only one default API domain is allowed.'))

    @api.model
    def get_default(self):
        """Return the default API domain record."""
        domain = self.env.ref('t4_coreapi.core_api_domain_default', raise_if_not_found=False)
        if domain and domain.active:
            return domain
        return self.search([('is_default', '=', True), ('active', '=', True)], limit=1)

    @api.model
    def get_from_request(self, httprequest=None):
        """Resolve the API domain from the incoming HTTP Host header."""
        httprequest = httprequest or (request.httprequest if request else None)
        if not httprequest:
            return self.get_default()

        host = get_request_hostname(httprequest)
        if host:
            domain = self.sudo().search([
                ('hostname', '=', host),
                ('active', '=', True),
                ('is_default', '=', False),
            ], limit=1)
            if domain:
                return domain
        return self.get_default()

    def action_view_versions(self):
        """Open API versions filtered to this domain."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('API Versions'),
            'res_model': 'core.api.version',
            'view_mode': 'list,form',
            'domain': [('domain_id', '=', self.id)],
            'context': {'default_domain_id': self.id},
        }
