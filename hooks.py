# Part of T4 Core API. See LICENSE file for full copyright and licensing details.

# ir.model.data xmlids renamed device → application (must run on every upgrade)
_IR_MODEL_DATA_RENAMES = [
    ('model_core_api_device', 'model_core_api_application'),
    ('model_core_api_device_secret_wizard', 'model_core_api_application_secret_wizard'),
    ('access_core_api_device_manager', 'access_core_api_application_manager'),
    ('access_core_api_device_secret_wizard_manager', 'access_core_api_application_secret_wizard_manager'),
    ('action_core_api_device', 'action_core_api_application'),
    ('menu_core_api_devices', 'menu_core_api_applications'),
    ('view_core_api_device_list', 'view_core_api_application_list'),
    ('view_core_api_device_form', 'view_core_api_application_form'),
    ('view_core_api_device_secret_wizard_form', 'view_core_api_application_secret_wizard_form'),
]


def _table_exists(cr, table_name):
    cr.execute(
        """
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = %s
        )
        """,
        (table_name,),
    )
    return cr.fetchone()[0]


def _column_exists(cr, table_name, column_name):
    cr.execute(
        """
        SELECT EXISTS (
            SELECT FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = %s AND column_name = %s
        )
        """,
        (table_name, column_name),
    )
    return cr.fetchone()[0]


def _xmlid_exists(cr, name):
    cr.execute(
        """
        SELECT 1 FROM ir_model_data
        WHERE module = 't4_coreapi' AND name = %s
        LIMIT 1
        """,
        (name,),
    )
    return bool(cr.fetchone())


def _rename_xmlid(cr, old_name, new_name):
    """Rename module xmlid unless the new name already exists."""
    if _xmlid_exists(cr, new_name) or not _xmlid_exists(cr, old_name):
        return
    cr.execute(
        """
        UPDATE ir_model_data
        SET name = %s
        WHERE module = 't4_coreapi' AND name = %s
        """,
        (new_name, old_name),
    )


def _migrate_ir_model_metadata(cr):
    """Fix ir.model / ir.model.fields after device → application rename."""
    cr.execute("""
        UPDATE ir_model SET model = 'core.api.application'
        WHERE model = 'core.api.device'
    """)
    cr.execute("""
        UPDATE ir_model_fields SET model = 'core.api.application'
        WHERE model = 'core.api.device'
    """)
    cr.execute("""
        UPDATE ir_model_fields
        SET name = 'application_id', field_description = 'Application'
        WHERE model IN ('core.api.application', 'core.api.token', 'core.api.log')
          AND name = 'device_id'
    """)
    cr.execute("""
        UPDATE ir_model_fields
        SET name = 'application_name', field_description = 'Application Name'
        WHERE model = 'core.api.token' AND name = 'device_name'
    """)
    cr.execute("""
        UPDATE ir_model SET model = 'core.api.application.secret.wizard'
        WHERE model = 'core.api.device.secret.wizard'
    """)
    cr.execute("""
        UPDATE ir_model_fields SET model = 'core.api.application.secret.wizard'
        WHERE model = 'core.api.device.secret.wizard'
    """)
    cr.execute("""
        UPDATE ir_model_fields
        SET name = 'application_id', field_description = 'Application'
        WHERE model = 'core.api.application.secret.wizard' AND name = 'device_id'
    """)


def _migrate_device_tables(cr):
    """Rename SQL tables/columns from device → application (first upgrade only)."""
    if not _table_exists(cr, 'core_api_device'):
        return
    if _table_exists(cr, 'core_api_application'):
        return

    cr.execute('ALTER TABLE core_api_device RENAME TO core_api_application')

    if _table_exists(cr, 'core_api_device_endpoint_rel'):
        cr.execute(
            'ALTER TABLE core_api_device_endpoint_rel '
            'RENAME TO core_api_application_endpoint_rel'
        )
        if _column_exists(cr, 'core_api_application_endpoint_rel', 'device_id'):
            cr.execute(
                'ALTER TABLE core_api_application_endpoint_rel '
                'RENAME COLUMN device_id TO application_id'
            )

    for table in ('core_api_token', 'core_api_log'):
        if _column_exists(cr, table, 'device_id'):
            cr.execute(f'ALTER TABLE {table} RENAME COLUMN device_id TO application_id')


def pre_init_hook(cr):
    """Migrate legacy core.api.device installs before data files load."""
    _migrate_device_tables(cr)
    _migrate_ir_model_metadata(cr)
    for old_name, new_name in _IR_MODEL_DATA_RENAMES:
        _rename_xmlid(cr, old_name, new_name)


def post_init_hook(env):
    """Ensure sample routes have a Server Action on upgrade."""
    health_action = env.ref('t4_coreapi.action_health_server', raise_if_not_found=False)
    health_endpoint = env.ref('t4_coreapi.endpoint_health', raise_if_not_found=False)
    if health_action and health_endpoint and not health_endpoint.action_id:
        health_endpoint.sudo().write({'action_id': health_action.id})


def post_load():
    """Allow ?db= on API routes when multiple databases are installed."""
    import odoo.http

    original = odoo.http.Request._get_session_and_dbname

    def _get_session_and_dbname_with_query_db(self):
        session, dbname = original(self)
        if dbname:
            return session, dbname
        query_db = (self.httprequest.args.get('db') or '').strip()
        host = self.httprequest.environ['HTTP_HOST']
        if query_db and query_db in odoo.http.db_filter([query_db], host=host):
            session.can_save = False
            session.db = query_db
            return session, query_db
        return session, dbname

    odoo.http.Request._get_session_and_dbname = _get_session_and_dbname_with_query_db
