import argparse
from datetime import datetime
from functools import partial, singledispatch
from pathlib import Path
import sys
import unittest

try:
    from tinycss2 import parse_stylesheet
    from tinycss2 import ast as tokens
except ImportError:
    print("Missing requirement: tinycss2", file=sys.stderr)
    sys.exit(1)


def get_parser():
    parser = argparse.ArgumentParser(
        description="Scan trac's CSS files to detect box-shadow rules and generate a stylesheet that resets them."
    )
    parser.add_argument("cssfiles", nargs="*", type=Path, help="The CSS files to scan")
    parser.add_argument(
        "--outfile",
        "-o",
        type=argparse.FileType("w"),
        default="-",
        help="Where to write the output",
    )
    parser.add_argument("--tests", action="store_true")
    return parser


def tripletwise(iterable):  # no relation to Jeff
    """
    Like itertools.pairwise, but for triplets instead of pairs.
    """
    i = iter(iterable)
    try:
        x, y, z = next(i), next(i), next(i)
    except StopIteration:
        return

    yield x, y, z
    for el in i:
        x, y, z = y, z, el
        yield x, y, z


def skip_whitespace(nodes):
    return filter(lambda node: node.type != "whitespace", nodes)


def has_shadow(rule):
    if not rule.content:
        return False

    for a, b, c in tripletwise(skip_whitespace(rule.content)):
        if isinstance(a, tokens.IdentToken) and a.value == "box-shadow":
            assert isinstance(
                c, (tokens.IdentToken, tokens.DimensionToken, tokens.NumberToken)
            ), f"Unexpected node type {c.type}"
            return isinstance(c, (tokens.DimensionToken, tokens.NumberToken))


def find_shadow(rules):
    for rule in rules:
        if has_shadow(rule):
            yield rule


@singledispatch
def tokenstr(token: tokens.Node):
    return token.value


@tokenstr.register
def _(token: tokens.WhitespaceToken):
    return " "


@tokenstr.register
def _(token: tokens.SquareBracketsBlock):
    return "[" + tokenlist_to_str(token.content) + "]"


@tokenstr.register
def _(token: tokens.HashToken):
    return f"#{token.value}"


@tokenstr.register
def _(token: tokens.StringToken):
    return f'"{token.value}"'


def tokenlist_to_str(tokens):
    return "".join(map(tokenstr, tokens))


def selector_str(rule):
    """
    Return the given rule's selector as a string
    """
    return tokenlist_to_str(rule.prelude).strip()


def reset_css_str(selector):
    return f"{selector}{{\n    @include noshadow;\n}}"


class NoShadowTestCase(unittest.TestCase):
    @classmethod
    def run_and_exit(cls):
        """
        Run all tests on the class and exit with the proper exit status (1 if any failures occured,
        0 otherwise)
        """
        runner = unittest.TextTestRunner()
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(cls)
        result = runner.run(suite)
        retval = 0 if result.wasSuccessful() else 1
        sys.exit(retval)

    def test_tripletwise(self):
        self.assertEqual(
            list(tripletwise("ABCDEF")),
            [("A", "B", "C"), ("B", "C", "D"), ("C", "D", "E"), ("D", "E", "F")],
        )

    def test_tripletwise_too_short(self):
        self.assertEqual(list(tripletwise("AB")), [])

    def test_skip_whitespace(self):
        rules = parse_stylesheet("html { color: red  ; }")
        self.assertEqual(len(rules), 1)
        non_whitespace_content = list(skip_whitespace(rules[0].content))
        self.assertEqual(
            len(non_whitespace_content), 4
        )  # attr, colon, value, semicolon

    def test_has_shadow(self):
        (rule,) = parse_stylesheet("html {box-shadow: 10px 5px 5px red;}")
        self.assertTrue(has_shadow(rule))

    def test_has_shadow_with_box_shadow_none(self):
        (rule,) = parse_stylesheet("html {box-shadow: none;}")
        self.assertFalse(has_shadow(rule))

    def test_has_shadow_empty_rule(self):
        (rule,) = parse_stylesheet("html {}")
        self.assertFalse(has_shadow(rule))

    def test_selector_str_tag(self):
        (rule,) = parse_stylesheet("html {}")
        self.assertEqual(selector_str(rule), "html")

    def test_selector_str_classname(self):
        (rule,) = parse_stylesheet(".className {}")
        self.assertEqual(selector_str(rule), ".className")

    def test_selector_str_id(self):
        (rule,) = parse_stylesheet("#identifier {}")
        self.assertEqual(selector_str(rule), "#identifier")

    def test_selector_str_with_brackets(self):
        (rule,) = parse_stylesheet('input[type="text"] {}')
        self.assertEqual(selector_str(rule), 'input[type="text"]')

    def test_selector_str_with_brackets_noquotes(self):
        (rule,) = parse_stylesheet("input[type=text] {}")
        self.assertEqual(selector_str(rule), "input[type=text]")

    def test_selector_str_with_comma(self):
        (rule,) = parse_stylesheet("a, button {}")
        self.assertEqual(selector_str(rule), "a, button")

    def test_selector_str_with_comma_and_newline(self):
        (rule,) = parse_stylesheet("a,\nbutton {}")
        self.assertEqual(selector_str(rule), "a, button")

    def test_selector_str_pseudoclass(self):
        (rule,) = parse_stylesheet("a:visited {}")
        self.assertEqual(selector_str(rule), "a:visited")

    def test_selector_str_pseudoclass_nonstandard(self):
        (rule,) = parse_stylesheet("button::-moz-focus-inner {}")
        self.assertEqual(selector_str(rule), "button::-moz-focus-inner")


SCSS_NOSHADOW_MIXIN_HEADER = """\
// Trac uses box-shadow and text-shadow everywhere but their 90s look doesn't
// fit well with our design.
@mixin noshadow {
    box-shadow: none;
    border-radius: unset;
}
"""


if __name__ == "__main__":
    parser = get_parser()
    options = parser.parse_args()

    if options.tests:
        NoShadowTestCase.run_and_exit()

    echo = partial(print, file=options.outfile)

    echo(
        f"// Generated by {Path(__file__).name} on {datetime.now().isoformat()}",
        end="\n\n",
    )
    echo(SCSS_NOSHADOW_MIXIN_HEADER)
    echo()

    for i, filepath in enumerate(sorted(options.cssfiles)):
        rules = parse_stylesheet(
            filepath.read_text(), skip_comments=True, skip_whitespace=True
        )
        shadowrules = list(find_shadow(rules))
        if shadowrules:
            if i > 0:
                echo()
                echo()
            echo(f"// {filepath.name}")
            combined_selector = ",\n".join(map(selector_str, shadowrules))
            echo(reset_css_str(combined_selector))
