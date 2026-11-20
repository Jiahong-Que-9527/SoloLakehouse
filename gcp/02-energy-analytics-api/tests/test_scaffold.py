"""Task 0.1: prove the package, tooling and CI wiring before any feature work."""


def test_package_imports():
    import energy_api

    assert energy_api.__doc__
