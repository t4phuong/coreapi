# Part of T4 Core API. See LICENSE file for full copyright and licensing details.

import logging
import secrets

from passlib.context import CryptContext

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.http import request

_logger = logging.getLogger(__name__)

SECRET_CRYPT_CONTEXT = CryptContext(['pbkdf2_sha512'], pbkdf2_sha512__rounds=6000)


class CoreApiApplication(models.Model):
    _name = 'core.api.application'
    _description = 'External API Application'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(required=True, tracking=True)
    client_id = fields.Char(
        string='Client ID',
        required=False,
        copy=False,
        readonly=True,
        index=True,
        tracking=True,
        help='Auto-generated when the application is saved.',
    )
    client_secret = fields.Char(
        string='Client Secret (hashed)',
        copy=False,
        readonly=True,
        groups='base.group_system',
    )
    state = fields.Selection(
        [('active', 'Active'), ('inactive', 'Inactive')],
        string='Status',
        default='active',
        required=True,
        tracking=True,
    )
    active = fields.Boolean(default=True, compute='_compute_active', store=True)
    token_ttl_hours = fields.Integer(
        string='Access Token TTL (hours)',
        default=24,
        help='Lifetime of issued access tokens. 0 = non-expiring (not recommended).',
    )
    refresh_token_ttl_hours = fields.Integer(
        string='Refresh Token TTL (hours)',
        default=168,
        help='Lifetime of refresh tokens. When both access and refresh tokens expire, '
             'the application must authenticate again with client credentials. 0 = non-expiring.',
    )
    token_ids = fields.One2many('core.api.token', 'application_id')
    token_count = fields.Integer(compute='_compute_token_count')
    active_token_id = fields.Many2one(
        'core.api.token',
        string='Current Token',
        compute='_compute_active_token',
        store=False,
    )
    token_expiration = fields.Datetime(
        string='Token Expires',
        related='active_token_id.expiration_date',
        readonly=True,
    )
    credentials_pending = fields.Boolean(
        string='Credentials Not Yet Viewed',
        default=False,
        copy=False,
        readonly=True,
    )
    domain_id = fields.Many2one(
        'core.api.domain',
        string='Host Domain',
        required=True,
        default=lambda self: self.env['core.api.domain'].get_default().id,
        tracking=True,
        help='Public hostname group for this application. API versions and routes belong to this host.',
    )
    default_version_id = fields.Many2one(
        'core.api.version',
        string='Default API Version',
        domain="[('domain_id', '=', domain_id), ('active', '=', True)]",
        help='The only API version this application may call. '
             'Routes on other versions can be prepared in the form but are blocked at runtime.',
    )
    domain_version_count = fields.Integer(
        compute='_compute_domain_version_count',
        string='Active API Versions on Domain',
    )
    endpoint_ids = fields.One2many(
        'core.api.endpoint',
        'application_id',
        string='Gateway Routes',
        help='All API routes owned by this application.',
    )
    version_tab_ids = fields.One2many(
        'core.api.application.version.tab',
        'application_id',
        string='Version Route Tabs',
    )
    rate_limit_per_minute = fields.Integer(
        string='API Rate Limit (/min)',
        default=60,
        help='Max API calls per minute. 0 = unlimited.',
    )
    auth_rate_limit_per_minute = fields.Integer(
        string='Auth Rate Limit (/min)',
        default=10,
        help='Max token requests per minute. 0 = unlimited.',
    )
    allowed_ips = fields.Text(
        string='Allowed IPs',
        help='One IP or CIDR per line. Empty = allow any IP.',
    )
    log_ids = fields.One2many('core.api.log', 'application_id')
    log_count = fields.Integer(compute='_compute_log_count')
    last_auth_at = fields.Datetime(readonly=True)
    last_auth_ip = fields.Char(readonly=True)
    notes = fields.Text()
    api_base_url = fields.Char(
        string='API Base URL',
        compute='_compute_api_integration_guide',
    )
    auth_endpoint_url = fields.Char(
        string='Token URL',
        compute='_compute_api_integration_guide',
    )
    auth_curl_example = fields.Text(
        string='Token Request (cURL)',
        compute='_compute_api_integration_guide',
    )
    api_call_curl_example = fields.Text(
        string='API Call (cURL)',
        compute='_compute_api_integration_guide',
    )
    api_database_name = fields.Char(
        string='Database Name',
        compute='_compute_api_integration_guide',
        help='PostgreSQL database name. Required for external API calls when multiple databases exist.',
    )

    _client_id_unique = models.Constraint('unique(client_id)', 'Client ID must be unique.')

    @api.depends('domain_id', 'domain_id.version_ids', 'domain_id.version_ids.active')
    def _compute_domain_version_count(self):
        """Count active API versions on the application's host domain."""
        for rec in self:
            rec.domain_version_count = len(rec.domain_id.version_ids.filtered('active'))

    def _ensure_version_tabs(self):
        """Create one route tab per active API version on the application's domain."""
        Tab = self.env['core.api.application.version.tab']
        for app in self:
            if not app.id or not app.domain_id:
                continue
            versions = app.domain_id.version_ids.filtered('active')
            existing = {tab.version_id.id: tab for tab in app.version_tab_ids}
            for version in versions:
                if version.id not in existing:
                    Tab.create({
                        'application_id': app.id,
                        'version_id': version.id,
                    })
            stale_tabs = app.version_tab_ids.filtered(lambda t: t.version_id not in versions)
            if stale_tabs:
                stale_tabs.unlink()

    @api.model
    def _ensure_version_tabs_all(self):
        """Create route tabs for every saved application (upgrade hook)."""
        self.search([])._ensure_version_tabs()

    @api.onchange('domain_id')
    def _onchange_domain_id(self):
        """Clear routes and reset default version when the host domain changes."""
        self.endpoint_ids = [(5, 0, 0)]
        self.version_tab_ids = [(5, 0, 0)]
        versions = self.domain_id.version_ids.filtered('active').sorted('sequence')
        self.default_version_id = versions[:1]
        result = {
            'domain': {
                'default_version_id': [('domain_id', '=', self.domain_id.id), ('active', '=', True)],
            },
        }
        if self.domain_id and not versions:
            result['warning'] = {
                'title': _('No API versions'),
                'message': _(
                    'Host domain "%(domain)s" has no API versions. '
                    'Create them on the domain first.',
                    domain=self.domain_id.display_name,
                ),
            }
        return result

    def write(self, vals):
        """Remove all routes when the host domain changes on a saved application."""
        if 'domain_id' in vals:
            for rec in self:
                if rec.domain_id.id != vals['domain_id']:
                    rec.endpoint_ids.unlink()
                    rec.version_tab_ids.unlink()
            if len(self) == 1 and 'default_version_id' not in vals:
                version = self.env['core.api.version'].search([
                    ('domain_id', '=', vals['domain_id']),
                    ('active', '=', True),
                ], order='sequence', limit=1)
                if version:
                    vals['default_version_id'] = version.id
        result = super().write(vals)
        if 'domain_id' in vals:
            self._ensure_version_tabs()
        return result

    @api.model
    def default_get(self, fields_list):
        """Pre-fill default API version from the default host domain."""
        defaults = super().default_get(fields_list)
        domain = self.env['core.api.domain'].browse(defaults.get('domain_id'))
        if not domain:
            domain = self.env['core.api.domain'].get_default()
            if domain and 'domain_id' in fields_list:
                defaults['domain_id'] = domain.id
        if 'default_version_id' in fields_list and not defaults.get('default_version_id') and domain:
            version = domain.version_ids.filtered('active').sorted('sequence')[:1]
            if not version:
                version = self.env['core.api.version'].get_default_version()
            if version and version.domain_id == domain:
                defaults['default_version_id'] = version.id
        return defaults

    @api.depends('state')
    def _compute_active(self):
        """Mirror application state into the active boolean field."""
        for rec in self:
            rec.active = rec.state == 'active'

    @api.depends('token_ids')
    def _compute_token_count(self):
        """Count issued tokens for the application stat button."""
        for rec in self:
            rec.token_count = len(rec.token_ids)

    @api.depends('log_ids')
    def _compute_log_count(self):
        """Count request logs for the application stat button."""
        for rec in self:
            rec.log_count = len(rec.log_ids)

    @api.depends(
        'client_id',
        'domain_id',
        'domain_id.base_url',
        'default_version_id',
        'default_version_id.code',
        'default_version_id.path_prefix',
        'default_version_id.public_base_url',
        'default_version_id.domain_id.base_url',
        'endpoint_ids.route_pattern',
        'endpoint_ids.version_id',
    )
    def _compute_api_integration_guide(self):
        """Build auth URLs and cURL samples shown on the application form."""
        for rec in self:
            version = rec.default_version_id
            if not version or version.domain_id != rec.domain_id:
                version = rec.domain_id.version_ids.filtered('active').sorted('sequence')[:1]
            if not version:
                version = self.env['core.api.version'].get_default_version()
            version_public = (version.public_base_url if version else '').rstrip('/')
            if not version_public:
                version_public = (
                    self.env['ir.config_parameter'].sudo().get_param('web.base.url') or ''
                ).rstrip('/')
                if version:
                    version_public = f'{version_public}{(version.path_prefix or "/api/v1").rstrip("/")}'
            auth_url = f'{version_public}/auth/token'
            db_name = self.env.cr.dbname
            rec.api_database_name = db_name
            rec.api_base_url = version_public
            rec.auth_endpoint_url = auth_url
            client_id = rec.client_id or '<client_id>'
            rec.auth_curl_example = (
                f'# 1) Initial login — send client_id/secret once\n'
                f'curl -X POST "{auth_url}?db={db_name}" \\\n'
                f'  -H "Content-Type: application/json" \\\n'
                f'  -H "X-Odoo-Database: {db_name}" \\\n'
                f'  -d \'{{"grant_type": "client_credentials", '
                f'"client_id": "{client_id}", '
                f'"client_secret": "<client_secret>"}}\'\n\n'
                f'# Response: status, message, api_token, refresh_token\n\n'
                f'# 2) When access_token expires — refresh without client_secret\n'
                f'curl -X POST "{auth_url}?db={db_name}" \\\n'
                f'  -H "Content-Type: application/json" \\\n'
                f'  -H "X-Odoo-Database: {db_name}" \\\n'
                f'  -d \'{{"grant_type": "refresh_token", '
                f'"refresh_token": "<refresh_token>"}}\''
            )
            sample_endpoints = rec.endpoint_ids.filtered(
                lambda e: not version or e.version_id == version
            ) or rec.endpoint_ids
            sample_suffix = (
                sample_endpoints[:1].route_suffix if sample_endpoints else 'your-route'
            )
            sample_url = f'{version_public}/{sample_suffix}?db={db_name}'
            rec.api_call_curl_example = (
                f'curl -X GET "{sample_url}" \\\n'
                f'  -H "Authorization: Bearer <access_token>" \\\n'
                f'  -H "Content-Type: application/json" \\\n'
                f'  -H "X-Odoo-Database: {db_name}"'
            )

    @api.depends('token_ids.active', 'token_ids.expiration_date', 'token_ids.token_type')
    def _compute_active_token(self):
        """Pick the current valid access token for display on the application form."""
        now = fields.Datetime.now()
        for rec in self:
            token = rec.token_ids.filtered(
                lambda t: t.token_type == 'access'
                and t.active
                and (not t.expiration_date or t.expiration_date >= now)
            )[:1]
            rec.active_token_id = token

    @api.model_create_multi
    def create(self, vals_list):
        """Generate client credentials when a new application is created."""
        prepared = []
        for vals in vals_list:
            vals = dict(vals)
            plaintext_secret = vals.pop('plaintext_client_secret', None)
            if not vals.get('client_id'):
                vals['client_id'] = self._generate_client_id()
            if plaintext_secret:
                vals['client_secret'] = SECRET_CRYPT_CONTEXT.hash(plaintext_secret)
            elif not vals.get('client_secret'):
                plaintext_secret = secrets.token_urlsafe(32)
                vals['client_secret'] = SECRET_CRYPT_CONTEXT.hash(plaintext_secret)
            else:
                plaintext_secret = None
            prepared.append((vals, plaintext_secret))
        records = super().create([v for v, _ in prepared])
        records._ensure_version_tabs()
        for record, (_, plaintext_secret) in zip(records, prepared):
            if not record.client_id:
                record.sudo().write({'client_id': self._generate_client_id()})
            if plaintext_secret:
                record._store_pending_secret(plaintext_secret)
                record.sudo().write({'credentials_pending': True})
                record._notify_application_form_reload()
        return records

    @api.model
    def _generate_client_id(self):
        """Return a unique client_id value for a new application."""
        return f'app_{secrets.token_hex(16)}'

    def _store_pending_secret(self, plaintext_secret):
        """Keep the plaintext secret in the user session until the wizard opens."""
        self.ensure_one()
        if request and getattr(request, 'session', None) is not None:
            pending = dict(request.session.get('core_api_application_secrets', {}))
            pending[str(self.id)] = plaintext_secret
            request.session['core_api_application_secrets'] = pending

    def _pop_pending_secret(self):
        """Read and remove the plaintext secret from the user session."""
        self.ensure_one()
        if request and getattr(request, 'session', None) is not None:
            pending = dict(request.session.get('core_api_application_secrets', {}))
            return pending.pop(str(self.id), None)
        return None

    def _clear_pending_secret(self):
        """Discard any pending plaintext secret from the user session."""
        self.ensure_one()
        if request and getattr(request, 'session', None) is not None:
            pending = dict(request.session.get('core_api_application_secrets', {}))
            pending.pop(str(self.id), None)
            request.session['core_api_application_secrets'] = pending

    def _notify_application_form_reload(self):
        """Ask open application forms to reload after credential state changes."""
        self.ensure_one()
        self.env['bus.bus']._sendone(
            'broadcast',
            'core_api_application_reload',
            {'application_id': self.id},
        )

    def _open_secret_wizard(self, plaintext_secret):
        """Open the one-time credentials popup for the current application."""
        self.ensure_one()
        wizard = self.env['core.api.application.secret.wizard'].create({
            'application_id': self.id,
            'client_id': self.client_id,
            'client_secret': plaintext_secret,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Application Credentials'),
            'res_model': 'core.api.application.secret.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_view_credentials(self):
        """Show credentials once after create when they are still in session."""
        self.ensure_one()
        if not self.credentials_pending:
            raise UserError(_('Client secret was already displayed. Use "Regenerate Secret" if needed.'))
        plaintext = self._pop_pending_secret()
        if not plaintext:
            raise UserError(_(
                'Credentials are no longer available in this session. '
                'Use "Regenerate Secret" to issue new credentials.'
            ))
        return self._open_secret_wizard(plaintext)

    def action_regenerate_secret(self):
        """Issue a new client secret and show it in the credentials wizard."""
        self.ensure_one()
        if self.state != 'active':
            raise UserError(_('Cannot regenerate secret for an inactive application.'))
        plaintext = secrets.token_urlsafe(32)
        self.sudo().write({
            'client_secret': SECRET_CRYPT_CONTEXT.hash(plaintext),
            'credentials_pending': True,
        })
        self._store_pending_secret(plaintext)
        self._notify_application_form_reload()
        return self._open_secret_wizard(plaintext)

    def action_set_active(self):
        """Activate the application from the form header."""
        self.write({'state': 'active'})

    def action_set_inactive(self):
        """Deactivate the application from the form header."""
        self.write({'state': 'inactive'})

    def action_revoke_token(self):
        """Revoke the current active token for this application."""
        self.ensure_one()
        token = self.active_token_id
        if not token:
            raise UserError(_('No active token to revoke.'))
        token.action_revoke()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Token Revoked'),
                'message': _('The active token for application "%s" has been revoked.', self.name),
                'type': 'warning',
                'sticky': False,
            },
        }

    def action_view_tokens(self):
        """Open the token list filtered to this application."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Tokens'),
            'res_model': 'core.api.token',
            'view_mode': 'list,form',
            'domain': [('application_id', '=', self.id)],
            'context': {'default_application_id': self.id},
        }

    def action_view_logs(self):
        """Open the request log list filtered to this application."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Request Logs'),
            'res_model': 'core.api.log',
            'view_mode': 'list,form',
            'domain': [('application_id', '=', self.id)],
        }

    @api.model
    def set_api_response(self, data):
        """Call from any Server Action to return JSON to the API client."""
        request.core_api_response = data

    def get_api_context(self):
        """Return request data injected by the gateway for server action code."""
        self.ensure_one()
        ctx = self.env.context
        return {
            'method': ctx.get('core_api_method'),
            'route': ctx.get('core_api_route'),
            'endpoint_code': ctx.get('core_api_endpoint_code'),
            'body': ctx.get('core_api_body') or {},
            'params': ctx.get('core_api_params') or {},
        }

    def check_ip_allowed(self, ip_address):
        """Raise AccessError when the client IP is not in the allowlist."""
        self.ensure_one()
        from odoo.addons.t4_coreapi.utils.security import check_ip_allowed
        if not check_ip_allowed(self.allowed_ips, ip_address):
            raise AccessError(
                _('IP address %(ip)s is not allowed for application "%(app)s".',
                  ip=ip_address, app=self.name)
            )
        return True

    def check_api_rate_limit(self):
        """Raise AccessError when API rate limit is exceeded."""
        from odoo.addons.t4_coreapi.utils.security import check_application_api_rate_limit
        check_application_api_rate_limit(self)
        return True

    def check_auth_rate_limit(self):
        """Raise AccessError when auth rate limit is exceeded."""
        from odoo.addons.t4_coreapi.utils.security import check_application_auth_rate_limit
        check_application_auth_rate_limit(self)
        return True

    @api.model
    def authenticate_client(self, client_id, client_secret, ip_address=None):
        """Validate client credentials. Returns application or empty recordset."""
        application, _error = self.authenticate_client_with_reason(
            client_id, client_secret, ip_address=ip_address,
        )
        return application

    @api.model
    def authenticate_client_with_reason(self, client_id, client_secret, ip_address=None):
        """Validate client credentials. Returns (application, error_message)."""
        if not (client_id or '').strip():
            return self.browse(), _('client_id is required.')
        if not client_secret:
            return self.browse(), _('client_secret is required.')

        client_id = client_id.strip()
        application = self.sudo().search([('client_id', '=', client_id)], limit=1)
        if not application:
            return self.browse(), _('No application found for the given client_id.')

        if application.state != 'active':
            return self.browse(), _('Application "%s" is inactive.') % application.name

        if not application.client_secret or not SECRET_CRYPT_CONTEXT.verify(
            client_secret, application.client_secret
        ):
            return self.browse(), _('Invalid client_secret for the given client_id.')

        application.write({
            'last_auth_at': fields.Datetime.now(),
            'last_auth_ip': ip_address or False,
        })
        return application, None

    def check_api_access(self, endpoint_code, version_id=None):
        """Raise AccessError when the application cannot call the endpoint code."""
        self.ensure_one()
        if self.state != 'active':
            raise AccessError(_('Application "%s" is inactive.', self.name))
        if version_id and self.default_version_id and version_id != self.default_version_id.id:
            raise AccessError(_(
                'Application "%(app)s" is restricted to API version %(version)s.',
                app=self.name,
                version=self.default_version_id.display_name,
            ))
        endpoints = self.endpoint_ids.filtered(lambda e: e.code == endpoint_code)
        if version_id:
            endpoints = endpoints.filtered(lambda e: e.version_id.id == version_id)
        if not endpoints:
            raise AccessError(
                _('Application "%(app)s" is not allowed to access API: %(endpoint)s',
                  app=self.name, endpoint=endpoint_code)
            )
        return True

    def check_route_access(self, path, method=None):
        """Match request path against allowed endpoint route patterns."""
        self.ensure_one()
        if not self.endpoint_ids:
            raise AccessError(_('Application "%s" has no allowed APIs configured.', self.name))
        normalized = (path or '').split('?')[0].rstrip('/') or '/'
        for endpoint in self.endpoint_ids:
            pattern = (endpoint.route_pattern or '').rstrip('/') or '/'
            if normalized == pattern or normalized.startswith(f'{pattern}/'):
                return endpoint.code
        raise AccessError(
            _('Application "%(app)s" is not allowed to call route: %(route)s',
              app=self.name, route=path)
        )
