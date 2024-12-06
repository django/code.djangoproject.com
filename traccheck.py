#!/usr/bin/env python
import argparse
from dataclasses import dataclass
from datetime import datetime
import difflib
from functools import cached_property, partial
import unittest
from unittest.mock import Mock
import sys

from trac import __version__ as TRACVERSION
from trac.core import ComponentMeta
from trac.env import Environment as TracEnvironment
from trac.log import LOG_LEVELS as TRAC_LOG_LEVELS


def _build_component_tree(import_paths):
    """
    Build a recursive data structure of all given component paths. For example:

        "trac.admin.web_ui.PluginAdminPanel" -> {"trac": {"admin": {"web_ui": "PluginAdminPanel": {}}}}
        "tracdjangoplugin.*" -> {"tracdjangoplugin": {"*": {}}}

    This will be used to determine if some configured components are installed.
    """
    tree = {}
    for path in import_paths:
        branch = tree
        for node in path.split("."):
            branch.setdefault(node, {})
            branch = branch[node]

    return tree


printerr = partial(print, file=sys.stderr)


@dataclass
class ConfiguredComponent:
    """
    Encapsulate the logic for a single component line in [components].
    """

    env: TracEnvironment
    pathstr: str
    boolstr: str

    @property
    def is_installed(self):
        """
        Recursively navigate the environment's installed components to figure out if
        this one matches one (or more) of them.
        """
        branch = self.env.registered_component_tree
        for node in self.pathstr.split("."):
            if node == "*":
                return bool(branch)
            if node not in branch:
                return False
            branch = branch[node]

        assert not branch, f"Final node in installation tree is not empty: {branch!r}"
        return True

    @property
    def is_valid_boolstr(self):
        """
        Only accept either `enabled` or `disabled`, this is to prevent issues with trailing
        comments. For example the line `someplugin.* = enabled  # we need this` would not
        enable the plugin because of the comment.
        """
        return self.boolstr in {"enabled", "disabled"}

    def __str__(self):
        return f"{self.pathstr} = {self.boolstr}"

    def get_lint_errors(self):
        errors = []

        if not self.is_valid_boolstr:
            errors.append("Invalid boolean value")
        if not self.is_installed:
            errors.append("Component is not installed")

        return errors


class CommandEnvironment(TracEnvironment):
    def __init__(self, cmdoptions, *args, **kwargs):
        self._cmdoptions = cmdoptions
        super().__init__(cmdoptions.trac_env, *args, **kwargs)

    def setup_log(self):
        if self._cmdoptions.trac_log_level:
            self.config.set("logging", "log_type", "stderr")
            self.config.set("logging", "log_level", self._cmdoptions.trac_log_level)
            super().setup_log()
        else:
            # Let the mock object capture (and discard) all method calls.
            self.log = Mock()

    # The rest of the methods here are custom and not available on Trac's Environment.

    @property
    def registered_components(self):
        yield from map(self._component_name, ComponentMeta._components)

    @cached_property
    def registered_component_tree(self):
        return _build_component_tree(self.registered_components)

    @property
    def configured_components(self):
        yield from (
            ConfiguredComponent(self, name, value)
            for name, value in self.components_section.options()
        )

    def get_lint_errors(self):
        errors = []
        for component in self.configured_components:
            errors.extend((component, err) for err in component.get_lint_errors())
        return errors


def get_parser():
    parser = argparse.ArgumentParser(
        prog="SUBCOMMAND",
        description=(
            "A suite of utilities that help make sure the trac environment is what we "
            "expect it to be"
        ),
    )
    subparsers = parser.add_subparsers(title="available commands")
    lint = subparsers.add_parser("lint", help="Validate the trac.ini file")
    components = subparsers.add_parser(
        "components", help="Get information about available/installed components"
    )
    runtests = subparsers.add_parser(
        "runtests", help="Run the test suite for this script"
    )

    # set some common arguments
    for subparser in [lint, components]:
        subparser.add_argument("trac_env", help="Path to trac's environment directory")
        subparser.add_argument(
            "--trac-log-level",
            type=str.upper,
            choices=TRAC_LOG_LEVELS,
            help="Display Trac's own logging (leave blank to hide Trac's log messages)",
        )

    lint.set_defaults(handler=CMD_LINT)

    components.set_defaults(handler=CMD_COMPONENTS)
    components.add_argument(
        "--output",
        "-o",
        type=argparse.FileType("w"),
        default="-",
        help='The path to the output file. Use "-" for stdout (default).',
    )
    components.add_argument(
        "--check",
        "-c",
        type=argparse.FileType("r"),
        help=(
            "Check that the enabled components match the ones in the given file "
            "exactly (minus comments)"
        ),
    )

    runtests.set_defaults(handler=CMD_RUNTESTS)

    return parser


class MockEnvironment:
    """
    Makes unittesting ConfiguredComponent easier
    """

    def __init__(self, installed):
        self.registered_component_tree = _build_component_tree(installed)


class TracCheckTestCase(unittest.TestCase):
    def test_build_component_tree_single_item(self):
        self.assertEqual(_build_component_tree(["A.B.C"]), {"A": {"B": {"C": {}}}})

    def test_build_component_tree_single_item_wildcard(self):
        self.assertEqual(_build_component_tree(["A.B.*"]), {"A": {"B": {"*": {}}}})

    def test_build_component_items_no_overlap(self):
        self.assertEqual(
            _build_component_tree(["A.B.C", "D.E.F"]),
            {"A": {"B": {"C": {}}}, "D": {"E": {"F": {}}}},
        )

    def test_build_component_items_overlap(self):
        self.assertEqual(
            _build_component_tree(["A.B.C", "A.B.X"]), {"A": {"B": {"C": {}, "X": {}}}}
        )

    def test_configured_component_is_valid(self):
        env = MockEnvironment([])  # no installed plugins needed for this test
        for boolstr, expected in [
            ("enabled", True),
            ("disabled", True),
            ("ENABLED", False),
            ("enabled # test", False),
            ("enabled#test", False),
        ]:
            component = ConfiguredComponent(env=env, pathstr="test", boolstr=boolstr)
            with self.subTest(boolstr=boolstr):
                self.assertIs(component.is_valid_boolstr, expected)

    def test_configured_component_is_installed(self):
        for installed, pathstr, expected in [
            ("a.b.c", "a.b.c", True),
            ("a.b.c", "d.e.f", False),
            ("a.b.c", "a.b.*", True),
            ("a.b.c", "a.*", True),
            ("a.b.c", "a.b.x", False),
            ("a.b.c", "a.b.c.d", False),
        ]:
            env = MockEnvironment([installed])
            component = ConfiguredComponent(env=env, pathstr=pathstr, boolstr="enabled")
            with self.subTest(intalled=installed, pathstr=pathstr):
                self.assertIs(component.is_installed, expected)


def CMD_LINT(env, options):
    errors = env.get_lint_errors()
    if errors:
        printerr(f"Found {len(errors)} error{'s' if len(errors)>1 else ''}:")
        for component, error in errors:
            printerr(error, component, sep="\t")
        return 1

    printerr("No errors found, congrats")
    return 0


def CMD_COMPONENTS(env, options):
    components = [
        component
        for component in sorted(env.registered_components)
        if env.is_component_enabled(component)
    ]

    if options.check is None:
        curtime = datetime.now().replace(microsecond=0)
        header = (
            f"# generated by {__file__} on {curtime} with Trac version {TRACVERSION}"
        )
        print(header, file=options.output)
        for component in components:
            print(component, file=options.output)
    else:
        expected_components = [
            line.rstrip("\n") for line in options.check if not line.startswith("#")
        ]

        if components == expected_components:
            printerr("The list of installed components matches the provided file")
            return 0

        difference = difflib.context_diff(
            expected_components,
            components,
            fromfile=options.check.name,
            tofile=f"<installed components from {options.trac_env}>",
            lineterm="",
        )
        printerr("The list of installed components does not match the provided file:")
        printerr()
        printerr("\n".join(difference))
        return 1


def CMD_RUNTESTS(options):
    runner = unittest.TextTestRunner()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TracCheckTestCase)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    import django

    django.setup()  # required because some of our own plugins access django settings

    options = get_parser().parse_args()
    if hasattr(options, "trac_env"):
        handlerargs = (CommandEnvironment(options), options)
    else:  # the runtests command doesn't need to load a whole environment
        handlerargs = (options,)

    retcode = options.handler(*handlerargs)
    sys.exit(0 if retcode is None else retcode)
