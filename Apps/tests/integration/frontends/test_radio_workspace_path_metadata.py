"""Every Radio Workspace path field must describe native dialog semantics."""

from __future__ import annotations

from solar_apps.frontends.workbench.radio_workspace.catalog import catalog_payload


def test_all_radio_workspace_path_fields_have_explicit_metadata() -> None:
    path_fields: list[dict] = []
    for module in catalog_payload()["modules"]:
        for action in module["actions"]:
            path_fields.extend(
                field for field in action["input_schema"] if field.get("path")
            )

    assert path_fields
    for field in path_fields:
        assert field["path_kind"] in {"file", "directory", "save_file"}
        assert isinstance(field["extensions"], list)
        assert isinstance(field["allow_multiple"], bool)
        if field["path_kind"] == "file":
            assert field["extensions"], field["name"]
