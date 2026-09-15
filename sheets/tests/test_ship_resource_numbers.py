import importlib
from types import SimpleNamespace

import pytest
from django.apps import apps
from django.db import connection
from sheets.schema import load_schema, SchemaError

migration = importlib.import_module("sheets.migrations.0003_ship_resource_numbers")

@pytest.mark.django_db
def test_old_marks_are_archived_without_inventing_numbers(ship_sheet):
    ship_sheet.values={"ship_space_available":True,"ship_power_used":False,"ship_power_available":"90","ship_name":"Keep"}
    ship_sheet.field_versions={"ship_space_available":4}
    ship_sheet.save()
    migration.archive_marks(apps, SimpleNamespace(connection=connection))
    ship_sheet.refresh_from_db()
    assert ship_sheet.values == {"ship_space_available":"","ship_power_used":"","ship_power_available":"90","ship_name":"Keep"}
    assert ship_sheet.field_versions["ship_space_available"]==5
    history=ship_sheet.changes.get(field_id="ship_space_available")
    assert history.old_value is True and history.new_value==""
    migration.archive_marks(apps, SimpleNamespace(connection=connection))
    assert ship_sheet.changes.count()==2

@pytest.mark.parametrize("field", migration.RESOURCE_FIELDS)
def test_resource_fields_accept_numbers_not_marks(field):
    spec=load_schema("ship-page").field_by_id(field)
    assert spec.kind=="text" and spec.input_mode=="numeric"
    spec.validate_value("90")
    spec.validate_value("")
    for invalid in (True, False, "yes", "-1", "1.5"):
        with pytest.raises(SchemaError): spec.validate_value(invalid)

def test_hit_areas_do_not_overlap_other_controls():
    s=load_schema("ship-page")
    rects=[]
    for f in s.fields:
        l,t,r,b=f.hit_padding
        x=float(f.x)*s.image_width/100; y=float(f.y)*s.image_height/100
        w=float(f.width)*s.image_width/100; h=float(f.height)*s.image_height/100
        rects.append((f.id,x-l,y-t,x+w+r,y+h+b))
    for i,a in enumerate(rects):
        for b in rects[i+1:]:
            assert min(a[3],b[3])-max(a[1],b[1]) <= 0.01 or min(a[4],b[4])-max(a[2],b[2]) <= 0.01, (a[0],b[0])
