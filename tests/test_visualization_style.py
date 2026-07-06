from __future__ import annotations


def test_configure_chinese_fonts_returns_selected_font(monkeypatch):
    from solar_toolkit.visualization import configure_chinese_fonts

    class Font:
        def __init__(self, name):
            self.name = name

    monkeypatch.setattr(
        "matplotlib.font_manager.fontManager.ttflist",
        [Font("Microsoft YaHei"), Font("DejaVu Sans")],
    )

    selected = configure_chinese_fonts(["SimHei", "Microsoft YaHei"])

    assert selected == "Microsoft YaHei"
