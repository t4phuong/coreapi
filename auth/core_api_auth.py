# -*- coding: utf-8 -*-
from odoo import models, fields, api
# pyrefly: ignore [missing-import]
from odoo.addons.t4_coreapi.exceptions import APIUnauthorized, APIForbidden, APIBadRequest
import json
import base64
import hmac
import hashlib
from datetime import datetime, timedelta
# pyrefly: ignore [missing-import]
from odoo.addons.t4_coreapi.utils.utils import endpoint, get_body, get_headers, get_route, get_coreapi_data

class SimpleJWT:
    @staticmethod
    def encode(payload, secret):
        header = {"alg": "HS256", "typ": "JWT"}
        b64_header = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip('=')
        b64_payload = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip('=')
        signature = hmac.new(secret.encode(), f"{b64_header}.{b64_payload}".encode(), hashlib.sha256).digest()
        b64_signature = base64.urlsafe_b64encode(signature).decode().rstrip('=')
        return f"{b64_header}.{b64_payload}.{b64_signature}"

    @staticmethod
    def decode(token, secret):
        parts = token.split('.')
        if len(parts) != 3:
            raise ValueError("Invalid token format")
        b64_header, b64_payload, b64_signature = parts
        
        signature = hmac.new(secret.encode(), f"{b64_header}.{b64_payload}".encode(), hashlib.sha256).digest()
        expected_signature = base64.urlsafe_b64encode(signature).decode().rstrip('=')
        
        if not hmac.compare_digest(b64_signature, expected_signature):
            raise ValueError("Invalid signature")
            
        payload_padded = b64_payload + '=' * (-len(b64_payload) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_padded).decode())
        
        if 'exp' in payload:
            if datetime.utcnow().timestamp() > payload['exp']:
                raise ValueError("Token expired")
                
        return payload

class CoreApiAuth(models.AbstractModel):
    _name = 't4.coreapi.auth'
    _description = 'Core API Default Auth Logic'

    @api.model
    def _get_all_roles(self, client):
        roles = set()
        queue = list(client.role_ids)
        while queue:
            role = queue.pop(0)
            if role.name not in roles:
                roles.add(role.name)
                queue.extend(role.implied_ids)
        return list(roles)

    @endpoint("Default Auth: Login")
    def action_login(self):
        body = get_body(self.env)

        username = body.get('username')
        password = body.get('password')

        if not username or not password:
            raise APIBadRequest("Missing username or password")

        client = self.env['t4.coreapi.client'].sudo().search([
            ('username', '=', username)
        ], limit=1)

        if not client or not client.check_password(password):
            raise APIUnauthorized("Invalid username or password")

        service = client.service_id

        roles = self._get_all_roles(client)
        
        expiration_hours = 24
        expires_at = datetime.utcnow() + timedelta(hours=expiration_hours)

        payload = {
            'user_id': client.id,
            'service_code': service.code,
            'roles': roles,
            'exp': int(expires_at.timestamp())
        }

        token = SimpleJWT.encode(payload, service.jwt_secret)

        return {
            'token': token,
            'expires_at': expires_at.isoformat()
        }

    @endpoint("Default Auth: Auth Middleware (AuthN & AuthZ)")
    def action_auth_middleware(self):
        route = get_route(self.env)
        if not route:
            return {}

        service = route.version_id.service_id
        if service.privacy == 'public':
            return {}

        headers = get_headers(self.env)
        auth_header = headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            raise APIUnauthorized("Missing or invalid Authorization header")

        token_str = auth_header.split(' ')[1]
        try:
            payload = SimpleJWT.decode(token_str, service.jwt_secret)
        except ValueError as e:
            raise APIUnauthorized(str(e))

        if payload.get('service_code') != service.code:
            raise APIForbidden("Forbidden: Token not issued for this service")

        if route.role_id:
            required_role = route.role_id.name
            token_roles = payload.get('roles', [])
            if required_role not in token_roles:
                raise APIForbidden("Forbidden: Client does not have the required role")
                
        # Update user_id in context for rate limiting
        coreapi_data = get_coreapi_data(self.env)
        if coreapi_data is not None:
            coreapi_data['user_id'] = payload.get('user_id')
            
        return {}
