# Part of T4 Core API. See LICENSE file for full copyright and licensing details.
import logging

from werkzeug.exceptions import NotFound

from odoo import http
from odoo.http import request

from odoo.addons.t4_coreapi.controllers.base import CoreApiController
from odoo.addons.t4_coreapi.utils import (
    log_core_api,
    get_context,
)

_logger = logging.getLogger(__name__)


class CoreApiProxyController(CoreApiController):
    """HTTP gateway: validate token, then run the matching server action."""

    @http.route(
        '/api/<path:subpath>',
        type='http',
        auth='core_api',
        methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE'],
        csrf=False,
        save_session=False,
    )
    @log_core_api('api')
    def gateway(self, subpath, **kw):
        """Handle all /api/* routes for authenticated applications."""
        Version = request.env['core.api.version'].sudo()
        version, rest = Version.resolve_from_api_subpath(subpath)
        if not version:
            raise NotFound('Unknown or inactive API route.')

        if rest == 'auth/token' or rest.startswith('auth/token/'):
            raise NotFound('Use POST on the dedicated auth endpoint for token requests.')

        path = f'{version.path_prefix.rstrip("/")}/{rest}'.rstrip('/') if rest else version.path_prefix.rstrip('/')
        application = self._get_application()

        ctx = get_context(
            kw,
            request.httprequest.get_data(),
        )

        return request.env['core.api.endpoint'].with_context(
            **ctx,
        ).dispatch_request(path, application)
