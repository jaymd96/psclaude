"""PEP 440 version management with pre-release support."""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

PreRelease = Literal["dev", "alpha", "beta", "rc"]

_PRE_ORDER: dict[str, int] = {"dev": 0, "alpha": 1, "beta": 2, "rc": 3}
_PRE_SUFFIX: dict[str, str] = {"dev": ".dev", "alpha": "a", "beta": "b", "rc": "rc"}
_SUFFIX_TO_PRE: dict[str, str] = {".dev": "dev", "a": "alpha", "b": "beta", "rc": "rc"}

_VERSION_RE = re.compile(
    r"^(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)"
    r"(?:(?P<pre_kind>\.dev|rc|a|b)(?P<pre_num>\d+))?$"
)
_ABOUT_RE = re.compile(r'^(__version__\s*=\s*["\'])([^"\']+)(["\'])', re.MULTILINE)


@dataclass(frozen=True)
class Version:
    """PEP 440 version: ``major.minor.patch[.devN|aN|bN|rcN]``."""

    major: int
    minor: int
    patch: int
    pre: PreRelease | None = None
    pre_num: int | None = None

    def __post_init__(self) -> None:
        if (self.pre is None) != (self.pre_num is None):
            msg = "pre and pre_num must both be set or both be None"
            raise ValueError(msg)

    # -- Parsing / display ----------------------------------------------------

    @classmethod
    def parse(cls, text: str) -> "Version":
        """Parse a PEP 440 version string."""
        m = _VERSION_RE.match(text.strip())
        if not m:
            msg = f"Invalid PEP 440 version: {text!r}"
            raise ValueError(msg)
        raw_kind = m.group("pre_kind")
        pre: PreRelease | None = _SUFFIX_TO_PRE[raw_kind] if raw_kind else None
        pre_num = int(m.group("pre_num")) if m.group("pre_num") else None
        return cls(
            major=int(m.group("major")),
            minor=int(m.group("minor")),
            patch=int(m.group("patch")),
            pre=pre,
            pre_num=pre_num,
        )

    def __str__(self) -> str:
        base = f"{self.major}.{self.minor}.{self.patch}"
        if self.pre is None:
            return base
        return f"{base}{_PRE_SUFFIX[self.pre]}{self.pre_num}"

    # -- Comparison -----------------------------------------------------------

    @property
    def _sort_key(self) -> tuple[int, int, int, int, int]:
        pre_ord = _PRE_ORDER[self.pre] if self.pre else 99
        return (self.major, self.minor, self.patch, pre_ord, self.pre_num or 0)

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Version):
            return NotImplemented
        return self._sort_key < other._sort_key

    def __le__(self, other: object) -> bool:
        if not isinstance(other, Version):
            return NotImplemented
        return self._sort_key <= other._sort_key

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, Version):
            return NotImplemented
        return self._sort_key > other._sort_key

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, Version):
            return NotImplemented
        return self._sort_key >= other._sort_key

    # -- Properties -----------------------------------------------------------

    @property
    def is_release(self) -> bool:
        """True if this is a final release (no pre-release qualifier)."""
        return self.pre is None

    @property
    def base(self) -> "Version":
        """The release version with pre-release qualifier stripped."""
        return Version(self.major, self.minor, self.patch)

    # -- Bumps ----------------------------------------------------------------

    def bump_major(self) -> "Version":
        """Bump major version: ``N.y.z`` -> ``(N+1).0.0``."""
        return Version(self.major + 1, 0, 0)

    def bump_minor(self) -> "Version":
        """Bump minor version: ``x.N.z`` -> ``x.(N+1).0``."""
        return Version(self.major, self.minor + 1, 0)

    def bump_patch(self) -> "Version":
        """Bump patch version: ``x.y.N`` -> ``x.y.(N+1)``."""
        return Version(self.major, self.minor, self.patch + 1)

    def _bump_pre(self, kind: PreRelease) -> "Version":
        """Bump to a pre-release stage with automatic promotion/regression handling.

        - Same kind: increment (``1.0.0rc1`` -> ``1.0.0rc2``)
        - Earlier → later: promote (``1.0.0a1`` -> ``1.0.0rc1``)
        - Later → earlier: regress to next patch (``1.0.0rc1`` -> ``1.0.1.dev1``)
        - From release: next patch (``1.0.0`` -> ``1.0.1rc1``)
        """
        target_order = _PRE_ORDER[kind]

        if self.pre == kind:
            return Version(self.major, self.minor, self.patch, kind, self.pre_num + 1)

        if self.pre is not None and _PRE_ORDER[self.pre] < target_order:
            # Promote: dev -> alpha, alpha -> beta, beta -> rc
            return Version(self.major, self.minor, self.patch, kind, 1)

        if self.pre is not None and _PRE_ORDER[self.pre] > target_order:
            # Regression: can't go backwards, start fresh for next patch
            return Version(self.major, self.minor, self.patch + 1, kind, 1)

        # From release
        return Version(self.major, self.minor, self.patch + 1, kind, 1)

    def bump_dev(self) -> "Version":
        """Enter or advance the dev pre-release stage."""
        return self._bump_pre("dev")

    def bump_alpha(self) -> "Version":
        """Enter or advance the alpha pre-release stage."""
        return self._bump_pre("alpha")

    def bump_beta(self) -> "Version":
        """Enter or advance the beta pre-release stage."""
        return self._bump_pre("beta")

    def bump_rc(self) -> "Version":
        """Enter or advance the release-candidate stage."""
        return self._bump_pre("rc")

    def release(self) -> "Version":
        """Strip pre-release qualifier to produce the final release."""
        return self.base


# -- File I/O ----------------------------------------------------------------


def _default_about_file() -> Path:
    return Path(__file__).parent / "__about__.py"


def read_version(about_file: Path | None = None) -> "Version":
    """Read ``__version__`` from a Python source file.

    Defaults to this package's own ``__about__.py``.
    """
    path = about_file or _default_about_file()
    text = path.read_text()
    m = _ABOUT_RE.search(text)
    if not m:
        msg = f"No __version__ found in {path}"
        raise ValueError(msg)
    return Version.parse(m.group(2))


def write_version(version: "Version", about_file: Path | None = None) -> Path:
    """Write *version* into a ``__version__ = "..."`` line, preserving surrounding content.

    Returns the path that was written.
    """
    path = about_file or _default_about_file()
    text = path.read_text()
    new_text = _ABOUT_RE.sub(rf"\g<1>{version}\g<3>", text)
    path.write_text(new_text)
    return path


def bump(kind: str, about_file: Path | None = None) -> "Version":
    """Read current version, bump by *kind*, write back, return new version.

    *kind* is one of: ``major``, ``minor``, ``patch``, ``dev``, ``alpha``,
    ``beta``, ``rc``, ``release``.
    """
    current = read_version(about_file)
    if kind == "release":
        new = current.release()
    else:
        method = getattr(current, f"bump_{kind}", None)
        if method is None:
            msg = (
                f"Unknown bump kind: {kind!r}. "
                "Use: major, minor, patch, dev, alpha, beta, rc, release"
            )
            raise ValueError(msg)
        new = method()
    write_version(new, about_file)
    return new
