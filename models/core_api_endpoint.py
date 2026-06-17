# Part of T4 Core API. See LICENSE file for full copyright and licensing details.

import json
import logging

from werkzeug.exceptions import BadRequest, NotFound

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.http import request

_logger = logging.getLogger(__name__)


class CoreApiEndpoint(models.Model):
    _name = 'core.api.endpoint'
    _description = 'Core API Gateway Route'
    _order = 'route_pattern, code'

    name = fields.Char(required=True, translate=True)
    code = fields.Char(
        required=True,
        index=True,
        help='Unique route code used in logs and API context.',
    )
    route_pattern = fields.Char(
        string='Gateway Route',
        required=True,
        help='Public route on this Odoo server, e.g. /api/v1/orders',
    )
    http_methods = fields.Char(
        string='Allowed Methods',
        default='GET,POST,PUT,PATCH,DELETE',
        help='Comma-separated HTTP methods applications may use.',
    )
    action_id = fields.Many2one(
        'ir.actions.server',
        string='Server Action',
        help='Executed after auth check. Any model — use env.context core_api_* keys.',
    )
    description = fields.Text(translate=True)
    active = fields.Boolean(default=True)

    _code_unique = models.Constraint('unique(code)', 'Endpoint code must be unique.')

    def _parsed_methods(self):
        self.ensure_one()
        raw = (self.http_methods or 'GET').upper().replace(' ', '')
        return [m for m in raw.split(',') if m]

    def allows_method(self, method):
        self.ensure_one()
        allowed = self._parsed_methods()
        return not allowed or (method or '').upper() in allowed

    @api.model
    def find_for_request(self, path, method):
        normalized = (path or '').split('?')[0].rstrip('/') or '/'
        method = (method or 'GET').upper()
        candidates = []
        for endpoint in self.sudo().search([('active', '=', True)]):
            pattern = (endpoint.route_pattern or '').rstrip('/') or '/'
            if normalized == pattern or normalized.startswith(f'{pattern}/'):
                if endpoint.allows_method(method):
                    candidates.append((len(pattern), endpoint))
        if not candidates:
            return self.browse()
        candidates.sort(key=lambda item: item[0], reverse=True)
        return candidates[0][1]

    def _parse_request_body(self, httprequest):
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
        self.ensure_one()
        ctx = {
            'core_api_application_id': application.id,
            'core_api_method': httprequest.method,
            'core_api_route': self.route_pattern,
            'core_api_endpoint_id': self.id,
            'core_api_endpoint_code': self.code,
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
                'message': (
                    'Server action ran but returned no JSON. '
                    'Call env["core.api.application"].set_api_response({...}) in the action code.'
                ),
            }

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

    def dispatch(self, application):
        self.ensure_one()
        if application:
            application.check_api_access(self)
        return self._run_server_action(application, request.httprequest)

    @api.model
    def dispatch_request(self, path, application):
        endpoint = self.find_for_request(path, request.httprequest.method)
        if not endpoint:
            raise NotFound(f'No gateway route configured for: {path}')
        return endpoint.dispatch(application)
