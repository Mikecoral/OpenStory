from examples.west_world_test.recorder.world_object_registry import WorldObjectRegistry

_META = {"object_id", "name", "hidden", "destroyed", "provenance"}


def test_create_assigns_global_monotonic_id_and_provenance():
    reg = WorldObjectRegistry()
    oid = reg.create(name="威士忌", location_id="saloon", by="maeve",
                     tick=2, action="倒一杯酒", fields={"state": "满杯"})
    assert oid == "obj_0"
    row = reg.get(oid)
    assert row["name"] == "威士忌"
    assert row["location_id"] == "saloon"
    assert row["held_by"] == ""
    assert row["destroyed"] is False
    assert row["provenance"] == {"created_by": "maeve", "created_tick": 2, "created_action": "倒一杯酒"}
    second = reg.create(name="第二杯", location_id="saloon", by="maeve", tick=3, action="再倒", fields={})
    assert second == "obj_1"


def test_apply_patch_updates_free_fields_and_protects_meta():
    reg = WorldObjectRegistry()
    oid = reg.create(name="酒杯", location_id="saloon", by="t", tick=1, action="a", fields={"state": "完整"})
    reg.apply_patch(oid, {"state": "破碎", "quantity": "一片"})
    row = reg.get(oid)
    assert row["state"] == "破碎"
    assert row["quantity"] == "一片"


def test_destroy_is_soft_delete_and_recorded():
    reg = WorldObjectRegistry()
    oid = reg.create(name="酒杯", location_id="saloon", by="t", tick=1, action="a", fields={})
    reg.destroy(oid, by="hector", tick=4)
    assert reg.get(oid)["destroyed"] is True
    assert reg.objects_at("saloon") == []          # destroyed 不在视图里
    assert any(e["op"] == "destroy" and e["object_id"] == oid for e in reg.ledger)


def test_objects_at_filters_by_location_and_hidden():
    reg = WorldObjectRegistry()
    reg.create(name="可见杯", location_id="saloon", by="t", tick=1, action="a", fields={})
    reg.create(name="密照", location_id="saloon", by="t", tick=1, action="a", fields={}, hidden=True)
    reg.create(name="别处物", location_id="ranch", by="t", tick=1, action="a", fields={})
    visible = reg.objects_at("saloon")
    assert [r["name"] for r in visible] == ["可见杯"]
    with_hidden = reg.objects_at("saloon", include_hidden=True)
    assert {r["name"] for r in with_hidden} == {"可见杯", "密照"}
