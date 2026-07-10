"""Matplotlib helpers for directional trapezoid frequency spectra."""

from __future__ import annotations

from dataclasses import replace

import matplotlib as mpl
from matplotlib.axes import Axes
from matplotlib.patches import Polygon

from mixer_math import FrequencyBand, FrequencyMarker, UNIT_SCALE

OVERLAP_COLOR = "#c43c7a"


def configure_matplotlib() -> None:
    mpl.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": [
                "Microsoft YaHei",
                "SimHei",
                "Noto Sans CJK SC",
                "Arial Unicode MS",
                "DejaVu Sans",
            ],
            "axes.unicode_minus": False,
            "axes.titlesize": 12,
            "axes.labelsize": 10,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "legend.fontsize": 9,
        }
    )


def draw_spectrum(
    ax: Axes,
    bands: list[FrequencyBand] | tuple[FrequencyBand, ...],
    *,
    unit: str,
    show_negative: bool,
    title: str,
    markers: list[FrequencyMarker] | tuple[FrequencyMarker, ...] = (),
    compact: bool = False,
    show_legend: bool = True,
    highlight_overlap: bool = False,
    annotate_bounds: bool = False,
) -> None:
    """Draw directional trapezoid spectra and optional point-frequency markers."""

    ax.clear()
    scale = UNIT_SCALE[unit]

    if not bands and not markers:
        ax.text(0.5, 0.5, "无频谱", transform=ax.transAxes, ha="center", va="center")
        ax.set_axis_off()
        return

    x_min, x_max = _axis_limits(bands, markers, scale, show_negative)
    ax.set_xlim(x_min, x_max)
    ax.set_ylim(-0.1, 1.32 if annotate_bounds else 1.22)

    ax.axhline(0.0, color="#16395d", linewidth=1.2)
    if x_min < 0.0 < x_max:
        ax.axvline(0.0, color="#16395d", linewidth=1.0, alpha=0.85)

    for band in bands:
        _draw_one_band(ax, band, scale=scale, label=band.label)
        if show_negative:
            mirrored = replace(
                band,
                low_hz=-band.high_hz,
                high_hz=-band.low_hz,
                label="_nolegend_",
                inverted=not band.inverted,
                alpha=max(0.18, band.alpha * 0.55),
            )
            _draw_one_band(ax, mirrored, scale=scale, label="_nolegend_")

    if highlight_overlap:
        _draw_overlap_regions(ax, bands, scale=scale, show_negative=show_negative)

    if annotate_bounds:
        _draw_boundary_markers(ax, bands, unit=unit, scale=scale, show_negative=show_negative)

    for marker in markers:
        _draw_marker(ax, marker.frequency_hz / scale, marker, label=marker.label, unit=unit)
        if show_negative and marker.mirror_negative and marker.frequency_hz != 0:
            _draw_marker(
                ax,
                -marker.frequency_hz / scale,
                marker,
                label="_nolegend_",
                unit=unit,
                alpha=0.55,
            )

    ax.set_title(title, pad=3 if compact else 8)
    ax.set_xlabel(f"f / {unit}" if not compact else "")
    ax.set_yticks([])
    ax.grid(axis="x", color="#d7e0ea", linestyle="--", linewidth=0.75, alpha=0.75)

    for spine in ("left", "right", "top"):
        ax.spines[spine].set_visible(False)
    ax.spines["bottom"].set_color("#16395d")

    if compact:
        ax.tick_params(axis="x", labelsize=7, pad=1)
        ax.set_title(title, fontsize=9, pad=1)
    elif show_legend:
        handles, labels = ax.get_legend_handles_labels()
        dedup: dict[str, object] = {}
        for handle, label in zip(handles, labels):
            if label and not label.startswith("_"):
                dedup.setdefault(label, handle)
        if dedup:
            ax.legend(dedup.values(), dedup.keys(), loc="upper right", frameon=False)


def _draw_one_band(ax: Axes, band: FrequencyBand, *, scale: float, label: str) -> None:
    low = band.low_hz / scale
    high = band.high_hz / scale
    low, high = _expand_zero_width(low, high, ax.get_xlim())

    # Normal direction: lower input frequency is the tall edge, higher input
    # frequency is the short edge. Inverted bands swap that visual direction.
    left_top = 0.46 if band.inverted else 0.98
    right_top = 0.98 if band.inverted else 0.46
    points = [(low, 0.0), (high, 0.0), (high, right_top), (low, left_top)]

    edge_color = "#53677c" if band.suppressed else "#16395d"
    alpha = 0.16 if band.suppressed else band.alpha
    linestyle = "--" if band.suppressed else "-"
    linewidth = 1.8 if band.suppressed else 1.5

    patch = Polygon(
        points,
        closed=True,
        facecolor=band.color,
        edgecolor=edge_color,
        linewidth=linewidth,
        linestyle=linestyle,
        alpha=alpha,
        label=label,
    )
    ax.add_patch(patch)
    ax.plot(
        [low, high],
        [left_top, right_top],
        color=edge_color,
        linewidth=linewidth,
        linestyle=linestyle,
        alpha=0.9 if not band.suppressed else 0.7,
    )


def _draw_overlap_regions(
    ax: Axes,
    bands: list[FrequencyBand] | tuple[FrequencyBand, ...],
    *,
    scale: float,
    show_negative: bool,
) -> None:
    drawn_bands = list(bands)
    if show_negative:
        drawn_bands.extend(
            replace(
                band,
                low_hz=-band.high_hz,
                high_hz=-band.low_hz,
                inverted=not band.inverted,
            )
            for band in bands
        )

    label_used = False
    for index, first in enumerate(drawn_bands):
        for second in drawn_bands[index + 1 :]:
            low = max(first.low_hz, second.low_hz)
            high = min(first.high_hz, second.high_hz)
            if high <= low:
                continue

            y_low = min(_band_top_at(first, low), _band_top_at(second, low))
            y_high = min(_band_top_at(first, high), _band_top_at(second, high))
            patch = Polygon(
                [
                    (low / scale, 0.0),
                    (high / scale, 0.0),
                    (high / scale, y_high),
                    (low / scale, y_low),
                ],
                closed=True,
                facecolor=OVERLAP_COLOR,
                edgecolor="#84224f",
                linewidth=1.2,
                alpha=0.48,
                label="重叠区域" if not label_used else "_nolegend_",
                zorder=5,
            )
            ax.add_patch(patch)
            label_used = True


def _draw_boundary_markers(
    ax: Axes,
    bands: list[FrequencyBand] | tuple[FrequencyBand, ...],
    *,
    unit: str,
    scale: float,
    show_negative: bool,
) -> None:
    values = []
    for band in bands:
        values.extend((band.low_hz, band.high_hz))
        if show_negative:
            values.extend((-band.high_hz, -band.low_hz))

    unique_values = _unique_sorted(values)
    label_levels = (1.14, 1.24)
    for index, value_hz in enumerate(unique_values):
        x_value = value_hz / scale
        ax.axvline(
            x_value,
            ymin=0.08,
            ymax=0.92,
            color="#6c8fb3",
            linewidth=0.9,
            linestyle="--",
            alpha=0.78,
            zorder=1,
        )
        ax.text(
            x_value,
            label_levels[index % len(label_levels)],
            _format_axis_frequency(value_hz, unit),
            ha="center",
            va="bottom",
            fontsize=8,
            color="#24496e",
            bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.72, "pad": 1.2},
            clip_on=False,
        )


def _draw_marker(
    ax: Axes,
    x_value: float,
    marker: FrequencyMarker,
    *,
    label: str,
    unit: str,
    alpha: float = 1.0,
) -> None:
    ax.vlines(
        x_value,
        0.0,
        1.04,
        color=marker.color,
        linewidth=2.2,
        alpha=alpha,
        label=label,
    )
    ax.text(
        x_value,
        1.08,
        _format_axis_frequency(x_value * UNIT_SCALE[unit], unit),
        ha="center",
        va="bottom",
        fontsize=8,
        color=marker.color,
        bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.72, "pad": 1.0},
        clip_on=False,
    )


def _axis_limits(
    bands: list[FrequencyBand] | tuple[FrequencyBand, ...],
    markers: list[FrequencyMarker] | tuple[FrequencyMarker, ...],
    scale: float,
    show_negative: bool,
) -> tuple[float, float]:
    values = []
    values.extend(band.low_hz / scale for band in bands)
    values.extend(band.high_hz / scale for band in bands)
    values.extend(marker.frequency_hz / scale for marker in markers)

    if not values:
        values = [0.0]

    min_x = min(values)
    max_x = max(values)

    if show_negative:
        max_abs = max(abs(min_x), abs(max_x), 1.0)
        pad = max_abs * 0.08
        return -max_abs - pad, max_abs + pad

    if max_x == min_x:
        span = max(abs(max_x), 1.0) * 0.16
    else:
        span = max_x - min_x
    pad = max(span * 0.08, max(abs(max_x), abs(min_x), 1.0) * 0.01)
    return min_x - pad, max_x + pad


def _expand_zero_width(low: float, high: float, limits: tuple[float, float]) -> tuple[float, float]:
    if high != low:
        return low, high
    span = max(abs(limits[1] - limits[0]), 1.0)
    half_width = span * 0.008
    return low - half_width, high + half_width


def _band_top_at(band: FrequencyBand, frequency_hz: float) -> float:
    if band.high_hz == band.low_hz:
        return 0.72

    t = (frequency_hz - band.low_hz) / (band.high_hz - band.low_hz)
    t = max(0.0, min(1.0, t))
    left_top = 0.46 if band.inverted else 0.98
    right_top = 0.98 if band.inverted else 0.46
    return left_top + (right_top - left_top) * t


def _unique_sorted(values: list[float]) -> list[float]:
    if not values:
        return []

    sorted_values = sorted(values)
    unique = [sorted_values[0]]
    for value in sorted_values[1:]:
        tolerance = max(abs(value), abs(unique[-1]), 1.0) * 1e-9
        if abs(value - unique[-1]) > tolerance:
            unique.append(value)
    return unique


def _format_axis_frequency(value_hz: float, unit: str) -> str:
    return f"{value_hz / UNIT_SCALE[unit]:.6g} {unit}"
