"""Frequency calculations for the mixer spectrum demonstration."""

from __future__ import annotations

from dataclasses import dataclass, replace
from math import isfinite


UNIT_SCALE = {
    "Hz": 1.0,
    "kHz": 1.0e3,
    "MHz": 1.0e6,
    "GHz": 1.0e9,
}

INPUT_MODE_LIMITS = "上下限"
INPUT_MODE_CENTER_BW = "中心频率 + 带宽"
INPUT_MODES = (INPUT_MODE_LIMITS, INPUT_MODE_CENTER_BW)

CONFIG_REAL = "单路实数混频（和频 + 差频）"
CONFIG_COMPLEX = "正交复数混频"
CONFIG_SSB = "单边带混频"
CONFIG_WEAVER_LSB = "双输入独立边带混频"
CONFIG_NAMES = (CONFIG_REAL, CONFIG_COMPLEX, CONFIG_SSB, CONFIG_WEAVER_LSB)

COLOR_INPUT_1 = "#e18f3e"
COLOR_INPUT_2 = "#2f9d57"
COLOR_Q = "#4f8cc9"
COLOR_LO = "#111111"


@dataclass(frozen=True)
class FrequencyBand:
    """A frequency interval plus enough style data to render its spectrum."""

    low_hz: float
    high_hz: float
    label: str
    color: str
    inverted: bool = False
    suppressed: bool = False
    alpha: float = 0.78

    def __post_init__(self) -> None:
        if not isfinite(self.low_hz) or not isfinite(self.high_hz):
            raise ValueError("频率必须是有限数值")
        if self.high_hz < self.low_hz:
            raise ValueError("频率上限不能小于下限")

    @property
    def center_hz(self) -> float:
        return 0.5 * (self.low_hz + self.high_hz)

    @property
    def bandwidth_hz(self) -> float:
        return self.high_hz - self.low_hz


@dataclass(frozen=True)
class FrequencyMarker:
    """A point frequency, rendered as a vertical marker instead of a band."""

    frequency_hz: float
    label: str
    color: str = COLOR_LO
    mirror_negative: bool = True

    def __post_init__(self) -> None:
        if not isfinite(self.frequency_hz):
            raise ValueError("点频必须是有限数值")


@dataclass(frozen=True)
class MixerResult:
    topology_name: str
    input_bands: tuple[FrequencyBand, ...]
    lo_marker: FrequencyMarker
    visible_bands: tuple[FrequencyBand, ...]
    suppressed_bands: tuple[FrequencyBand, ...]
    notes: tuple[str, ...]

    @property
    def all_output_bands(self) -> tuple[FrequencyBand, ...]:
        return self.visible_bands + self.suppressed_bands


def parse_frequency_pair(
    first_text: str,
    second_text: str,
    mode: str,
    unit: str,
    *,
    allow_zero_bandwidth: bool,
    label: str,
    color: str,
) -> FrequencyBand:
    """Parse two user-visible frequency values into a Hz frequency interval."""

    if mode not in INPUT_MODES:
        raise ValueError(f"不支持的输入形式：{mode}")
    if unit not in UNIT_SCALE:
        raise ValueError(f"不支持的单位：{unit}")

    first = _parse_float(first_text, "第一个频率")
    second = _parse_float(second_text, "第二个频率")
    scale = UNIT_SCALE[unit]

    if mode == INPUT_MODE_LIMITS:
        low_hz = first * scale
        high_hz = second * scale
        if high_hz < low_hz:
            raise ValueError("上限频率必须大于或等于下限频率")
    else:
        center_hz = first * scale
        bandwidth_hz = second * scale
        if bandwidth_hz < 0:
            raise ValueError("带宽不能为负数")
        low_hz = center_hz - 0.5 * bandwidth_hz
        high_hz = center_hz + 0.5 * bandwidth_hz

    if not allow_zero_bandwidth and high_hz <= low_hz:
        raise ValueError(f"{label}需要非零带宽")

    return FrequencyBand(low_hz, high_hz, label=label, color=color)


def parse_frequency_value(text: str, unit: str, *, label: str) -> float:
    if unit not in UNIT_SCALE:
        raise ValueError(f"不支持的单位：{unit}")
    return _parse_float(text, label) * UNIT_SCALE[unit]


def values_for_mode(band: FrequencyBand, mode: str, unit: str) -> tuple[float, float]:
    """Convert a band back to the two values shown in the selected input mode."""

    scale = UNIT_SCALE[unit]
    if mode == INPUT_MODE_LIMITS:
        return band.low_hz / scale, band.high_hz / scale
    if mode == INPUT_MODE_CENTER_BW:
        return band.center_hz / scale, band.bandwidth_hz / scale
    raise ValueError(f"不支持的输入形式：{mode}")


def format_frequency(value_hz: float, unit: str, digits: int = 6) -> str:
    value = value_hz / UNIT_SCALE[unit]
    return f"{value:.{digits}g} {unit}"


def format_band(band: FrequencyBand, unit: str) -> str:
    return f"{format_frequency(band.low_hz, unit)} ~ {format_frequency(band.high_hz, unit)}"


def calculate_mixer_result(
    topology_name: str,
    input_1: FrequencyBand,
    lo_hz: float,
    input_2: FrequencyBand | None = None,
    *,
    iq_swap_lo: bool = False,
) -> MixerResult:
    """Return idealized output spectra for the selected mixer topology."""

    lo_marker = FrequencyMarker(lo_hz, "本振 LO")

    if topology_name == CONFIG_REAL:
        signal = replace(input_1, label="输入信号", color=COLOR_INPUT_1)
        visible = (
            _sum_band(signal, lo_hz, "和频：fIN + fLO", COLOR_INPUT_1),
            _difference_band(signal, lo_hz, "差频：|fIN - fLO|", COLOR_INPUT_2),
        )
        notes = (
            "单路实数乘法会同时产生和频与差频。",
            "LO 是点频，因此在频谱图中用黑色竖线表示。",
        )
        return MixerResult(topology_name, (signal,), lo_marker, visible, (), notes)

    if topology_name == CONFIG_SSB:
        signal = replace(input_1, label="输入信号", color=COLOR_INPUT_1)
        if iq_swap_lo:
            topology_label = f"{topology_name}（下边带）"
            visible = (_lo_minus_signal_band(signal, lo_hz, "下边带：fLO - fIN", COLOR_INPUT_1),)
            suppressed = (_suppressed(_sum_band(signal, lo_hz, "上边带镜像：fLO + fIN", COLOR_INPUT_1)),)
        else:
            topology_label = f"{topology_name}（上边带）"
            visible = (_sum_band(signal, lo_hz, "上边带：fLO + fIN", COLOR_INPUT_1),)
            suppressed = (
                _suppressed(_lo_minus_signal_band(signal, lo_hz, "下边带镜像：fLO - fIN", COLOR_INPUT_1)),
            )
        notes = (
            "单边带混频把一个实数输入分成 I 直通和 Q 90° 移相两路。",
            "交换 LO I/Q 后会切换保留的上下边带。",
        )
        return MixerResult(topology_label, (signal,), lo_marker, visible, suppressed, notes)

    if input_2 is None:
        raise ValueError("当前配置需要第二路输入信号")

    if topology_name == CONFIG_COMPLEX:
        i_band = replace(input_1, label="I 输入信号", color=COLOR_INPUT_1)
        q_band = replace(input_2, label="Q 输入信号", color=COLOR_Q)
        if iq_swap_lo:
            topology_label = f"{topology_name}（下边带）"
            visible = (
                _lo_minus_signal_band(i_band, lo_hz, "I 下边带：fLO - fI", COLOR_INPUT_1),
                _lo_minus_signal_band(q_band, lo_hz, "Q 下边带：fLO - fQ", COLOR_Q),
            )
            suppressed = (
                _suppressed(_sum_band(i_band, lo_hz, "I 上边带镜像：fLO + fI", COLOR_INPUT_1)),
                _suppressed(_sum_band(q_band, lo_hz, "Q 上边带镜像：fLO + fQ", COLOR_Q)),
            )
        else:
            topology_label = f"{topology_name}（上边带）"
            visible = (
                _sum_band(i_band, lo_hz, "I 上边带：fLO + fI", COLOR_INPUT_1),
                _sum_band(q_band, lo_hz, "Q 上边带：fLO + fQ", COLOR_Q),
            )
            suppressed = (
                _suppressed(_lo_minus_signal_band(i_band, lo_hz, "I 下边带镜像：fLO - fI", COLOR_INPUT_1)),
                _suppressed(_lo_minus_signal_band(q_band, lo_hz, "Q 下边带镜像：fLO - fQ", COLOR_Q)),
            )
        notes = (
            "IQ 混频包含 I、Q 两路输入和 90° LO 相移。",
            "图中虚线频谱表示理想求和后被抑制的镜像边带。",
        )
        return MixerResult(topology_label, (i_band, q_band), lo_marker, visible, suppressed, notes)

    if topology_name == CONFIG_WEAVER_LSB:
        if iq_swap_lo:
            first_input = replace(input_1, label="输入 1（下边带）", color=COLOR_INPUT_1)
            second_input = replace(input_2, label="输入 2（上边带）", color=COLOR_INPUT_2)
            topology_label = f"{topology_name}（交换 IQ）"
            visible = (
                _lo_minus_signal_band(first_input, lo_hz, "输入 1 下边带：fLO - f1", COLOR_INPUT_1),
                _sum_band(second_input, lo_hz, "输入 2 上边带：fLO + f2", COLOR_INPUT_2),
            )
            placement_note = "输入 1 放到下边带，输入 2 放到上边带。"
        else:
            first_input = replace(input_1, label="输入 1（上边带）", color=COLOR_INPUT_1)
            second_input = replace(input_2, label="输入 2（下边带）", color=COLOR_INPUT_2)
            topology_label = topology_name
            visible = (
                _sum_band(first_input, lo_hz, "输入 1 上边带：fLO + f1", COLOR_INPUT_1),
                _lo_minus_signal_band(second_input, lo_hz, "输入 2 下边带：fLO - f2", COLOR_INPUT_2),
            )
            placement_note = "输入 1 放到上边带，输入 2 放到下边带。"
        notes = (
            "双输入结构把两路独立实数输入分别搬移到 LO 两侧。",
            placement_note,
        )
        return MixerResult(topology_label, (first_input, second_input), lo_marker, visible, (), notes)

    raise ValueError(f"未知混频器配置：{topology_name}")


def _parse_float(text: str, field_name: str) -> float:
    cleaned = text.strip().replace(",", "")
    if not cleaned:
        raise ValueError(f"{field_name}不能为空")
    try:
        value = float(cleaned)
    except ValueError as exc:
        raise ValueError(f"{field_name}不是有效数字：{text}") from exc
    if not isfinite(value):
        raise ValueError(f"{field_name}必须是有限数值")
    return value


def _sum_band(signal: FrequencyBand, lo_hz: float, label: str, color: str) -> FrequencyBand:
    return FrequencyBand(
        signal.low_hz + lo_hz,
        signal.high_hz + lo_hz,
        label=label,
        color=color,
        inverted=signal.inverted,
    )


def _difference_band(signal: FrequencyBand, lo_hz: float, label: str, color: str) -> FrequencyBand:
    low = signal.low_hz - lo_hz
    high = signal.high_hz - lo_hz
    folded_low, folded_high, inverted = _fold_to_positive(low, high, inverted=signal.inverted)
    return FrequencyBand(folded_low, folded_high, label=label, color=color, inverted=inverted)


def _lo_minus_signal_band(signal: FrequencyBand, lo_hz: float, label: str, color: str) -> FrequencyBand:
    low = lo_hz - signal.high_hz
    high = lo_hz - signal.low_hz
    folded_low, folded_high, inverted = _fold_to_positive(low, high, inverted=not signal.inverted)
    return FrequencyBand(folded_low, folded_high, label=label, color=color, inverted=inverted)


def _fold_to_positive(low_hz: float, high_hz: float, *, inverted: bool) -> tuple[float, float, bool]:
    """Fold a signed output interval onto the positive-frequency axis."""

    if high_hz < low_hz:
        low_hz, high_hz = high_hz, low_hz
        inverted = not inverted

    if low_hz >= 0.0:
        return low_hz, high_hz, inverted
    if high_hz <= 0.0:
        return -high_hz, -low_hz, not inverted

    return 0.0, max(-low_hz, high_hz), inverted


def _suppressed(band: FrequencyBand) -> FrequencyBand:
    return replace(band, suppressed=True, alpha=0.2)
