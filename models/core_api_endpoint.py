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
    CoreApiInvalidResponse,
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
        default=lambda self: self.env['core.api.version'].get_default_version().id,
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

    @api.model_create_multi
    def create(self, vals_list):
        """Fill application_id from form context when creating from an application."""
        for vals in vals_list:
            if not vals.get('application_id'):
                default_app = self.env.context.get('default_application_id')
                if default_app:
                    vals['application_id'] = default_app
            if not vals.get('version_id'):
                default_version = self.env.context.get('default_version_id')
                if default_version:
                    vals['version_id'] = default_version
        return super().create(vals_list)

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
                raise BadRequest('Invalid JSON body.') from e
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
        if response_data is None:
            response_data = {
                'status': 'ok',
                'message': "Successful!",
            }
        elif not isinstance(response_data, dict):
            raise CoreApiInvalidResponse(
                _('API response must be a dict. Use set_api_response({...}).')
            )

        status = 200
        if isinstance(response_data, dict):
            payload = dict(response_data)
            if payload.get('status_code'):
                status = int(payload.pop('status_code'))
            response_data = payload

        return request.make_response(
            json.dumps(response_data, default=str),
            headers=[('Content-Type', 'application/json')],
            status=status,
        )

    def _error_response(self, message, status=400):
        return request.make_response(
            json.dumps({'status': 'error', 'message': message}),
            headers=[('Content-Type', 'application/json')],
            status=status,
        )

    def dispatch(self, application):
        """Validate access and run this route for the authenticated application."""
        self.ensure_one()
        # if application:
        #     if self.application_id != application:
        #         raise AccessError(_(
        #             'Gateway route "%(route)s" does not belong to application "%(app)s".',
        #             route=self.name, app=application.name,
        #         ))
        #     application.check_api_access(self.code, version_id=self.version_id.id)
        # return self._run_server_action(application, request.httprequest)
        try:
            if application:
                # application.check_api_access(self.code)
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
            return self._error_response(str(e), 400)
        except ValidationError as e:
            return self._error_response(str(e), 400)


    @api.model
    def dispatch_request(self, path, application):
        """Entry point from the HTTP gateway controller."""
        endpoint = self.find_for_request(
            path, request.httprequest.method, application=application,
        )
        if not endpoint:
            raise NotFound(f'No gateway route configured for: {path}')
        return endpoint.dispatch(application)
