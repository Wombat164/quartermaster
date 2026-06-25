"""v0 smoke test -- the package imports and the toolchain is wired. No logic yet."""

from quartermaster import __version__


def test_version_present() -> None:
    assert __version__ == "0.0.0"
