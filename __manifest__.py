{
    'name': 'T4 Core API',
    'version': '19.0.3.0.1',
    'summary': 'Secure external API gateway with client credentials and token auth',
    'description': """
T4 Core API
===========
OAuth2-style API gateway for external devices and services.

**Device management**
* Register external devices with Client ID / Client Secret (hashed)
* Per-device allowed API catalog
* Token issuance, expiry, and instant revoke

**Authentication**
* ``POST /api/v1/auth/token`` — client credentials grant
* ``auth='core_api'`` gatekeeper on protected routes
* ``@validate_core_api('code')`` decorator for fine-grained access control

**Extend in other modules**

.. code-block:: python

    from odoo.addons.t4_coreapi.utils.decorators import validate_core_api

    @http.route('/api/v1/my-route', auth='core_api', ...)
    @validate_core_api('my_endpoint')
    def my_route(self, **kw):
        ...
    """,
    'category': 'Technical',
    'author': 'T4',
    'depends': ['base', 'mail'],
    'data': [
        'security/groups.xml',
        'security/ir.model.access.csv',
        'security/t4_coreapi_rules.xml',
        'data/core_api_endpoint_data.xml',
        'views/core_api_endpoint_views.xml',
        'views/core_api_device_views.xml',
        'views/core_api_token_views.xml',
        'views/core_api_log_views.xml',
        'views/menu_views.xml',
        'wizard/core_api_device_secret_wizard_views.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
    'post_load': 'post_load',
}
