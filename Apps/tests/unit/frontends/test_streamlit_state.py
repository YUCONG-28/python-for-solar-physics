from __future__ import annotations

from types import SimpleNamespace

from solar_apps.platform.state import StateStore
from solar_apps.ui.state import bind_streamlit_fields, save_streamlit_fields


def test_streamlit_binder_restores_and_saves_only_whitelisted_primitives(
    tmp_path,
) -> None:
    store = StateStore(
        tmp_path / "state.json",
        "frontend_state",
        allowed_keys=("theme", "fields", "legacy_imported"),
    )
    store.save({"fields": {"display_mode": "dark", "result_table": "ignore"}})
    st = SimpleNamespace(session_state={})

    bind_streamlit_fields(
        st,
        store,
        frontend_id="example",
        field_keys=("display_mode", "chunk_memory_mb"),
    )
    assert st.session_state["display_mode"] == "dark"
    assert "result_table" not in st.session_state

    st.session_state["display_mode"] = "light"
    st.session_state["chunk_memory_mb"] = 256
    st.session_state["scientific_result"] = {"large": "object"}
    save_streamlit_fields(
        st,
        store,
        ("display_mode", "chunk_memory_mb"),
    )

    fields = store.load()["fields"]
    assert fields["display_mode"] == "light"
    assert fields["chunk_memory_mb"] == 256
    assert "scientific_result" not in fields
