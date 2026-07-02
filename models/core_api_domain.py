# Part of T4 Core API. See LICENSE file for full copyright and licensing details.

import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.http import request

_HOSTNAME_RE = re.compile(
    r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,63}$'
    r'|^(?:\d{1,3}\.){3}\d{1,3}$'
    r'|^localhost$'
)


class CoreApiDomain(models.Model):
    _name = 'core.api.domain'
    _description = 'API Host Domain'
    _order = 'sequence, name'

    name = fields.Char(required=True)
    hostname = fields.Char(
        string='Hostname',
        help='Public hostname clients use in the URL, e.g. ashaf.xyz. '
             'Leave empty on the default domain to match any host.',
    )
    base_url = fields.Char(
        string='Public Base URL',
        compute='_compute_base_url',
        help='Scheme + host used in integration examples (no service or version path).',
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    is_default = fields.Boolean(
        string='Default Domain',
        default=False,
        help='Used when the HTTP Host header does not match any configured hostname.',
    )
    description = fields.Text()

    _hostname_unique = models.Constraint(
        'unique(hostname)',
        'Hostname must be unique (empty hostname is allowed only once for the default domain).',
    )

    @api.depends('hostname')
    def _compute_base_url(self):
        """Build the public origin URL from web.base.url and optional hostname."""
        web_base = (self.env['ir.config_parameter'].sudo().get_param('web.base.url') or '').rstrip('/')
        for rec in self:
            if rec.hostname:
                parsed = re.match(r'^(https?)://([^/]+)', web_base)
                scheme = parsed.group(1) if parsed else 'https'
                rec.base_url = f'{scheme}://{rec.hostname.strip()}'
            else:
                rec.base_url = web_base

    @api.constrains('hostname')
    def _check_hostname(self):
        """Validate hostname format when set."""
        for rec in self:
            host = (rec.hostname or '').strip()
            if not host:
                continue
            if not _HOSTNAME_RE.match(host):
                raise ValidationError(_(
                    'Invalid hostname "%(host)s". Use a domain like ashaf.xyz or localhost.',
                    host=host,
                ))

    @api.constrains('is_default')
    def _check_single_default(self):
        """Allow only one default host domain."""
        for rec in self.filtered('is_default'):
            other = self.search([
                ('is_default', '=', True),
                ('id', '!=', rec.id),
            ], limit=1)
            if other:
                raise ValidationError(_(
                    'Only one default API host domain is allowed (already: "%s").',
                    other.name,
                ))

    @api.model
    def get_default(self):
        """Return the default host domain record."""
        domain = self.search([('is_default', '=', True)], limit=1)
        if domain:
            return domain
        return self.search([], order='sequence, id', limit=1)

    @api.model
    def get_from_request(self, httprequest=None):
        """Resolve host domain from the HTTP Host header."""
        req = httprequest or (request.httprequest if request else None)
        host = ''
        if req:
            host = (req.host or '').split(':')[0].strip().lower()
        if host:
            matched = self.sudo().search([
                ('hostname', '!=', False),
                ('hostname', 'ilike', host),
                ('active', '=', True),
            ], limit=1)
            if matched:
                return matched
        return self.sudo().get_default()
