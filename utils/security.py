# Part of T4 Core API. See LICENSE file for full copyright and licensing details.

import ipaddress

from odoo.exceptions import AccessError
from odoo.http import request


def get_client_ip():
    if not request:
        return None
    return request.httprequest.environ.get('REMOTE_ADDR')


def check_ip_allowed(allowed_ips_text, ip_address):
    """Return True if IP is allowed. Empty allowlist = allow any."""
    if not allowed_ips_text or not ip_address:
        return True
    lines = [ln.strip() for ln in allowed_ips_text.splitlines() if ln.strip()]
    if not lines:
        return True
    try:
        client = ipaddress.ip_address(ip_address)
    except ValueError:
        return False
    for entry in lines:
        try:
            if '/' in entry:
                if client in ipaddress.ip_network(entry, strict=False):
                    return True
            elif client == ipaddress.ip_address(entry):
                return True
        except ValueError:
            continue
    return False


def check_rate_limit(env, domain_extra, limit, error_message):
    if not limit:
        return True
    count = env['core.api.log'].sudo().count_recent(domain_extra, minutes=1)
    if count >= limit:
        raise AccessError(error_message)
    return True


def check_application_api_rate_limit(application):
    application.ensure_one()
    check_rate_limit(
        application.env,
        [('application_id', '=', application.id), ('event_type', '=', 'api')],
        application.rate_limit_per_minute,
        f'API rate limit exceeded for application "{application.name}" ({application.rate_limit_per_minute}/min).',
    )


def check_application_auth_rate_limit(application):
    application.ensure_one()
    check_rate_limit(
        application.env,
        [('application_id', '=', application.id), ('event_type', '=', 'auth')],
        application.auth_rate_limit_per_minute,
        f'Auth rate limit exceeded for application "{application.name}" ({application.auth_rate_limit_per_minute}/min).',
    )


def check_ip_auth_rate_limit(env, ip_address, limit=30):
    """Global per-IP auth throttle when application is unknown or before lookup."""
    if not ip_address or not limit:
        return True
    check_rate_limit(
        env,
        [('ip_address', '=', ip_address), ('event_type', '=', 'auth'), ('route', '=', '/api/v1/auth/token')],
        limit,
        f'Too many authentication attempts from IP {ip_address}. Try again later.',
    )
