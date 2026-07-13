import sys

import pytest


def test_backend_runtime_is_python_312():
    assert sys.version_info[:2] == (3, 12)


def test_integration_marker_is_registered(pytestconfig):
    markers = pytestconfig.getini("markers")
    assert any(line.startswith("integration:") for line in markers)
