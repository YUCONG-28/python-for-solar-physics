from __future__ import annotations

import os
import threading
import time
from datetime import datetime
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image
from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QApplication

from solar_apps.frontends.image_composer.models import FolderSource, ImageRecord
from solar_apps.frontends.image_composer import ui as image_composer_ui
from solar_apps.frontends.image_composer.ui import ImageComposerWindow


def test_offscreen_window_adds_and_duplicates_a_canvas_slot(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication(["image-composer-test"])
    path = tmp_path / "preview.png"
    Image.new("RGB", (40, 20), "orange").save(path)
    folder = FolderSource(
        id="folder",
        path=tmp_path,
        name="Camera",
        records=[ImageRecord(1, path, datetime(2026, 7, 17, 12), "filename")],
        start_index=1,
        end_index=1,
    )
    window = ImageComposerWindow(allowed_roots=(tmp_path,))
    window.add_folder_source(folder)
    slot = window.add_slot("folder", 1, QPointF(320, 240))
    app.processEvents()

    assert slot is not None
    assert len(window.project.slots) == 1
    assert slot.id in window._slot_items
    window.duplicate_selected_slot()
    assert len(window.project.slots) == 2

    window._dirty = False
    window.close()
    window.deleteLater()
    app.processEvents()


def test_close_cancels_thumbnail_without_waiting_for_slow_decode(
    tmp_path: Path, monkeypatch
) -> None:
    app = QApplication.instance() or QApplication(["image-composer-test"])
    path = tmp_path / "slow-preview.png"
    Image.new("RGB", (40, 20), "blue").save(path)
    started = threading.Event()
    release = threading.Event()

    def slow_decode(_path: Path) -> Image.Image:
        started.set()
        assert release.wait(2.0)
        return Image.new("RGBA", (40, 20), "blue")

    monkeypatch.setattr(image_composer_ui, "load_oriented_rgba", slow_decode)
    folder = FolderSource(
        id="slow-folder",
        path=tmp_path,
        name="Slow Camera",
        records=[ImageRecord(1, path, datetime(2026, 7, 17, 12), "filename")],
        start_index=1,
        end_index=1,
    )
    window = ImageComposerWindow(allowed_roots=(tmp_path,))
    window.add_folder_source(folder)
    assert started.wait(1.0)
    (task,) = tuple(window._thumbnail_tasks.values())

    window._dirty = False
    close_started = time.monotonic()
    assert window.close()
    assert time.monotonic() - close_started < 0.5
    assert task not in window._thumbnail_tasks.values()
    assert task._cancel_event.is_set()
    assert task in image_composer_ui._RETIRED_THUMBNAIL_TASKS

    window.deleteLater()
    app.processEvents()
    release.set()
    assert task.wait(1.0)
    app.processEvents()
    assert task not in image_composer_ui._RETIRED_THUMBNAIL_TASKS
