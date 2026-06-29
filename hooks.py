# Part of T4 Core API. See LICENSE file for full copyright and licensing details.


def post_init_hook(env):
    """Backfill gateway routes, version tabs, and sync application form tabs."""
    env['core.api.endpoint']._migrate_legacy_route_fields()
    env['core.api.endpoint']._migrate_link_version_tabs()
    env['core.api.application'].search([])._ensure_version_tabs()
    env['core.api.version'].sync_all_application_version_tab_views()
