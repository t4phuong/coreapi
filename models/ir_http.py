# Part of T4 Core API. See LICENSE file for full copyright and licensing details.

import re

from werkzeug.exceptions import TooManyRequests, Unauthorized

from odoo import models
from odoo.http import request

from odoo.addons.t4_coreapi.utils.security import get_client_ip


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    @classmethod
    def _extract_bearer_token(cls):
        header = request.httprequest.headers.get('Authorization')
        if header and (m := re.match(r'^bearer\s+(.+)$', header, re.IGNORECASE)):
            return m.group(1).strip()
        return None

    @classmethod
    def _auth_method_core_api(cls):
        """Gatekeeper: validate application bearer token before controller runs."""
        token = cls._extract_bearer_token()
        if not token:
            raise Unauthorized(
                'Missing Authorization: Bearer <token>',
                www_authenticate='Bearer realm="Core API"',
            )

        application, token_rec = request.env['core.api.token'].sudo().authenticate(token)
        if not application:
            raise Unauthorized(
                'Invalid or expired access token',
                www_authenticate='Bearer realm="Core API"',
            )

        ip = get_client_ip()
        try:
            application.check_ip_allowed(ip)
            application.check_api_rate_limit()
        except Exception as e:
            if 'rate limit' in str(e).lower():
                raise TooManyRequests(str(e)) from e
            raise

        request.update_env(user=request.env.ref('base.public_user').id)
        request.update_context(
            core_api_application_id=application.id,
            core_api_token_id=token_rec.id,
            core_api_client_id=application.client_id,
        )
        request.session.can_save = False

    @classmethod
    def _auth_method_validate_core_api(cls):
        """Alias auth method — same gatekeeper as core_api."""
        cls._auth_method_core_api()
