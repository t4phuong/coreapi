# Part of T4 Core API. See LICENSE file for full copyright and licensing details.


def pre_init_hook(env):
    """Backfill application service_code before NOT NULL schema and views load."""
    cr = env.cr
    cr.execute("""
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'core_api_application'
    """)
    if not cr.fetchone():
        return

    cr.execute("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'core_api_application' AND column_name = 'service_code'
    """)
    if not cr.fetchone():
        cr.execute("ALTER TABLE core_api_application ADD COLUMN service_code VARCHAR")

    cr.execute("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'core_api_domain' AND column_name = 'service_code'
    """)
    if cr.fetchone():
        cr.execute("""
            UPDATE core_api_application AS app
            SET service_code = domain.service_code
            FROM core_api_domain AS domain
            WHERE app.domain_id = domain.id
              AND (app.service_code IS NULL OR app.service_code = '')
              AND domain.service_code IS NOT NULL
              AND domain.service_code <> ''
        """)

    cr.execute("""
        UPDATE core_api_application
        SET service_code = 'app' || id::text
        WHERE service_code IS NULL OR service_code = ''
    """)
    cr.execute("""
        UPDATE core_api_application AS app
        SET service_code = 'app' || app.id::text
        WHERE app.id <> (
            SELECT MIN(id) FROM core_api_application
            WHERE service_code = app.service_code
        )
    """)

    cr.execute("""
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'core_api_endpoint'
    """)
    if not cr.fetchone():
        return

    cr.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'core_api_endpoint'
          AND column_name IN ('active', 'route_active')
    """)
    endpoint_cols = {row[0] for row in cr.fetchall()}
    if 'active' in endpoint_cols and 'route_active' not in endpoint_cols:
        cr.execute("ALTER TABLE core_api_endpoint RENAME COLUMN active TO route_active")
    elif 'active' in endpoint_cols and 'route_active' in endpoint_cols:
        cr.execute("""
            UPDATE core_api_endpoint
            SET route_active = COALESCE(route_active, active)
        """)
        cr.execute("ALTER TABLE core_api_endpoint DROP COLUMN active")

    cr.execute("""
        SELECT state FROM ir_module_module
        WHERE name = 't4_coreapi'
    """)
    module_state = cr.fetchone()
    if module_state and module_state[0] in ('installed', 'to upgrade'):
        env['core.api.version'].cleanup_stale_application_version_tab_views()


def post_init_hook(env):
    """Backfill gateway routes, version tabs, service codes, and sync application form tabs."""
    env['core.api.application']._migrate_service_codes()
    env['core.api.endpoint']._migrate_legacy_route_fields()
    env['core.api.endpoint']._migrate_link_version_tabs()
    env['core.api.application'].search([])._ensure_version_tabs()
    env['core.api.version'].sync_all_application_version_tab_views()
