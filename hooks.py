# Part of T4 Core API. See LICENSE file for full copyright and licensing details.


def post_init_hook(env):
    """Backfill version fields on gateway routes created before API versioning."""
    env['core.api.endpoint']._migrate_legacy_route_fields()
