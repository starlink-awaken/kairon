"""Tests for URI models — extracted from SharedBrain D_Continuity."""

from kairon_lib.uri_models import UriRegistry, UriResource


def test_uri_resource_defaults():
    r = UriResource(uri="bos://test/resource", resource_type="test")
    assert r.uri == "bos://test/resource"
    assert r.ttl_seconds == 3600


def test_uri_resource_to_dict():
    r = UriResource(uri="bos://a/b", resource_type="type1")
    d = r.to_dict()
    assert d["uri"] == "bos://a/b"


def test_uri_registry_register_and_resolve():
    reg = UriRegistry()
    reg.register(UriResource(uri="bos://test/x", resource_type="x"))
    assert reg.count == 1
    resolved = reg.resolve("bos://test/x")
    assert resolved is not None
    assert resolved.resource_type == "x"


def test_uri_registry_resolve_missing():
    reg = UriRegistry()
    assert reg.resolve("bos://missing") is None
