"""Tests for PEP 440 version management."""

import pytest

from psclaude._version import Version, bump, read_version, write_version

# -- Parsing ------------------------------------------------------------------


class TestParse:
    def test_release(self):
        assert Version.parse("1.2.3") == Version(1, 2, 3)

    def test_dev(self):
        assert Version.parse("1.2.3.dev1") == Version(1, 2, 3, "dev", 1)

    def test_alpha(self):
        assert Version.parse("1.2.3a1") == Version(1, 2, 3, "alpha", 1)

    def test_beta(self):
        assert Version.parse("1.2.3b2") == Version(1, 2, 3, "beta", 2)

    def test_rc(self):
        assert Version.parse("1.2.3rc1") == Version(1, 2, 3, "rc", 1)

    def test_invalid(self):
        with pytest.raises(ValueError, match="Invalid PEP 440"):
            Version.parse("not-a-version")

    def test_whitespace_stripped(self):
        assert Version.parse("  1.2.3  ") == Version(1, 2, 3)

    def test_multi_digit(self):
        assert Version.parse("10.20.300rc42") == Version(10, 20, 300, "rc", 42)


# -- Display ------------------------------------------------------------------


class TestStr:
    @pytest.mark.parametrize("text", ["1.2.3", "1.2.3.dev1", "1.2.3a1", "1.2.3b2", "1.2.3rc1"])
    def test_roundtrip(self, text):
        assert str(Version.parse(text)) == text


# -- Validation ---------------------------------------------------------------


class TestPostInit:
    def test_pre_without_num(self):
        with pytest.raises(ValueError, match="pre and pre_num"):
            Version(1, 0, 0, pre="dev", pre_num=None)

    def test_num_without_pre(self):
        with pytest.raises(ValueError, match="pre and pre_num"):
            Version(1, 0, 0, pre=None, pre_num=1)


# -- Comparison ---------------------------------------------------------------


class TestComparison:
    def test_dev_lt_alpha(self):
        assert Version.parse("1.0.0.dev1") < Version.parse("1.0.0a1")

    def test_alpha_lt_beta(self):
        assert Version.parse("1.0.0a1") < Version.parse("1.0.0b1")

    def test_beta_lt_rc(self):
        assert Version.parse("1.0.0b1") < Version.parse("1.0.0rc1")

    def test_rc_lt_release(self):
        assert Version.parse("1.0.0rc1") < Version.parse("1.0.0")

    def test_full_ordering(self):
        versions = [
            Version.parse("1.0.0"),
            Version.parse("1.0.0rc2"),
            Version.parse("1.0.0.dev1"),
            Version.parse("1.0.0a1"),
            Version.parse("1.0.0b1"),
            Version.parse("1.0.0rc1"),
        ]
        expected = [
            Version.parse("1.0.0.dev1"),
            Version.parse("1.0.0a1"),
            Version.parse("1.0.0b1"),
            Version.parse("1.0.0rc1"),
            Version.parse("1.0.0rc2"),
            Version.parse("1.0.0"),
        ]
        assert sorted(versions) == expected

    def test_cross_version(self):
        assert Version.parse("0.9.9") < Version.parse("1.0.0.dev1")

    def test_le(self):
        assert Version.parse("1.0.0") <= Version.parse("1.0.0")
        assert Version.parse("1.0.0.dev1") <= Version.parse("1.0.0")

    def test_ge(self):
        assert Version.parse("1.0.0") >= Version.parse("1.0.0")
        assert Version.parse("1.0.0") >= Version.parse("1.0.0rc1")

    def test_gt(self):
        assert Version.parse("1.0.0") > Version.parse("1.0.0rc1")

    def test_not_implemented(self):
        assert Version.parse("1.0.0").__lt__("not a version") is NotImplemented
        assert Version.parse("1.0.0").__le__("not a version") is NotImplemented
        assert Version.parse("1.0.0").__gt__("not a version") is NotImplemented
        assert Version.parse("1.0.0").__ge__("not a version") is NotImplemented


# -- Properties ---------------------------------------------------------------


class TestProperties:
    def test_is_release(self):
        assert Version.parse("1.2.3").is_release is True
        assert Version.parse("1.2.3rc1").is_release is False
        assert Version.parse("1.2.3.dev1").is_release is False

    def test_base(self):
        assert Version.parse("1.2.3rc1").base == Version(1, 2, 3)
        assert Version.parse("1.2.3").base == Version(1, 2, 3)


# -- Major / Minor / Patch bumps ---------------------------------------------


class TestBumpMajorMinorPatch:
    def test_bump_major(self):
        assert Version.parse("1.2.3").bump_major() == Version(2, 0, 0)

    def test_bump_minor(self):
        assert Version.parse("1.2.3").bump_minor() == Version(1, 3, 0)

    def test_bump_patch(self):
        assert Version.parse("1.2.3").bump_patch() == Version(1, 2, 4)

    def test_bump_patch_from_rc(self):
        assert Version.parse("1.2.3rc1").bump_patch() == Version(1, 2, 4)

    def test_bump_major_from_dev(self):
        assert Version.parse("1.2.3.dev1").bump_major() == Version(2, 0, 0)

    def test_bump_minor_from_rc(self):
        assert Version.parse("1.2.3rc1").bump_minor() == Version(1, 3, 0)


# -- Dev bumps ----------------------------------------------------------------


class TestBumpDev:
    def test_from_release(self):
        assert Version.parse("1.2.3").bump_dev() == Version(1, 2, 4, "dev", 1)

    def test_increment(self):
        assert Version.parse("1.2.3.dev1").bump_dev() == Version(1, 2, 3, "dev", 2)

    def test_from_alpha_regression(self):
        assert Version.parse("1.2.3a1").bump_dev() == Version(1, 2, 4, "dev", 1)

    def test_from_rc_regression(self):
        assert Version.parse("1.2.3rc1").bump_dev() == Version(1, 2, 4, "dev", 1)


# -- Alpha bumps --------------------------------------------------------------


class TestBumpAlpha:
    def test_from_release(self):
        assert Version.parse("1.2.3").bump_alpha() == Version(1, 2, 4, "alpha", 1)

    def test_increment(self):
        assert Version.parse("1.2.3a1").bump_alpha() == Version(1, 2, 3, "alpha", 2)

    def test_promote_from_dev(self):
        assert Version.parse("1.2.3.dev1").bump_alpha() == Version(1, 2, 3, "alpha", 1)

    def test_from_beta_regression(self):
        assert Version.parse("1.2.3b1").bump_alpha() == Version(1, 2, 4, "alpha", 1)


# -- Beta bumps ---------------------------------------------------------------


class TestBumpBeta:
    def test_from_release(self):
        assert Version.parse("1.2.3").bump_beta() == Version(1, 2, 4, "beta", 1)

    def test_increment(self):
        assert Version.parse("1.2.3b1").bump_beta() == Version(1, 2, 3, "beta", 2)

    def test_promote_from_alpha(self):
        assert Version.parse("1.2.3a1").bump_beta() == Version(1, 2, 3, "beta", 1)

    def test_promote_from_dev(self):
        assert Version.parse("1.2.3.dev1").bump_beta() == Version(1, 2, 3, "beta", 1)

    def test_from_rc_regression(self):
        assert Version.parse("1.2.3rc1").bump_beta() == Version(1, 2, 4, "beta", 1)


# -- RC bumps -----------------------------------------------------------------


class TestBumpRc:
    def test_from_release(self):
        assert Version.parse("1.2.3").bump_rc() == Version(1, 2, 4, "rc", 1)

    def test_increment(self):
        assert Version.parse("1.2.3rc1").bump_rc() == Version(1, 2, 3, "rc", 2)

    def test_promote_from_dev(self):
        assert Version.parse("1.2.3.dev1").bump_rc() == Version(1, 2, 3, "rc", 1)

    def test_promote_from_alpha(self):
        assert Version.parse("1.2.3a1").bump_rc() == Version(1, 2, 3, "rc", 1)

    def test_promote_from_beta(self):
        assert Version.parse("1.2.3b1").bump_rc() == Version(1, 2, 3, "rc", 1)


# -- Release ------------------------------------------------------------------


class TestRelease:
    def test_from_rc(self):
        assert Version.parse("1.2.3rc2").release() == Version(1, 2, 3)

    def test_from_dev(self):
        assert Version.parse("1.2.3.dev5").release() == Version(1, 2, 3)

    def test_from_release_noop(self):
        assert Version.parse("1.2.3").release() == Version(1, 2, 3)


# -- File I/O -----------------------------------------------------------------


class TestFileIO:
    def test_read_write_roundtrip(self, tmp_path):
        about = tmp_path / "__about__.py"
        about.write_text('"""Metadata."""\n\n__version__ = "1.0.0"\n')

        v = read_version(about)
        assert v == Version(1, 0, 0)

        write_version(Version(2, 0, 0, "rc", 1), about)
        assert read_version(about) == Version(2, 0, 0, "rc", 1)
        assert '__version__ = "2.0.0rc1"' in about.read_text()

    def test_read_missing_version(self, tmp_path):
        about = tmp_path / "__about__.py"
        about.write_text("# no version here\n")
        with pytest.raises(ValueError, match="No __version__"):
            read_version(about)

    def test_preserves_surrounding_content(self, tmp_path):
        about = tmp_path / "__about__.py"
        about.write_text('"""Metadata."""\n\n__version__ = "1.0.0"\n\nFOO = 42\n')
        write_version(Version(1, 1, 0), about)
        text = about.read_text()
        assert "FOO = 42" in text
        assert '"""Metadata."""' in text

    def test_single_quotes(self, tmp_path):
        about = tmp_path / "__about__.py"
        about.write_text("__version__ = '1.0.0'\n")
        assert read_version(about) == Version(1, 0, 0)

    def test_read_default_about(self):
        v = read_version()
        assert isinstance(v, Version)


# -- Convenience bump ---------------------------------------------------------


class TestBumpConvenience:
    def test_bump_patch(self, tmp_path):
        about = tmp_path / "__about__.py"
        about.write_text('__version__ = "1.0.0"\n')
        new = bump("patch", about)
        assert new == Version(1, 0, 1)
        assert read_version(about) == Version(1, 0, 1)

    def test_bump_release(self, tmp_path):
        about = tmp_path / "__about__.py"
        about.write_text('__version__ = "1.0.1rc2"\n')
        new = bump("release", about)
        assert new == Version(1, 0, 1)

    def test_bump_dev(self, tmp_path):
        about = tmp_path / "__about__.py"
        about.write_text('__version__ = "1.0.0"\n')
        new = bump("dev", about)
        assert new == Version(1, 0, 1, "dev", 1)

    def test_bump_rc(self, tmp_path):
        about = tmp_path / "__about__.py"
        about.write_text('__version__ = "1.0.0"\n')
        new = bump("rc", about)
        assert new == Version(1, 0, 1, "rc", 1)

    def test_bump_major(self, tmp_path):
        about = tmp_path / "__about__.py"
        about.write_text('__version__ = "1.2.3"\n')
        new = bump("major", about)
        assert new == Version(2, 0, 0)

    def test_bump_minor(self, tmp_path):
        about = tmp_path / "__about__.py"
        about.write_text('__version__ = "1.2.3"\n')
        new = bump("minor", about)
        assert new == Version(1, 3, 0)

    def test_bump_alpha(self, tmp_path):
        about = tmp_path / "__about__.py"
        about.write_text('__version__ = "1.0.0"\n')
        new = bump("alpha", about)
        assert new == Version(1, 0, 1, "alpha", 1)

    def test_bump_beta(self, tmp_path):
        about = tmp_path / "__about__.py"
        about.write_text('__version__ = "1.0.0"\n')
        new = bump("beta", about)
        assert new == Version(1, 0, 1, "beta", 1)

    def test_bump_invalid_kind(self, tmp_path):
        about = tmp_path / "__about__.py"
        about.write_text('__version__ = "1.0.0"\n')
        with pytest.raises(ValueError, match="Unknown bump kind"):
            bump("invalid", about)
