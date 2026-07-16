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
        'views/core_api_action_views.xml',
        'views/core_api_service_views.xml',
        'views/core_api_version_views.xml',
        'views/core_api_menu.xml',
    ],

    'installable': True,

    'application': True,

    'license': 'LGPL-3',
}

