-- Sample data reproducing ticket #37239 from production (code.djangoproject.com)
-- https://code.djangoproject.com/ticket/37239

BEGIN;

INSERT INTO ticket (
    id, type, "time", changetime, component, severity, priority, owner, reporter, cc,
    version, milestone, status, resolution, summary, description, keywords
) VALUES (
    37239,
    'Bug',
    1785297235000000,
    1785511817805600,
    'Database layer (models, ORM)',
    'Normal',
    '',
    'jacobtylerwalls',
    'jacobtylerwalls',
    'lilyfoote',
    '5.2',
    '',
    'assigned',
    '',
    E'Saving related objects with generated primary keys doesn\'t update assigned relations',
    $desc$With these models:
{{{#!py
class DBDefaultsFunctionPK(models.Model):
    uuid = models.UUIDField(primary_key=True, db_default=UUID4())

    class Meta:
        required_db_features = {
            "supports_uuid4_function",
            "supports_expression_defaults",
        }


class DBDefaultsFunctionPKChild(DBDefaultsFunctionPK):
    parent = models.OneToOneField(
        DBDefaultsFunctionPK,
        models.CASCADE,
        primary_key=True,
        db_default=UUID4(),
        related_name="child",
    )

    class Meta:
        required_db_features = {
            "supports_uuid4_function",
            "supports_expression_defaults",
        }
}}}
This test fails:
{{{#!py
    @skipUnlessDBFeature(
        "can_return_rows_from_bulk_insert",
        "supports_expression_defaults",
        "supports_uuid4_function",
    )
    def test_foreign_key_db_default_expression_via_parent(self):
        parent = DBDefaultsFunctionPK()
        obj = DBDefaultsFunctionPKChild(parent=parent)
        parent.save()
        obj.save()
        self.assertEqual(obj.pk, parent.pk)
}}}
{{{
======================================================================
FAIL: test_foreign_key_db_default_expression_via_parent (field_defaults.tests.DefaultTests.test_foreign_key_db_default_expression_via_parent)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/jwalls/django/tests/field_defaults/tests.py", line 152, in test_foreign_key_db_default_expression_via_parent
    self.assertEqual(obj.pk, parent.pk)
    ~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
AssertionError: UUID('fdfe6046-e662-4c36-a2e1-b10677d0ccb3') != UUID('ddeef3dd-52bc-4b35-b643-4634876a4acc')

----------------------------------------------------------------------
Ran 1 test in 0.016s

FAILED (failures=1, errors=1)
}}}
----
A similar version of the test using `Now()` instead of `UUID4()` fails on 5.2 (since `UUID4()` is not available there), but I ran into issues with trying to use datetimes in FK constraints on sqlite, so I'm happy to take advice on the best examples to build these models with, as I could be glazing over something obviously better.
----
This is the "separate non-release-blocker ticket" mentioned in #37238, and the underlying reason for the relaxed assertions on the PR for it.$desc$,
    ''
);

INSERT INTO ticket_custom (ticket, name, value) VALUES
    (37239, 'easy', '0'),
    (37239, 'has_patch', '1'),
    (37239, 'needs_better_patch', '0'),
    (37239, 'needs_docs', '0'),
    (37239, 'needs_tests', '0'),
    (37239, 'stage', 'Accepted'),
    (37239, 'ui_ux', '0');

-- comment:1 -- Jacob Walls, 2026-07-28 22:58:01 -05:00
INSERT INTO ticket_change (ticket, "time", author, field, oldvalue, newvalue) VALUES
    (37239, 1785297481122372, 'jacobtylerwalls', 'has_patch', '0', '1'),
    (37239, 1785297481122372, 'jacobtylerwalls', 'comment', '', $c1$[https://github.com/django/django/pull/21694 PR]$c1$);

-- comment:2 -- Sarah Boyce, 2026-07-29 02:47:58 -05:00
INSERT INTO ticket_change (ticket, "time", author, field, oldvalue, newvalue) VALUES
    (37239, 1785311278521760, 'sarahboyce', 'cc', '', 'lilyfoote'),
    (37239, 1785311278521760, 'sarahboyce', 'stage', 'Unreviewed', 'Accepted'),
    (37239, 1785311278521760, 'sarahboyce', 'comment', '', 'Thank you!');

-- comment:3 -- Sarah Boyce, 2026-07-29 03:23:32 -05:00
INSERT INTO ticket_change (ticket, "time", author, field, oldvalue, newvalue) VALUES
    (37239, 1785313412940074, 'sarahboyce', 'needs_better_patch', '0', '1');

-- comment:4 -- Sarah Boyce, 2026-07-29 05:00:18 -05:00
INSERT INTO ticket_change (ticket, "time", author, field, oldvalue, newvalue) VALUES
    (37239, 1785319218661765, 'sarahboyce', 'summary',
        E'After assigning a related object with a db_default, the db_default expression is reevaluated when saving the other object',
        E'Saving related objects with generated primary keys doesn\'t update assigned relations'),
    (37239, 1785319218661765, 'sarahboyce', 'comment', '',
        $c4$I have closed #37238 as a duplicate as the fix for this appears to resolve that issue.
That ticket gives different example models we could use that wouldn't use `UUID4`$c4$);

-- comment:5 -- Jacob Walls, 2026-07-31 10:30:17 -05:00
INSERT INTO ticket_change (ticket, "time", author, field, oldvalue, newvalue) VALUES
    (37239, 1785511817805600, 'jacobtylerwalls', 'needs_better_patch', '1', '0');

-- Keep the id sequence in sync so future trac-created tickets don't collide.
SELECT setval('ticket_id_seq', GREATEST((SELECT MAX(id) FROM ticket), 1));

COMMIT;
