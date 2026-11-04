-- Seed data for Trac's ticket "select field" lookup tables: component, version,
-- and the enum table (severity, ticket_type). Values are the real distinct
-- values currently used on code.djangoproject.com (fetched via its public
-- /query?...&format=csv export), plus "Uncategorized", which is trac.ini's
-- configured default_component but wasn't present in the sampled query.
--
-- IMPORTANT: Trac caches these lookups in memory per-process. After running
-- this file (or any INSERT into component/version/enum) you must restart the
-- trac container for ticket pages to pick up the new values:
--   docker restart codedjangoprojectcom-trac-1
--
-- Without this data, Trac hides the corresponding ticket-box row entirely
-- (Component/Version/Severity/Type) rather than showing it empty -- it's not
-- a rendering bug, the field is just treated as unconfigured.
--
-- priority and milestone are intentionally NOT seeded here: this Trac
-- instance hides those two fields regardless of table contents (confirmed by
-- ticket CSV exports never including them), so seeding them would have no
-- visible effect.

BEGIN;

INSERT INTO component (name, owner, description) VALUES
    ('CSRF', '', ''),
    ('Core (Cache system)', '', ''),
    ('Core (Mail)', '', ''),
    ('Core (Management commands)', '', ''),
    ('Core (Other)', '', ''),
    ('Core (Serialization)', '', ''),
    ('Core (System checks)', '', ''),
    ('Core (URLs)', '', ''),
    ('Database layer (models, ORM)', '', ''),
    ('Documentation', '', ''),
    ('Error reporting', '', ''),
    ('File uploads/storage', '', ''),
    ('Forms', '', ''),
    ('GIS', '', ''),
    ('Generic views', '', ''),
    ('HTTP handling', '', ''),
    ('Internationalization', '', ''),
    ('Migrations', '', ''),
    ('Packaging', '', ''),
    ('Template system', '', ''),
    ('Testing framework', '', ''),
    ('Uncategorized', '', ''),
    ('Utilities', '', ''),
    ('contrib.admin', '', ''),
    ('contrib.auth', '', ''),
    ('contrib.contenttypes', '', ''),
    ('contrib.flatpages', '', ''),
    ('contrib.messages', '', ''),
    ('contrib.postgres', '', ''),
    ('contrib.redirects', '', ''),
    ('contrib.sessions', '', ''),
    ('contrib.sitemaps', '', ''),
    ('contrib.sites', '', ''),
    ('contrib.staticfiles', '', ''),
    ('contrib.syndication', '', '')
ON CONFLICT (name) DO NOTHING;

INSERT INTO version (name, "time", description) VALUES
    ('1.0', NULL, ''),
    ('1.1', NULL, ''),
    ('1.1-beta', NULL, ''),
    ('1.2', NULL, ''),
    ('1.2-beta', NULL, ''),
    ('1.3', NULL, ''),
    ('1.4', NULL, ''),
    ('1.4-beta-1', NULL, ''),
    ('1.5', NULL, ''),
    ('1.6', NULL, ''),
    ('1.7', NULL, ''),
    ('1.8', NULL, ''),
    ('1.9', NULL, ''),
    ('1.10', NULL, ''),
    ('1.11', NULL, ''),
    ('2.0', NULL, ''),
    ('2.1', NULL, ''),
    ('2.2', NULL, ''),
    ('3.0', NULL, ''),
    ('3.1', NULL, ''),
    ('3.2', NULL, ''),
    ('4.0', NULL, ''),
    ('4.1', NULL, ''),
    ('4.2', NULL, ''),
    ('5.0', NULL, ''),
    ('5.1', NULL, ''),
    ('5.2', NULL, ''),
    ('6.0', NULL, ''),
    ('6.1', NULL, ''),
    ('dev', NULL, ''),
    ('newforms-admin', NULL, ''),
    ('soc2009/admin-ui', NULL, '')
ON CONFLICT (name) DO NOTHING;

INSERT INTO enum (type, name, value) VALUES
    ('severity', 'Normal', '1'),
    ('severity', 'Release blocker', '2'),
    ('ticket_type', 'Bug', '1'),
    ('ticket_type', 'New feature', '2'),
    ('ticket_type', 'Cleanup/optimization', '3')
ON CONFLICT (type, name) DO NOTHING;

COMMIT;
