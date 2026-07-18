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

import uuid

class CoreApiAuthSession(models.Model):
    _name = 't4.coreapi.auth.session'
    _description = 'Core API Auth Session'

    session_key = fields.Char(string='Session Key', required=True, index=True)
    client_id = fields.Many2one('t4.coreapi.client', string='Client', required=True, ondelete='cascade', index=True)
    service_id = fields.Many2one(
        't4.coreapi.service',
        related='client_id.service_id',
        store=True,
        string='Service'
    )
    expires_at = fields.Datetime(string='Expires At', index=True)
    uses_per_minute = fields.Integer(string='Uses / Minute', compute='_compute_uses_per_minute')

    def action_revoke_session(self):
        for record in self:
            record.unlink()

    def _compute_uses_per_minute(self):
        for record in self:
            if not record.id:
                record.uses_per_minute = 0
                continue
            time_limit = fields.Datetime.now() - timedelta(minutes=1)
            record.uses_per_minute = self.env['t4.coreapi.rate.limit.log'].sudo().search_count([
                ('session_id', '=', record.id),
                ('create_date', '>=', time_limit)
            ])

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

        expiration_hours = service.token_expiration or 24
        expires_at = datetime.utcnow() + timedelta(hours=expiration_hours)

        if not service.allow_multiple_sessions:
            existing_sessions = self.env['t4.coreapi.auth.session'].sudo().search([('client_id', '=', client.id)])
            existing_sessions.unlink()

        session_key = uuid.uuid4().hex
        self.env['t4.coreapi.auth.session'].sudo().create({
            'session_key': session_key,
            'client_id': client.id,
            'expires_at': expires_at,
        })

        return {
            'token': session_key,
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
        
        session = self.env['t4.coreapi.auth.session'].sudo().search([
            ('session_key', '=', token_str),
        ], limit=1)

        if not session or session.client_id.service_id.id != service.id:
            raise APIUnauthorized("Invalid or missing session key")

        if session.expires_at and session.expires_at < datetime.utcnow():
            raise APIUnauthorized("Session key has expired")

        client = session.client_id

        if route.role_id:
            required_role = route.role_id.name
            roles = self._get_all_roles(client)
            if required_role not in roles:
                raise APIForbidden("Forbidden: Client does not have the required role")
                
        # Update user_id and session_id in context
        coreapi_data = get_coreapi_data(self.env)
        if coreapi_data is not None:
            coreapi_data['user_id'] = client.id
            coreapi_data['session_id'] = session.id
            
        return {}

    @endpoint("Default Auth: Logout")
    def action_logout(self):
        coreapi_data = get_coreapi_data(self.env)
        session_id = coreapi_data.get('session_id') if coreapi_data else None
        if not session_id:
            raise APIUnauthorized("Not authenticated or missing session")
        
        session = self.env['t4.coreapi.auth.session'].sudo().browse(session_id)
        if session.exists():
            session.unlink()
            
        return {'message': 'Logged out successfully'}
