# Part of T4 Core API. See LICENSE file for full copyright and licensing details.

import json
import logging
import time

from werkzeug.exceptions import BadRequest, NotFound, TooManyRequests, Unauthorized

from odoo import http
from odoo.http import request

from odoo.addons.t4_coreapi.utils.security import (
    check_ip_auth_rate_limit,
    get_client_ip,
)

_logger = logging.getLogger(__name__)


class CoreApiAuthController(http.Controller):
    """OAuth2-style client credentials token endpoint."""

    def _log_auth(self, application, route, ip, ua, status_code, success, duration_ms=0, error=None):
        """Write an authentication attempt to core.api.log."""
        request.env['core.api.log'].sudo().log_event(
            event_type='auth',
            route=route,
            method='POST',
            ip_address=ip,
            status_code=status_code,
            success=success,
            application=application,
            duration_ms=duration_ms,
            error_message=error,
            user_agent=ua,
        )

    @http.route(
        '/api/<string:version_code>/auth/token',
        type='http',
        auth='none',
        methods=['POST'],
        csrf=False,
        save_session=False,
    )
    def issue_token(self, version_code, **kw):
        """Exchange client_id and client_secret for a bearer access token."""
        version = request.env['core.api.version'].sudo().get_active_by_code(version_code)
        if not version:
            raise NotFound(f'Unknown or inactive API version: {version_code}')

        auth_route = f'{version.path_prefix.rstrip("/")}/auth/token'
        t0 = time.time()
        ip = get_client_ip()
        ua = request.httprequest.headers.get('User-Agent')
        application = request.env['core.api.application']

        try:
            check_ip_auth_rate_limit(request.env, ip)
        except Exception as e:
            duration = (time.time() - t0) * 1000
            self._log_auth(application, auth_route, ip, ua, 429, False, duration, str(e))
            raise TooManyRequests(str(e)) from e

        try:
            raw = request.httprequest.get_data(as_text=True) or ''
            if request.httprequest.content_type and 'json' in request.httprequest.content_type:
                data = json.loads(raw) if raw else {}
            else:
                data = dict(request.httprequest.form) or (json.loads(raw) if raw else {})
        except json.JSONDecodeError:
            raise BadRequest('Invalid JSON body') from None

        client_id = (data.get('client_id') or kw.get('client_id') or '').strip()
        client_secret = data.get('client_secret') or kw.get('client_secret') or ''
        grant_type = (data.get('grant_type') or kw.get('grant_type') or 'client_credentials').strip()

        if grant_type != 'client_credentials':
            raise BadRequest('Unsupported grant_type. Use client_credentials.')

        candidate = request.env['core.api.application'].sudo().search([
            ('client_id', '=', client_id),
        ], limit=1)
        if candidate:
            try:
                candidate.check_ip_allowed(ip)
                candidate.check_auth_rate_limit()
            except Exception as e:
                duration = (time.time() - t0) * 1000
                self._log_auth(candidate, auth_route, ip, ua, 429 if 'rate limit' in str(e).lower() else 403, False, duration, str(e))
                if 'rate limit' in str(e).lower():
                    raise TooManyRequests(str(e)) from e
                raise

        application = request.env['core.api.application'].sudo().authenticate_client(
            client_id, client_secret, ip_address=ip,
        )
        if not application:
            duration = (time.time() - t0) * 1000
            self._log_auth(candidate, auth_route, ip, ua, 401, False, duration, 'Invalid client credentials')
            _logger.warning('Core API auth failed for client_id=%s from %s', client_id, ip)
            raise Unauthorized('Invalid client credentials')

        plaintext, token_rec = request.env['core.api.token'].sudo().issue_for_application(application)
        expires_in = application.token_ttl_hours * 3600 if application.token_ttl_hours else None
        body = {
            'access_token': plaintext,
            'token_type': 'Bearer',
        }
        if expires_in:
            body['expires_in'] = expires_in
        if token_rec.expiration_date:
            body['expires_at'] = token_rec.expiration_date.isoformat()

        duration = (time.time() - t0) * 1000
        self._log_auth(application, auth_route, ip, ua, 200, True, duration)

        return request.make_response(
            json.dumps(body),
            headers=[('Content-Type', 'application/json')],
            status=200,
        )
