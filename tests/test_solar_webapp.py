from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _public_script_paths_from_index() -> set[str]:
    index = (REPO_ROOT / "docs" / "script_index.md").read_text(encoding="utf-8")
    public_index = re.sub(
        r"(?ms)^## Deprecated Compatibility Entrypoints\n.*?(?=^## |\Z)",
        "",
        index,
    )
    matches = re.findall(r"`((?:scripts|examples)/[^`]+\.py)`", public_index)
    return {Path(match).as_posix() for match in matches}


def test_registry_covers_public_non_archived_script_index_workflows():
    from solar_toolkit.webapp.registry import default_registry

    registry = default_registry(REPO_ROOT)
    registered = {
        module.script_path.as_posix()
        for module in registry.runnable_modules()
        if module.script_path is not None
    }
    expected = _public_script_paths_from_index()

    assert expected - registered == set()
    assert "scripts/radio/legacy/cso_radio_spectrogram_plot.py" in registered
    assert registry.archived_references
    assert all(reference.read_only for reference in registry.archived_references)


def test_registered_modules_build_safe_argument_list_commands(tmp_path):
    from solar_toolkit.webapp.registry import default_registry
    from solar_toolkit.webapp.runner import JobContext

    allowed = tmp_path / "allowed"
    allowed.mkdir()
    registry = default_registry(REPO_ROOT)
    context = JobContext(
        repo_root=REPO_ROOT,
        allowed_roots=[allowed],
        python_executable="PYTHON_EXE",
    )

    for module in registry.runnable_modules():
        command = module.build_command({"arguments": "--help"}, context=context)

        assert isinstance(command, list)
        assert command[0] == "PYTHON_EXE"
        if module.command_module:
            assert command[1:3] == ["-m", module.command_module]
        else:
            assert command[1].endswith(module.command_path.as_posix())
        assert command[-1] == "--help"
        assert all("&&" not in part and "|" not in part for part in command)
        assert module.title.isascii()
        assert module.category.isascii()
        assert module.risk_level in {"standard", "advanced", "deprecated"}
        assert module.input_schema
        assert module.available is True


def test_installed_registry_marks_source_only_recipes_unavailable(tmp_path):
    from solar_toolkit.webapp.registry import default_registry
    from solar_toolkit.webapp.runner import JobContext

    registry = default_registry(tmp_path)
    package_module = registry.get("aia-euv-processor")
    source_recipe = registry.get("aia-time-distance")
    context = JobContext(repo_root=tmp_path, python_executable=sys.executable)

    assert package_module.available is True
    assert package_module.command_module == "solar_toolkit.aia.cli"
    assert package_module.build_command({"arguments": "--help"}, context=context) == [
        sys.executable,
        "-m",
        "solar_toolkit.aia.cli",
        "--help",
    ]

    assert source_recipe.available is False
    assert "not included" in source_recipe.unavailable_reason
    assert source_recipe.to_public_dict()["available"] is False
    with pytest.raises(RuntimeError, match="is unavailable"):
        source_recipe.build_command({"arguments": "--help"}, context=context)


def test_path_payloads_must_stay_inside_allowed_roots(tmp_path):
    from solar_toolkit.webapp.registry import default_registry
    from solar_toolkit.webapp.runner import JobContext

    allowed = tmp_path / "allowed"
    blocked = tmp_path / "blocked"
    allowed.mkdir()
    blocked.mkdir()
    registry = default_registry(REPO_ROOT)
    context = JobContext(
        repo_root=REPO_ROOT,
        allowed_roots=[allowed],
        python_executable=sys.executable,
    )
    module = registry.get("aia-euv-processor")

    with pytest.raises(PermissionError):
        module.build_command(
            {"paths": [str(blocked / "input.fits")], "arguments": "--help"},
            context=context,
        )

    command = module.build_command(
        {"paths": [str(allowed / "input.fits")], "arguments": "--help"},
        context=context,
    )
    assert "--help" in command


def test_job_runner_captures_success_failure_and_cancellation(tmp_path):
    from solar_toolkit.webapp.registry import default_registry
    from solar_toolkit.webapp.runner import JobContext, JobRunner

    class FakeStdout:
        def __init__(self, lines: list[str]) -> None:
            self._lines = lines

        def readline(self) -> str:
            if self._lines:
                return self._lines.pop(0)
            return ""

        def close(self) -> None:
            return None

    class FakeProcess:
        def __init__(self, returncode: int, lines: list[str] | None = None) -> None:
            self.returncode = returncode
            self.stdout = FakeStdout(lines or ["job line\n"])
            self.terminated = False

        def poll(self) -> int | None:
            return self.returncode

        def wait(self, timeout: float | None = None) -> int:
            return self.returncode

        def terminate(self) -> None:
            self.terminated = True
            self.returncode = -15

        def kill(self) -> None:
            self.terminated = True
            self.returncode = -9

    processes: list[FakeProcess] = []

    def fake_popen(*_args, **_kwargs) -> FakeProcess:
        process = FakeProcess(0)
        processes.append(process)
        return process

    context = JobContext(
        repo_root=REPO_ROOT,
        allowed_roots=[tmp_path],
        python_executable=sys.executable,
    )
    runner = JobRunner(default_registry(REPO_ROOT), context, popen_factory=fake_popen)

    job = runner.start("aia-euv-processor", {"arguments": "--help"})
    final = runner.wait(job.id, timeout=2.0)

    assert final["status"] == "succeeded"
    assert "job line" in "\n".join(final["logs"])
    assert runner.cancel(job.id)["status"] == "succeeded"


@pytest.mark.skipif(
    importlib.util.find_spec("flask") is None,
    reason="Flask is optional; install the app extra to test HTTP routes.",
)
def test_webapp_flask_routes_expose_modules_and_english_frontend(tmp_path):
    from solar_toolkit.webapp.server import create_app

    app = create_app(
        allowed_roots=[tmp_path],
        python_executable=sys.executable,
        repo_root=REPO_ROOT,
    )
    client = app.test_client()

    health = client.get("/api/health").get_json()
    modules = client.get("/api/modules").get_json()
    one_module = client.get("/api/modules/aia-euv-processor").get_json()
    page = client.get("/").get_data(as_text=True)

    assert health == {"ok": True}
    assert modules["ok"] is True
    assert any(item["id"] == "image-sequence-viewer" for item in modules["modules"])
    assert one_module["module"]["title"] == "AIA EUV Processor"
    assert "Solar Physics Workbench" in page
    assert "Run Workflow" in page
    assert not re.search(r"[\u4e00-\u9fff]", page)


def test_webapp_frontend_assets_are_english_and_include_expected_controls():
    template = (
        REPO_ROOT / "solar_toolkit" / "webapp" / "templates" / "index.html"
    ).read_text(encoding="utf-8")
    script = (REPO_ROOT / "solar_toolkit" / "webapp" / "static" / "main.js").read_text(
        encoding="utf-8"
    )
    style = (REPO_ROOT / "solar_toolkit" / "webapp" / "static" / "style.css").read_text(
        encoding="utf-8"
    )
    combined = "\n".join([template, script, style])

    for marker in [
        "Solar Physics Workbench",
        "Workflow Library",
        "Advanced",
        "Legacy Reference",
        "Run Workflow",
        "Cancel Job",
        "Job Log",
        "/api/modules",
        "/api/jobs",
    ]:
        assert marker in combined
    assert not re.search(r"[\u4e00-\u9fff]", combined)
