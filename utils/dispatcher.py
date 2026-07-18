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
# pyrefly: ignore [missing-import]
from odoo.exceptions import AccessError, MissingError, ValidationError, UserError
# pyrefly: ignore [missing-import]
from werkzeug.exceptions import HTTPException
from dateutil.relativedelta import relativedelta

import logging
_logger = logging.getLogger(__name__)

class CoreApiDispatcher:
    _name = 't4.coreapi.dispatcher'
    _description = 'Core API Dispatcher'

    ########## Service #############
    def _find_service_by_code (self, code):
        service = request.env['t4.coreapi.service'].sudo().search([
            ('code', '=', code)], limit=1)
        if not service:
            raise APINotFound("Service not found!")
        return service
    
    def _find_version_by_code (self, version_code):
        version = request.env['t4.coreapi.version'].sudo().search([
            ('version_code', '=', version_code),
            ('active', '=', True),
        ], limit=1)
        if not version:
            raise APINotFound("Version not found!")
        return version

    def _find_route_by_path (self, version_id, route_path):
        route = request.env['t4.coreapi.route'].sudo().search([
            ('version_id', '=', version_id),
            ('route_path', '=', route_path),
        ], limit=1)
        if not route:
            raise APINotFound("Route not found!")

        return route   

    ############ Execution ############
    def _check_rate_limit(self, service, client=None, session_id=None):
        if not service.is_rate_limit_enabled:
            return

        time_limit = fields.Datetime.now() - relativedelta(minutes=service.rate_limit_period)
        domain = [('service_id', '=', service.id), ('create_date', '>=', time_limit)]
        
        if service.rate_limit_type == 'session':
            if not session_id:
                return
            domain.append(('session_id', '=', session_id))
        elif service.rate_limit_type == 'user':
            if not client:
                return
            domain.append(('client_id', '=', client.id))

        log_count = request.env['t4.coreapi.rate.limit.log'].sudo().search_count(domain)

        if log_count >= service.rate_limit_calls:
            if service.rate_limit_action == 'warning':
                pass # Just let it pass if it's warning
            else:
                raise APITooManyRequests("Rate limit exceeded.")

        vals = {'service_id': service.id}
        if client:
            vals['client_id'] = client.id
        if session_id:
            vals['session_id'] = session_id
        request.env['t4.coreapi.rate.limit.log'].sudo().create(vals)

    def _execute_api_action(self, api_action, context):
        if api_action:
            return api_action.with_context(context).run()
        return None

    ############ API ############
    def _set_default_response(self):
        self.set_response({
            "message": "default response"
        }, 200)

    @classmethod
    def set_response(cls, data, status_code=200):
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
                {"error": exception.message}, 
                exception.status_code)
        elif isinstance(exception, HTTPException):
            self.set_response(
                {"error": exception.description or exception.name}, 
                exception.code)
        elif isinstance(exception, AccessError):
            self.set_response({"error": str(exception)}, 403)
        elif isinstance(exception, MissingError):
            self.set_response({"error": str(exception)}, 404)
        elif isinstance(exception, (ValidationError, UserError)):
            self.set_response({"error": str(exception)}, 400)
        else:
            _logger.error(exception)
            self.set_response({"error": str(exception)}, 500)

    def dispatch(self):
        self._set_default_response()

        try:
            service_info = request.service_info
            service = self._find_service_by_code(service_info["service_code"])
            version = self._find_version_by_code(service_info["version_code"])
            route = self._find_route_by_path(version.id, service_info["route_path"])
            
            if service_info["method"] != route.allow_method:
                raise APIBadRequest(f"Method {service_info['method']} not allowed for this route.")
            request.coreapi_route = route
            
            if service.rate_limit_type == 'service':
                self._check_rate_limit(service)
            
            coreapi_data = {
                "params": request.params,
                "header": request.httprequest.headers,
                "body": request.httprequest.data,
                "cookies": request.httprequest.cookies,
                "route": route,
                "user_id": None,
                "state": {},
            }
            
            ctx = {"core api": coreapi_data, **request.env.context}
            
            for req in service.primary_action_ids.sorted(lambda x: x.sequence):
                action_result = self._execute_api_action(req.api_action_id, ctx)
                if action_result and isinstance(action_result, dict):
                    coreapi_data['state'].update(action_result)
                
            if service.rate_limit_type in ('session', 'user'):
                user_id = coreapi_data.get('user_id')
                session_id = coreapi_data.get('session_id')
                client = request.env['t4.coreapi.client'].sudo().browse(user_id) if user_id else None
                self._check_rate_limit(service, client, session_id)
                
            # Filter sensitive contexts before executing the final route action
            coreapi_data.pop('header', None)
            coreapi_data.pop('cookies', None)
                
            self._execute_api_action(route.api_action_id, ctx)
        except Exception as e:
            self._exception_handler(e)
            
        return self._response()



    


