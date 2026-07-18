{

    'name': 'T4 Core API',

    'version': '2.0.0',

    'summary': 'Secure external API gateway with client credentials and token auth',

    'description': """
    """,

    'category': 'Technical',

    'author': 'T4',

    'depends': ['base', 'bus', 'mail'],

    'data': [
        'security/ir.model.access.csv',
        'data/ir_cron_data.xml',
        'data/core_api_auth_data.xml',
        'views/core_api_service_views.xml',
        'views/core_api_version_views.xml',
        'wizard/action_generate_wizard_views.xml',
        'views/core_api_action_views.xml',
        'views/core_api_client_views.xml',
        'views/core_api_auth_session_views.xml',
        'views/core_api_menu.xml',
    ],

    'assets': {
        'web.assets_backend': [
            't4_coreapi/static/src/components/versions_timeline/api_versions_timeline.js',
            't4_coreapi/static/src/components/versions_timeline/api_versions_timeline.xml',
        ],
    },

    'installable': True,

    'application': True,

    'license': 'LGPL-3',
}
