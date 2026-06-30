# Part of T4 Core API. See LICENSE file for full copyright and licensing details.

import json
import logging
import re

from werkzeug.exceptions import BadRequest, NotFound

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError
from odoo.http import request

from odoo.addons.t4_coreapi.utils.exception import (
    CoreApiBadRequest,
    CoreApiInvalidBody,
)
from odoo.addons.t4_coreapi.utils.response import (
    api_error_response,
    make_json_response,
    normalize_gateway_response,
)

_logger = logging.getLogger(__name__)

_ROUTE_PATTERN_RE = re.compile(r'^/api/([^/]+)(?:/(.*))?$')


class CoreApiEndpoint(models.Model):
    _name = 'core.api.endpoint'
    _description = 'Core API Gateway Route'
    _order = 'version_id, route_suffix, code'

    name = fields.Char(required=True, translate=True)
    code = fields.Char(
        required=True,
        index=True,
        help='Unique route code per application and API version. Used in logs and API context.',
    )
    version_id = fields.Many2one(
        'core.api.version',
        string='API Version',
        required=True,
        ondelete='restrict',
        index=True,
    )
    route_suffix = fields.Char(
        string='Route Path',
        required=True,
        help='Path after the version prefix, e.g. orders or orders/create.',
    )
    route_pattern = fields.Char(
        string='Full Gateway URL',
        compute='_compute_route_pattern',
        store=True,
        readonly=True,
        help='Computed public route, e.g. /api/v1/orders.',
    )
    http_methods = fields.Char(
        string='Allowed Methods',
        default='GET,POST,PUT,PATCH,DELETE',
        help='Comma-separated HTTP methods applications may use.',
    )
    action_id = fields.Many2one(
        'ir.actions.server',
        string='Server Action',
        help='Executed after auth check. Use env.context core_api_* keys in the action.',
    )
    description = fields.Text(translate=True)
    active = fields.Boolean(default=True)
    application_id = fields.Many2one(
        'core.api.application',
        string='Application',
        ondelete='cascade',
        index=True,
    )
    version_tab_id = fields.Many2one(
        'core.api.application.version.tab',
        string='Version Route Tab',
        ondelete='cascade',
        index=True,
    )

    _code_unique_per_application_version = models.Constraint(
        'unique(application_id, version_id, code)',
        'Endpoint code must be unique per application and API version.',
    )
    _route_unique_per_application_version = models.Constraint(
        'unique(application_id, version_id, route_suffix)',
        'Route path must be unique per application and API version.',
    )

    @api.depends('version_id.path_prefix', 'route_suffix')
    def _compute_route_pattern(self):
        """Build the full public URL from version prefix and route suffix."""
        for endpoint in self:
            prefix = (endpoint.version_id.path_prefix or '/api').rstrip('/')
            suffix = (endpoint.route_suffix or '').strip().strip('/')
            endpoint.route_pattern = f'{prefix}/{suffix}' if suffix else prefix

    @api.constrains('version_tab_id', 'application_id', 'version_id')
    def _check_version_tab(self):
        """Keep the version tab aligned with the route application and version."""
        for endpoint in self:
            tab = endpoint.version_tab_id
            if not tab:
                continue
            if tab.application_id != endpoint.application_id:
                raise ValidationError(_(
                    'Route tab application does not match the route application.'
                ))
            if tab.version_id != endpoint.version_id:
                raise ValidationError(_(
                    'Route tab API version does not match the route API version.'
                ))

    @api.constrains('application_id', 'version_id')
    def _check_version_domain(self):
        """Ensure the route version belongs to the application's host domain."""
        for endpoint in self:
            if not endpoint.application_id or not endpoint.version_id:
                continue
            if endpoint.version_id.domain_id != endpoint.application_id.domain_id:
                raise ValidationError(_(
                    'API version "%(version)s" does not belong to host domain "%(domain)s".',
                    version=endpoint.version_id.display_name,
                    domain=endpoint.application_id.domain_id.display_name,
                ))

    @api.constrains('application_id')
    def _check_application_id(self):
        """Block saving a route that is not linked to an application."""
        for endpoint in self:
            if not endpoint.application_id:
                raise ValidationError(
                    _('Each gateway route must belong to an application.')
                )

    @api.constrains('route_suffix')
    def _check_route_suffix(self):
        """Reject empty route paths."""
        for endpoint in self:
            if not (endpoint.route_suffix or '').strip().strip('/'):
                raise ValidationError(_('Route path is required.'))

    @api.model
    def _version_id_from_context(self, application_id=None):
        """Resolve API version from x2many context (tab-specific defaults)."""
        Version = self.env['core.api.version']
        default_version_id = self.env.context.get('default_version_id')
        if default_version_id:
            version = Version.browse(default_version_id).exists()
            if version:
                return version.id

        version_code = self.env.context.get('default_version_code')
        if not version_code:
            return False

        domain = [('code', '=', version_code), ('active', '=', True)]
        default_domain_id = self.env.context.get('default_domain_id')
        if default_domain_id:
            domain.append(('domain_id', '=', default_domain_id))
        elif application_id:
            app = self.env['core.api.application'].browse(application_id)
            if app.domain_id:
                domain.append(('domain_id', '=', app.domain_id.id))
        version = Version.search(domain, limit=1)
        return version.id if version else False

    @api.model
    def _assign_version_tab(self, vals):
        """Link a route to the correct per-version tab on its application."""
        tab_id = vals.get('version_tab_id') or self.env.context.get('default_version_tab_id')
        application_id = vals.get('application_id') or self.env.context.get('default_application_id')
        version_id = vals.get('version_id') or self._version_id_from_context(
            application_id=application_id,
        )
        if not tab_id and application_id and version_id:
            tab = self.env['core.api.application.version.tab'].get_or_create(
                application_id, version_id,
            )
            tab_id = tab.id
        if tab_id:
            tab = self.env['core.api.application.version.tab'].browse(tab_id).exists()
            if tab:
                vals['version_tab_id'] = tab.id
                vals.setdefault('application_id', tab.application_id.id)
                vals.setdefault('version_id', tab.version_id.id)
        return vals

    @api.model
    def default_get(self, fields_list):
        """Apply tab context so new inline rows get the correct API version."""
        defaults = super().default_get(fields_list)
        if 'version_id' not in fields_list:
            return defaults
        application_id = (
            defaults.get('application_id')
            or self.env.context.get('default_application_id')
        )
        version_id = self._version_id_from_context(application_id=application_id)
        if version_id:
            defaults['version_id'] = version_id
        elif not defaults.get('version_id'):
            default_version = self.env['core.api.version'].get_default_version()
            if default_version:
                defaults['version_id'] = default_version.id
        return defaults

    @api.model_create_multi
    def create(self, vals_list):
        """Fill application_id, version_id, and version tab from form context."""
        prepared = []
        for vals in vals_list:
            vals = dict(vals)
            if not vals.get('application_id'):
                default_app = self.env.context.get('default_application_id')
                if default_app:
                    vals['application_id'] = default_app
            vals = self._assign_version_tab(vals)
            if not vals.get('version_id'):
                version_id = self._version_id_from_context(
                    application_id=vals.get('application_id'),
                )
                if version_id:
                    vals['version_id'] = version_id
                    vals = self._assign_version_tab(vals)
                elif not vals.get('version_id'):
                    default_version = self.env['core.api.version'].get_default_version()
                    if default_version:
                        vals['version_id'] = default_version.id
                        vals = self._assign_version_tab(vals)
            prepared.append(vals)
        return super().create(prepared)

    @api.model
    def _migrate_link_version_tabs(self):
        """Attach existing routes to per-version application tabs."""
        Application = self.env['core.api.application'].sudo()
        for app in Application.search([]):
            app._ensure_version_tabs()
            for endpoint in app.endpoint_ids:
                tab = app.version_tab_ids.filtered(
                    lambda t: t.version_id == endpoint.version_id
                )[:1]
                if tab and endpoint.version_tab_id != tab:
                    endpoint.version_tab_id = tab.id

    @api.model
    def _normalize_route_suffix(self, suffix):
        """Return a canonical route suffix without leading or trailing slashes."""
        return (suffix or '').strip().strip('/')

    @api.model
    def _migrate_legacy_route_fields(self):
        """Parse stored route_pattern values into version_id and route_suffix."""
        Version = self.env['core.api.version'].sudo()
        default_version = Version.get_default_version()
        if not default_version:
            return

        self.env.cr.execute(
            """
            SELECT id, route_pattern
            FROM core_api_endpoint
            WHERE route_suffix IS NULL
               OR route_suffix = ''
               OR version_id IS NULL
            """
        )
        rows = self.env.cr.fetchall()
        for endpoint_id, pattern in rows:
            pattern = (pattern or '').split('?')[0].rstrip('/') or '/'
            version = default_version
            suffix = ''

            match = _ROUTE_PATTERN_RE.match(pattern)
            if match:
                version = Version.search([('code', '=', match.group(1))], limit=1) or default_version
                suffix = self._normalize_route_suffix(match.group(2))
            elif pattern.startswith('/api/'):
                suffix = self._normalize_route_suffix(pattern[5:])
            else:
                suffix = self._normalize_route_suffix(pattern)

            endpoint = self.browse(endpoint_id)
            if not suffix:
                suffix = endpoint.code or 'route'

            endpoint.write({
                'version_id': version.id,
                'route_suffix': suffix,
            })

    def _parsed_methods(self):
        """Return the list of allowed HTTP methods for this route."""
        self.ensure_one()
        raw = (self.http_methods or 'GET').upper().replace(' ', '')
        return [m for m in raw.split(',') if m]

    def allows_method(self, method):
        """Return True when the given HTTP method is allowed on this route."""
        self.ensure_one()
        allowed = self._parsed_methods()
        return not allowed or (method or '').upper() in allowed

    @api.model
    def find_for_request(self, path, method, application=None):
        """Find the best matching active route for path, method, and application."""
        normalized = (path or '').split('?')[0].rstrip('/') or '/'
        method = (method or 'GET').upper()
        domain = [('active', '=', True), ('version_id.active', '=', True)]
        if application:
            domain.append(('application_id', '=', application.id))
        candidates = []
        for endpoint in self.sudo().search(domain):
            pattern = (endpoint.route_pattern or '').rstrip('/') or '/'
            if normalized == pattern or normalized.startswith(f'{pattern}/'):
                if endpoint.allows_method(method):
                    candidates.append((len(pattern), endpoint))
        if not candidates:
            return self.browse()
        candidates.sort(key=lambda item: item[0], reverse=True)
        return candidates[0][1]

    def _parse_request_body(self, httprequest):
        """Parse JSON body from the incoming HTTP request."""
        raw = httprequest.get_data(as_text=True) or ''
        if not raw.strip():
            return {}
        if raw.strip().startswith(('{', '[')):
            try:
                return json.loads(raw)
            except json.JSONDecodeError as e:
                raise CoreApiInvalidBody('Invalid JSON body.') from e
        return raw

    def _server_action_context(self, application, httprequest):
        """Build the context dict passed to the linked server action."""
        self.ensure_one()
        ctx = {
            'core_api_application_id': application.id,
            'core_api_method': httprequest.method,
            'core_api_route': self.route_pattern,
            'core_api_endpoint_id': self.id,
            'core_api_endpoint_code': self.code,
            'core_api_version_id': self.version_id.id,
            'core_api_version_code': self.version_id.code,
            'core_api_body': self._parse_request_body(httprequest),
            'core_api_params': dict(httprequest.args),
        }
        action_model = self.action_id.model_id.model
        if action_model == 'core.api.application':
            ctx.update({
                'active_model': application._name,
                'active_id': application.id,
                'active_ids': application.ids,
            })
        else:
            ctx.update({
                'active_model': action_model,
                'active_id': False,
                'active_ids': [],
            })
        return ctx

    def _run_server_action(self, application, httprequest):
        """Execute the linked server action and return a JSON HTTP response."""
        self.ensure_one()
        if not self.action_id:
            raise ValidationError(_(
                'Gateway route "%s" has no Server Action configured.', self.name
            ))

        request.core_api_response = None
        ctx = self._server_action_context(application, httprequest)
        self.action_id.sudo().with_context(**ctx).run()

        response_data = getattr(request, 'core_api_response', None)
        status_code, payload = normalize_gateway_response(response_data)
        return make_json_response(payload, status_code)

    def _error_response(self, message, status=400):
        return api_error_response(message, status_code=status)

    def dispatch(self, application):
        """Validate access and run this route for the authenticated application."""
        self.ensure_one()
        try:
            if application:
                if self.application_id != application:
                    raise AccessError(_(
                        'Gateway route "%(route)s" does not belong to application "%(app)s".',
                        route=self.name, app=application.name,
                    ))
                application.check_api_access(self.code, version_id=self.version_id.id)
            return self._run_server_action(application, request.httprequest)
        except CoreApiBadRequest as e:
            return self._error_response(str(e), 400)
        except BadRequest as e:
            return self._error_response(e.description or str(e), 400)
        except ValidationError as e:
            return self._error_response(str(e), 400)


    @api.model
    def dispatch_request(self, path, application):
        """Entry point from the HTTP gateway controller."""
        endpoint = self.find_for_request(
            path, request.httprequest.method, application=application,
        )
        if not endpoint:
            raise NotFound(f'No gateway route configured for: {path}.')
        return endpoint.dispatch(application)
