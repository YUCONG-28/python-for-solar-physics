"""Streamlit frontend for radio-source trajectory playback."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import pandas as pd

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from solar_toolkit.aia.background import load_nearest_background, scan_aia_folder
from solar_toolkit.radio.trajectory import (
    FRAME_MODE_LABELS,
    filter_centers,
    frame_times,
    load_centers_table,
    select_visible_centers,
)
from solar_toolkit.visualization.radio_source_trajectory import build_trajectory_figure


def build_parser() -> argparse.ArgumentParser:
    """Build a lightweight help parser for direct ``python --help`` use."""

    parser = argparse.ArgumentParser(
        description=(
            "Launch the Streamlit radio-source trajectory app. "
            "Run with: streamlit run scripts/radio/run_radio_source_app.py"
        )
    )
    parser.add_argument(
        "--centers",
        default="radio_centers.csv",
        help="Default center CSV/XLSX path shown in the sidebar.",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    """Run the Streamlit app. The app reads existing center tables only."""

    args = build_parser().parse_args(argv or [])
    try:
        import streamlit as st
    except ImportError as exc:  # pragma: no cover - depends on optional extra.
        raise SystemExit(
            "Streamlit is required for this frontend. Install with: "
            'python -m pip install -e ".[app]"'
        ) from exc

    st.set_page_config(page_title="Radio Source Trajectory", layout="wide")
    st.title("射电源中心轨迹与 AIA 背景")

    with st.sidebar:
        st.header("输入数据")
        centers_path = st.text_input("中心表格 CSV/XLSX", value=args.centers)
        uploaded = st.file_uploader("或上传中心表格", type=["csv", "xlsx", "xls"])
        aia_dir = st.text_input("AIA FITS 文件夹", value="")
        aia_pattern = st.text_input("AIA 文件匹配", value="*.fits")

        st.header("播放控制")
        fps = st.slider("播放帧率 FPS", min_value=0.2, max_value=20.0, value=2.0, step=0.2)
        mode_label_to_value = {label: key for key, label in FRAME_MODE_LABELS.items()}
        selected_mode_label = st.selectbox(
            "轨迹显示模式",
            list(mode_label_to_value),
            index=1,
        )
        frame_mode = mode_label_to_value[selected_mode_label]
        tail_n = st.slider("尾迹帧数", min_value=1, max_value=200, value=5, step=1)
        draw_lines = st.checkbox("同频段/同极化中心连线", value=True)

        st.header("AIA 背景")
        use_aia = st.checkbox("显示最近时刻 AIA 背景", value=bool(aia_dir))
        max_pixels = st.slider("AIA 背景最大边长像素", 256, 2048, 1024, 128)
        percentile_limits = st.slider(
            "AIA 显示百分位裁剪",
            0.0,
            100.0,
            (1.0, 99.7),
            step=0.1,
        )
        log_scale = st.checkbox("AIA 背景使用 log10 显示", value=True)
        max_aia_dt_sec = st.number_input(
            "AIA 与射电帧最大时间差/秒",
            min_value=0.0,
            value=3600.0,
            step=10.0,
        )
        wcs_mode = st.selectbox("AIA 坐标模式", ["header", "sunpy"], index=0)

        st.header("左右旋对比")
        compare_lr = st.checkbox("显示 LCP-RCP 连线和差值表", value=True)
        compare_tolerance_sec = st.number_input(
            "LCP/RCP 匹配时间容差/秒",
            min_value=0.0,
            value=1.0,
            step=0.1,
        )

    try:
        centers = load_centers_table(uploaded if uploaded is not None else centers_path)
    except Exception as exc:
        st.error(f"无法读取中心表格：{exc}")
        st.stop()

    if centers.empty:
        st.warning("中心表格为空或没有有效中心。")
        st.stop()

    with st.sidebar:
        freqs_all = sorted(centers["freq_mhz"].dropna().unique().tolist())
        pols_all = sorted(centers["polarization"].dropna().astype(str).unique().tolist())
        methods_all = sorted(centers["center_method"].dropna().astype(str).unique().tolist())
        selected_freqs = st.multiselect("射电频段 / MHz", freqs_all, default=freqs_all)
        selected_pols = st.multiselect("极化", pols_all, default=pols_all)
        selected_methods = st.multiselect("中心方法", methods_all, default=methods_all)

    selected = filter_centers(
        centers,
        freqs=[float(freq) for freq in selected_freqs],
        polarizations=list(selected_pols),
        center_methods=list(selected_methods),
    )
    if selected.empty:
        st.warning("当前筛选条件下没有射电源中心。")
        st.stop()

    times = frame_times(selected)
    if not times:
        st.warning("没有有效时间帧。")
        st.stop()

    if "radio_source_frame_idx" not in st.session_state:
        st.session_state.radio_source_frame_idx = 0
    if "radio_source_playing" not in st.session_state:
        st.session_state.radio_source_playing = False
    st.session_state.radio_source_frame_idx = int(
        max(0, min(st.session_state.radio_source_frame_idx, len(times) - 1))
    )

    c1, c2, c3, c4, c5 = st.columns([1, 1, 1, 1, 5])
    with c1:
        if st.button("上一帧", use_container_width=True):
            st.session_state.radio_source_frame_idx = max(
                0,
                st.session_state.radio_source_frame_idx - 1,
            )
    with c2:
        if st.button("下一帧", use_container_width=True):
            st.session_state.radio_source_frame_idx = min(
                len(times) - 1,
                st.session_state.radio_source_frame_idx + 1,
            )
    with c3:
        if st.button("播放/暂停", use_container_width=True):
            st.session_state.radio_source_playing = (
                not st.session_state.radio_source_playing
            )
    with c4:
        if st.button("回到首帧", use_container_width=True):
            st.session_state.radio_source_frame_idx = 0
            st.session_state.radio_source_playing = False

    selected_index = st.slider(
        "时间帧索引",
        min_value=0,
        max_value=len(times) - 1,
        value=st.session_state.radio_source_frame_idx,
        step=1,
    )
    st.session_state.radio_source_frame_idx = int(selected_index)
    frame_time = pd.Timestamp(times[st.session_state.radio_source_frame_idx])

    aia_background = None
    title_extra = ""
    if use_aia and aia_dir:
        try:
            aia_table = scan_aia_folder(aia_dir, pattern=aia_pattern)
            aia_background, nearest = load_nearest_background(
                aia_table,
                frame_time,
                max_dt_seconds=float(max_aia_dt_sec),
                max_pixels=int(max_pixels),
                percentile_limits=tuple(percentile_limits),
                log_scale=bool(log_scale),
                wcs_mode=wcs_mode,
            )
            if nearest.status == "matched":
                title_extra = f"AIA dt={nearest.delta_seconds:.1f}s"
                st.caption(
                    f"AIA 背景：{aia_background.label}，"
                    f"与当前射电帧时间差 {nearest.delta_seconds:.1f} s"
                )
            else:
                st.info(f"未显示 AIA 背景：{nearest.status}")
        except Exception as exc:
            st.warning(f"AIA 背景读取失败：{exc}")

    visible = select_visible_centers(
        selected,
        frame_time,
        mode=frame_mode,
        tail_n=int(tail_n),
    )
    fig, compare_df = build_trajectory_figure(
        visible,
        frame_time,
        aia_background=aia_background,
        draw_lines=bool(draw_lines),
        compare_lr=bool(compare_lr),
        compare_tolerance_sec=float(compare_tolerance_sec),
        title_extra=title_extra,
    )
    st.plotly_chart(fig, use_container_width=True)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("总中心数", len(centers))
    m2.metric("筛选中心数", len(selected))
    m3.metric("当前显示中心数", len(visible))
    m4.metric("时间帧数", len(times))

    with st.expander("当前显示的射电中心表", expanded=False):
        st.dataframe(
            visible.sort_values(["freq_mhz", "polarization", "obs_time"]),
            use_container_width=True,
            hide_index=True,
        )

    if compare_lr:
        with st.expander("LCP-RCP 位置差", expanded=True):
            if compare_df.empty:
                st.info("当前显示范围内没有可配对的 LCP/RCP 中心。")
            else:
                st.dataframe(
                    compare_df.sort_values(["freq_mhz", "obs_time"]),
                    use_container_width=True,
                    hide_index=True,
                )

    if st.session_state.radio_source_playing:
        time.sleep(max(0.001, 1.0 / float(fps)))
        st.session_state.radio_source_frame_idx = (
            st.session_state.radio_source_frame_idx + 1
        ) % len(times)
        st.rerun()


def _direct_help_requested() -> bool:
    return any(arg in {"-h", "--help"} for arg in sys.argv[1:])


if __name__ == "__main__":
    if _direct_help_requested():
        build_parser().parse_args()
    else:
        main()
