{

    'name': 'T4 Core API',

    'version': '19.0.5.0.5',

    'summary': 'Secure external API gateway with client credentials and token auth',

    'description': """

T4 Core API

===========

OAuth2-style API gateway for external applications and branch controllers.



**Application management**

* Register external applications with Client ID / Client Secret (hashed)

* Per-application allowed API catalog

* Token issuance, expiry, and instant revoke



**Authentication**

* ``POST /api/v1/auth/token`` — client credentials grant

* ``auth='core_api'`` gatekeeper on protected routes

* ``@validate_core_api('code')`` decorator for fine-grained access control



**Gateway routes**

* After auth, linked **Server Actions** handle each route

* Use ``record.set_api_response({...})`` in action code to return JSON



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

        'views/core_api_endpoint_views.xml',

        'views/core_api_application_views.xml',

        'views/core_api_token_views.xml',

        'views/core_api_log_views.xml',

        'views/core_api_action_endpoint_views.xml',

        'views/menu_views.xml',

        'wizard/core_api_application_secret_wizard_views.xml',

    ],

    'installable': True,

    'application': True,

    'license': 'LGPL-3',
}

