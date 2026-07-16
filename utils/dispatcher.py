# pyrefly: ignore [missing-import]
import json
# pyrefly: ignore [missing-import]
from odoo.http import Response
# pyrefly: ignore [missing-import]
from odoo.http import request
# pyrefly: ignore [missing-import]
from odoo.addons.t4_coreapi.exceptions import (
    APIException,
    APINotFound,
    APIBadRequest,
    APITooManyRequests,
)

from odoo import fields
from dateutil.relativedelta import relativedelta

import logging
_logger = logging.getLogger(__name__)

class CoreApiDispatcher():
    _name = 't4.coreapi.dispatcher'
    _description = 'Core API Dispatcher'

    ########## Service #############
    def _find_service_by_code (self, code):
        service = request.env['t4.coreapi.service'].sudo().search([
            ('code', '=', code)], limit=1)
        if not service:
            raise APINotFound("Service not found!")
        return service
    
    def _find_version_by_route (self, route):
        version = request.env['t4.coreapi.version'].sudo().search([
            ('route', '=', route),
            ('active', '=', True),
        ], limit=1)
        if not version:
            raise APINotFound("Version not found!")
        return version

    def _find_route_by_full_route (self, full_route):
        route = request.env['t4.coreapi.route'].sudo().search([
            ('full_route', '=', full_route),
        ], limit=1)
        if not route:
            raise APINotFound("Route not found!")

        return route   

    ############ Execution ############
    def _check_rate_limit(self, service):
        if not service.is_rate_limit_enabled:
            return

        time_limit = fields.Datetime.now() - relativedelta(minutes=service.rate_limit_period)
        log_count = request.env['t4.coreapi.rate.limit.log'].sudo().search_count([
            ('service_id', '=', service.id),
            ('create_date', '>=', time_limit)
        ])

        if log_count >= service.rate_limit_calls:
            raise APITooManyRequests("Rate limit exceeded.")

        request.env['t4.coreapi.rate.limit.log'].sudo().create({
            'service_id': service.id
        })

    def _execute_required_action(self):
        service = self._find_service_by_code(request.service_info["service_code"])
        self._check_rate_limit(service)
        
        req_actions = service.required_action_ids.sorted(
            lambda x: x.sequence
        )
        for req in req_actions:
            self._execute_api_action(req.api_action_id)

    def _execute_route_action(self):
        service_info = request.service_info

        version = self._find_version_by_route(service_info["version_route"])  
        route = self._find_route_by_full_route(service_info["full_route"])

        if service_info["method"] != route.allow_method:
            raise APIBadRequest(f"Method {service_info['method']} not allowed for this route.")
        
        self._execute_api_action(route.api_action_id)

    def _get_context (self):
        context = {
            "core api": {
                "params": request.params,
                "header": request.httprequest.headers,
                "body": request.httprequest.data,
                "cookies": request.httprequest.cookies,
            },
            **request.env.context,
        }
        return context

    def _execute_api_action(self, api_action):
        if api_action:
            api_action.with_context(
                self._get_context()
            ).run()

    ############ API ############
    def _set_default_response(self):
        self.set_response({
            "message": "default response"
        }, 200)

    def set_response(self, data, status_code=200):
        request.api_response = {
            'data': data,
            'status': status_code,
        }

    def _response(self):
        api_response = request.api_response
        response_data = api_response.get('data')
        response_status = api_response.get('status')
        
        return Response(
            json.dumps(response_data),
            status=response_status,
            content_type="application/json",
        )

    def _exception_handler(self, exception):
        if isinstance(exception, APIException):
            self.set_response(
                {"message": exception.message}, 
                exception.status_code)
        else:
            _logger.error(exception)
            self.set_response(str(exception), 500)

    def dispatch(self):
        self._set_default_response()

        try:
            self._execute_required_action()
            self._execute_route_action()
        except Exception as e:
            self._exception_handler(e)

        return self._response()



    


