"""Tkinter GUI for demonstrating mixer spectra under different topologies."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from mixer_math import (
    COLOR_INPUT_1,
    COLOR_INPUT_2,
    CONFIG_COMPLEX,
    CONFIG_NAMES,
    CONFIG_REAL,
    CONFIG_SSB,
    CONFIG_WEAVER_LSB,
    INPUT_MODE_LIMITS,
    INPUT_MODES,
    UNIT_SCALE,
    calculate_mixer_result,
    format_band,
    format_frequency,
    parse_frequency_pair,
    parse_frequency_value,
    values_for_mode,
)
from spectrum_plot import configure_matplotlib, draw_spectrum


NAVY = "#14395c"
TEAL = "#76c9d2"
PANEL_BG = "#f7fbff"


class MixerDemoApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("混频器频谱演示")
        self.root.minsize(1360, 860)

        configure_matplotlib()
        self._configure_style()

        self.topology_var = tk.StringVar(value=CONFIG_REAL)
        self.mode_var = tk.StringVar(value=INPUT_MODE_LIMITS)
        self.unit_var = tk.StringVar(value="MHz")
        self.show_negative_var = tk.BooleanVar(value=False)
        self.swap_iq_lo_var = tk.BooleanVar(value=False)

        self.input1_first_var = tk.StringVar(value="1")
        self.input1_second_var = tk.StringVar(value="10")
        self.input2_first_var = tk.StringVar(value="1")
        self.input2_second_var = tk.StringVar(value="10")
        self.lo_freq_var = tk.StringVar(value="100")

        self.output_summary_var = tk.StringVar(value="")
        self.status_var = tk.StringVar(value="")
        self.last_mode = self.mode_var.get()
        self.last_unit = self.unit_var.get()

        self._build_toolbar()
        self._build_architecture_canvas()
        self._build_detail_plot()
        self._update_labels()
        self.update_all()

    def _configure_style(self) -> None:
        style = ttk.Style()
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure(".", font=("Microsoft YaHei", 10))
        style.configure("Accent.TButton", font=("Microsoft YaHei", 10, "bold"))

    def _build_toolbar(self) -> None:
        toolbar = ttk.Frame(self.root, padding=(10, 8, 10, 6))
        toolbar.grid(row=0, column=0, sticky="ew")
        toolbar.columnconfigure(9, weight=1)

        ttk.Label(toolbar, text="混频器配置").grid(row=0, column=0, sticky="w", padx=(0, 6))
        topology_box = ttk.Combobox(
            toolbar,
            textvariable=self.topology_var,
            values=CONFIG_NAMES,
            state="readonly",
            width=34,
        )
        topology_box.grid(row=0, column=1, sticky="w", padx=(0, 14))
        topology_box.bind("<<ComboboxSelected>>", self._on_topology_changed)

        ttk.Label(toolbar, text="输入形式").grid(row=0, column=2, sticky="w", padx=(0, 6))
        mode_box = ttk.Combobox(
            toolbar,
            textvariable=self.mode_var,
            values=INPUT_MODES,
            state="readonly",
            width=15,
        )
        mode_box.grid(row=0, column=3, sticky="w", padx=(0, 14))
        mode_box.bind("<<ComboboxSelected>>", self._on_mode_changed)

        ttk.Label(toolbar, text="单位").grid(row=0, column=4, sticky="w", padx=(0, 6))
        unit_box = ttk.Combobox(
            toolbar,
            textvariable=self.unit_var,
            values=tuple(UNIT_SCALE.keys()),
            state="readonly",
            width=8,
        )
        unit_box.grid(row=0, column=5, sticky="w", padx=(0, 14))
        unit_box.bind("<<ComboboxSelected>>", self._on_unit_changed)

        ttk.Checkbutton(
            toolbar,
            text="显示负频率",
            variable=self.show_negative_var,
            command=self.update_all,
        ).grid(row=0, column=6, sticky="w", padx=(0, 14))

        self.swap_iq_lo_check = ttk.Checkbutton(
            toolbar,
            text="交换 LO I/Q",
            variable=self.swap_iq_lo_var,
            command=self._on_swap_iq_changed,
        )
        self.swap_iq_lo_check.grid(row=0, column=7, sticky="w", padx=(0, 14))

        ttk.Button(toolbar, text="更新频谱", style="Accent.TButton", command=self.update_all).grid(
            row=0, column=8, sticky="w", padx=(0, 14)
        )

        self.status_label = ttk.Label(toolbar, textvariable=self.status_var)
        self.status_label.grid(row=0, column=9, sticky="w")

    def _build_architecture_canvas(self) -> None:
        self.canvas = tk.Canvas(
            self.root,
            width=1240,
            height=560,
            bg=PANEL_BG,
            highlightthickness=1,
            highlightbackground="#cbd8e6",
        )
        self.canvas.grid(row=1, column=0, sticky="n", padx=10, pady=(0, 8))

        self.input1_frame = ttk.LabelFrame(self.canvas, text="输入信号")
        self.input1_first_label = ttk.Label(self.input1_frame)
        self.input1_second_label = ttk.Label(self.input1_frame)
        self._build_pair_entries(
            self.input1_frame,
            self.input1_first_label,
            self.input1_second_label,
            self.input1_first_var,
            self.input1_second_var,
        )

        self.input2_frame = ttk.LabelFrame(self.canvas, text="输入信号 2")
        self.input2_first_label = ttk.Label(self.input2_frame)
        self.input2_second_label = ttk.Label(self.input2_frame)
        self._build_pair_entries(
            self.input2_frame,
            self.input2_first_label,
            self.input2_second_label,
            self.input2_first_var,
            self.input2_second_var,
        )

        self.lo_frame = ttk.LabelFrame(self.canvas, text="本振 LO")
        self.lo_label = ttk.Label(self.lo_frame)
        self.lo_label.grid(row=0, column=0, sticky="w", padx=(8, 5), pady=10)
        self.lo_entry = ttk.Entry(self.lo_frame, textvariable=self.lo_freq_var, width=12)
        self.lo_entry.grid(row=0, column=1, sticky="ew", padx=(0, 8), pady=10)
        self.lo_entry.bind("<Return>", lambda _event: self.update_all())
        self.lo_frame.columnconfigure(1, weight=1)

        self.output_frame = ttk.LabelFrame(self.canvas, text="输出频谱")
        self.output_summary_label = ttk.Label(
            self.output_frame,
            textvariable=self.output_summary_var,
            justify="left",
            wraplength=250,
            font=("Microsoft YaHei", 9),
        )
        self.output_summary_label.pack(fill="both", expand=True, padx=8, pady=6)

        self.input1_plot_frame, self.input1_fig, self.input1_ax, self.input1_canvas = self._make_mini_plot()
        self.input2_plot_frame, self.input2_fig, self.input2_ax, self.input2_canvas = self._make_mini_plot()
        self.lo_plot_frame, self.lo_fig, self.lo_ax, self.lo_canvas = self._make_mini_plot()
        self.output_plot_frame, self.output_fig, self.output_ax, self.output_canvas = self._make_mini_plot()

        self.input1_window = self.canvas.create_window(
            24, 35, window=self.input1_frame, anchor="nw", width=250, height=92
        )
        self.input1_plot_window = self.canvas.create_window(
            24, 142, window=self.input1_plot_frame, anchor="nw", width=250, height=112
        )
        self.input2_window = self.canvas.create_window(
            24, 328, window=self.input2_frame, anchor="nw", width=250, height=92
        )
        self.input2_plot_window = self.canvas.create_window(
            24, 420, window=self.input2_plot_frame, anchor="nw", width=250, height=112
        )
        self.lo_window = self.canvas.create_window(350, 440, window=self.lo_frame, anchor="nw", width=230, height=64)
        self.lo_plot_window = self.canvas.create_window(
            610, 416, window=self.lo_plot_frame, anchor="nw", width=250, height=112
        )
        self.output_window = self.canvas.create_window(
            692, 35, window=self.output_frame, anchor="nw", width=260, height=92
        )
        self.output_plot_window = self.canvas.create_window(
            692, 142, window=self.output_plot_frame, anchor="nw", width=260, height=112
        )

    def _build_pair_entries(
        self,
        parent: ttk.Frame,
        first_label: ttk.Label,
        second_label: ttk.Label,
        first_var: tk.StringVar,
        second_var: tk.StringVar,
    ) -> None:
        parent.columnconfigure(1, weight=1)
        first_label.grid(row=0, column=0, sticky="w", padx=(8, 5), pady=(8, 4))
        first_entry = ttk.Entry(parent, textvariable=first_var, width=12)
        first_entry.grid(row=0, column=1, sticky="ew", padx=(0, 8), pady=(8, 4))
        second_label.grid(row=1, column=0, sticky="w", padx=(8, 5), pady=(0, 8))
        second_entry = ttk.Entry(parent, textvariable=second_var, width=12)
        second_entry.grid(row=1, column=1, sticky="ew", padx=(0, 8), pady=(0, 8))
        first_entry.bind("<Return>", lambda _event: self.update_all())
        second_entry.bind("<Return>", lambda _event: self.update_all())

    def _make_mini_plot(self) -> tuple[ttk.Frame, Figure, object, FigureCanvasTkAgg]:
        frame = ttk.Frame(self.canvas)
        fig = Figure(figsize=(2.5, 1.12), dpi=100)
        ax = fig.add_subplot(111)
        fig.subplots_adjust(left=0.08, right=0.98, bottom=0.22, top=0.78)
        canvas = FigureCanvasTkAgg(fig, master=frame)
        canvas.get_tk_widget().pack(fill="both", expand=True)
        return frame, fig, ax, canvas

    def _build_detail_plot(self) -> None:
        detail = ttk.Frame(self.root, padding=(10, 0, 10, 10))
        detail.grid(row=2, column=0, sticky="nsew")
        self.root.rowconfigure(2, weight=1)
        self.root.columnconfigure(0, weight=1)

        self.detail_fig = Figure(figsize=(11.2, 2.55), dpi=100)
        self.detail_ax = self.detail_fig.add_subplot(111)
        self.detail_fig.subplots_adjust(left=0.055, right=0.985, bottom=0.21, top=0.86)
        self.detail_canvas = FigureCanvasTkAgg(self.detail_fig, master=detail)
        self.detail_canvas.get_tk_widget().pack(fill="both", expand=True)

    def _on_topology_changed(self, _event: tk.Event) -> None:
        self._update_labels()
        self.update_all()

    def _on_swap_iq_changed(self) -> None:
        self._update_labels()
        self.update_all()

    def _on_mode_changed(self, _event: tk.Event) -> None:
        new_mode = self.mode_var.get()
        old_mode = self.last_mode
        unit = self.unit_var.get()

        if new_mode != old_mode:
            self._convert_band_vars(old_mode, new_mode, unit, unit)
        self.last_mode = new_mode
        self._update_labels()
        self.update_all()

    def _on_unit_changed(self, _event: tk.Event) -> None:
        new_unit = self.unit_var.get()
        old_unit = self.last_unit
        mode = self.mode_var.get()

        if new_unit != old_unit:
            self._convert_band_vars(mode, mode, old_unit, new_unit)
            try:
                lo_hz = parse_frequency_value(self.lo_freq_var.get(), old_unit, label="LO 频率")
                self.lo_freq_var.set(self._entry_number(lo_hz / UNIT_SCALE[new_unit]))
            except ValueError:
                pass
        self.last_unit = new_unit
        self._update_labels()
        self.update_all()

    def _convert_band_vars(self, old_mode: str, new_mode: str, old_unit: str, new_unit: str) -> None:
        for first_var, second_var, label, color in (
            (self.input1_first_var, self.input1_second_var, "输入 1", COLOR_INPUT_1),
            (self.input2_first_var, self.input2_second_var, "输入 2", COLOR_INPUT_2),
        ):
            try:
                band = parse_frequency_pair(
                    first_var.get(),
                    second_var.get(),
                    old_mode,
                    old_unit,
                    allow_zero_bandwidth=False,
                    label=label,
                    color=color,
                )
                first, second = values_for_mode(band, new_mode, new_unit)
                first_var.set(self._entry_number(first))
                second_var.set(self._entry_number(second))
            except ValueError:
                continue

    def _parse_inputs(self):
        mode = self.mode_var.get()
        unit = self.unit_var.get()
        topology = self.topology_var.get()

        input1 = parse_frequency_pair(
            self.input1_first_var.get(),
            self.input1_second_var.get(),
            mode,
            unit,
            allow_zero_bandwidth=False,
            label="输入 1",
            color=COLOR_INPUT_1,
        )
        input2 = None
        if topology in (CONFIG_COMPLEX, CONFIG_WEAVER_LSB):
            input2 = parse_frequency_pair(
                self.input2_first_var.get(),
                self.input2_second_var.get(),
                mode,
                unit,
                allow_zero_bandwidth=False,
                label="输入 2",
                color=COLOR_INPUT_2,
            )

        lo_hz = parse_frequency_value(self.lo_freq_var.get(), unit, label="LO 频率")
        return input1, input2, lo_hz

    def _update_labels(self) -> None:
        unit = self.unit_var.get()
        topology = self.topology_var.get()

        if self.mode_var.get() == INPUT_MODE_LIMITS:
            first, second = "下限", "上限"
        else:
            first, second = "中心", "带宽"

        for first_label, second_label in (
            (self.input1_first_label, self.input1_second_label),
            (self.input2_first_label, self.input2_second_label),
        ):
            first_label.configure(text=f"{first} ({unit})")
            second_label.configure(text=f"{second} ({unit})")

        self.lo_label.configure(text=f"频率 ({unit})")

        if topology == CONFIG_REAL:
            self.input1_frame.configure(text="输入信号")
            self.input2_frame.configure(text="输入信号 2")
            self.swap_iq_lo_check.state(["disabled"])
        elif topology == CONFIG_COMPLEX:
            self.input1_frame.configure(text="I 输入信号")
            self.input2_frame.configure(text="Q 输入信号")
            self.swap_iq_lo_check.state(["!disabled"])
        elif topology == CONFIG_SSB:
            self.input1_frame.configure(text="输入信号")
            self.input2_frame.configure(text="输入信号 2")
            self.swap_iq_lo_check.state(["!disabled"])
        else:
            if self.swap_iq_lo_var.get():
                self.input1_frame.configure(text="输入信号 1（下边带）")
                self.input2_frame.configure(text="输入信号 2（上边带）")
            else:
                self.input1_frame.configure(text="输入信号 1（上边带）")
                self.input2_frame.configure(text="输入信号 2（下边带）")
            self.swap_iq_lo_check.state(["!disabled"])

    def update_all(self) -> None:
        self.draw_diagram()
        try:
            input1, input2, lo_hz = self._parse_inputs()
            result = calculate_mixer_result(
                self.topology_var.get(),
                input1,
                lo_hz,
                input2,
                iq_swap_lo=self.swap_iq_lo_var.get(),
            )
        except ValueError as exc:
            self.status_var.set(str(exc))
            self.status_label.configure(foreground="#b42318")
            return

        unit = self.unit_var.get()
        show_negative = self.show_negative_var.get()
        has_second_input = len(result.input_bands) > 1

        draw_spectrum(
            self.input1_ax,
            [result.input_bands[0]],
            unit=unit,
            show_negative=show_negative,
            title=result.input_bands[0].label,
            compact=True,
            show_legend=False,
        )
        if has_second_input:
            draw_spectrum(
                self.input2_ax,
                [result.input_bands[1]],
                unit=unit,
                show_negative=show_negative,
                title=result.input_bands[1].label,
                compact=True,
                show_legend=False,
            )
        else:
            draw_spectrum(
                self.input2_ax,
                [],
                unit=unit,
                show_negative=show_negative,
                title="输入 2",
                compact=True,
                show_legend=False,
            )

        draw_spectrum(
            self.lo_ax,
            [],
            unit=unit,
            show_negative=show_negative,
            markers=[result.lo_marker],
            title="LO",
            compact=True,
            show_legend=False,
        )
        draw_spectrum(
            self.output_ax,
            result.all_output_bands,
            unit=unit,
            show_negative=show_negative,
            markers=[result.lo_marker],
            title="输出",
            compact=True,
            show_legend=False,
        )
        draw_spectrum(
            self.detail_ax,
            result.all_output_bands,
            unit=unit,
            show_negative=show_negative,
            markers=[result.lo_marker],
            title=f"{result.topology_name} 输出频谱",
            compact=False,
            show_legend=True,
            highlight_overlap=True,
            annotate_bounds=True,
        )

        for figure_canvas in (
            self.input1_canvas,
            self.input2_canvas,
            self.lo_canvas,
            self.output_canvas,
            self.detail_canvas,
        ):
            figure_canvas.draw_idle()

        self.output_summary_var.set(self._format_output_summary(result, unit))
        warning = self._get_lo_warning(result, unit)
        if warning:
            self.status_var.set(warning)
            self.status_label.configure(foreground="#b42318")
        else:
            self.status_var.set("频谱已更新")
            self.status_label.configure(foreground="#1f6f43")
        self.draw_diagram()

    def _format_output_summary(self, result, unit: str) -> str:
        lines = [f"LO: {format_frequency(result.lo_marker.frequency_hz, unit)}"]
        for band in result.visible_bands:
            short_label = band.label.split("：", 1)[0]
            lines.append(f"{short_label}: {format_band(band, unit)}")
        for band in result.suppressed_bands:
            short_label = band.label.split("：", 1)[0]
            lines.append(f"{short_label}(抑制): {format_band(band, unit)}")
        return "\n".join(lines)

    def _get_lo_warning(self, result, unit: str) -> str:
        lo_hz = result.lo_marker.frequency_hz
        topology = self.topology_var.get()

        if topology == CONFIG_REAL:
            risky_bands = [band for band in result.input_bands if band.low_hz <= lo_hz <= band.high_hz]
        elif topology in (CONFIG_COMPLEX, CONFIG_SSB):
            if self.swap_iq_lo_var.get():
                risky_bands = [band for band in result.input_bands if lo_hz <= band.high_hz]
            else:
                risky_bands = [band for band in result.input_bands if band.low_hz <= lo_hz <= band.high_hz]
        elif self.swap_iq_lo_var.get():
            risky_bands = [result.input_bands[0]] if lo_hz <= result.input_bands[0].high_hz else []
        else:
            risky_bands = [result.input_bands[1]] if lo_hz <= result.input_bands[1].high_hz else []

        if not risky_bands:
            return ""

        band_names = "、".join(band.label for band in risky_bands)
        return f"警告：LO={format_frequency(lo_hz, unit)} 与 {band_names} 重叠或过低，差频/下边带会折叠"

    def draw_diagram(self) -> None:
        self.canvas.delete("diagram")
        topology = self.topology_var.get()
        self._position_embedded_widgets(topology)

        if topology == CONFIG_REAL:
            self._draw_real_mixer()
        elif topology == CONFIG_COMPLEX:
            self._draw_iq_mixer()
        elif topology == CONFIG_SSB:
            self._draw_ssb_mixer()
        else:
            self._draw_dual_input_mixer()

        self.canvas.tag_lower("diagram")

    def _position_embedded_widgets(self, topology: str) -> None:
        if topology == CONFIG_REAL:
            self._set_window(self.input1_window, 24, 35, 250, 92)
            self._set_window(self.input1_plot_window, 24, 142, 250, 112)
            self._set_window(self.input2_window, -500, -500, 250, 92, hidden=True)
            self._set_window(self.input2_plot_window, -500, -500, 250, 112, hidden=True)
            self._set_window(self.output_window, 960, 35, 270, 118)
            self._set_window(self.output_plot_window, 960, 170, 270, 112)
            self._set_window(self.lo_window, 500, 440, 250, 64)
            self._set_window(self.lo_plot_window, 780, 416, 270, 112)
        elif topology == CONFIG_COMPLEX:
            self._set_window(self.input1_window, 24, 25, 250, 92)
            self._set_window(self.input1_plot_window, 24, 112, 250, 112)
            self._set_window(self.input2_window, 24, 328, 250, 92)
            self._set_window(self.input2_plot_window, 24, 420, 250, 112)
            self._set_window(self.output_window, 960, 25, 270, 138)
            self._set_window(self.output_plot_window, 960, 180, 270, 112)
            self._set_window(self.lo_window, 485, 440, 250, 64)
            self._set_window(self.lo_plot_window, 760, 420, 270, 112)
        elif topology == CONFIG_SSB:
            self._set_window(self.input1_window, 24, 35, 250, 92)
            self._set_window(self.input1_plot_window, 24, 142, 250, 112)
            self._set_window(self.input2_window, -500, -500, 250, 92, hidden=True)
            self._set_window(self.input2_plot_window, -500, -500, 250, 112, hidden=True)
            self._set_window(self.output_window, 960, 35, 270, 138)
            self._set_window(self.output_plot_window, 960, 190, 270, 112)
            self._set_window(self.lo_window, 960, 342, 270, 64)
            self._set_window(self.lo_plot_window, 960, 430, 270, 112)
        else:
            self._set_window(self.input1_window, 24, 25, 250, 92)
            self._set_window(self.input1_plot_window, 24, 112, 250, 112)
            self._set_window(self.input2_window, 24, 328, 250, 92)
            self._set_window(self.input2_plot_window, 24, 420, 250, 112)
            self._set_window(self.lo_window, 960, 25, 270, 64)
            self._set_window(self.lo_plot_window, 960, 112, 270, 112)
            self._set_window(self.output_window, 960, 318, 270, 126)
            self._set_window(self.output_plot_window, 960, 452, 270, 100)

    def _set_window(
        self,
        window_id: int,
        x: int,
        y: int,
        width: int,
        height: int,
        *,
        hidden: bool = False,
    ) -> None:
        self.canvas.coords(window_id, x, y)
        self.canvas.itemconfigure(
            window_id,
            width=width,
            height=height,
            state=tk.HIDDEN if hidden else tk.NORMAL,
        )

    def _draw_real_mixer(self) -> None:
        self._title("单路实数混频器")
        self._mixer(620, 260)
        self._text(675, 304, "Mixer", font=("Microsoft YaHei", 10, "bold"))
        self._lo_symbol(620, 382)

        self._arrow(286, 260, 578, 260)
        self._text(430, 238, "输入", font=("Microsoft YaHei", 10, "bold"))
        self._arrow(662, 260, 934, 260)
        self._text(800, 238, "和频 + 差频", font=("Microsoft YaHei", 10, "bold"))
        self._arrow(620, 352, 620, 302)

    def _draw_iq_mixer(self) -> None:
        sideband = "下边带" if self.swap_iq_lo_var.get() else "上边带"
        self._title(f"正交复数混频（{sideband}）")
        self._mixer(540, 185)
        self._mixer(540, 360)
        self._sum(815, 272, "SUM")
        self._lo_symbol(430, 272)
        self._phase_box(490, 253, text="移相器")

        self._arrow(286, 185, 498, 185)
        self._text(390, 163, "I", font=("Microsoft YaHei", 12, "bold"))
        self._arrow(286, 360, 498, 360)
        self._text(390, 338, "Q", font=("Microsoft YaHei", 12, "bold"))

        self._line(578, 185, 815, 185)
        self._arrow(815, 185, 815, 234)
        self._line(578, 360, 815, 360)
        self._arrow(815, 360, 815, 310)
        self._arrow(854, 272, 934, 272)
        self._text(730, 232, "I Path", font=("Microsoft YaHei", 9, "bold"))
        self._text(730, 316, "Q Path", font=("Microsoft YaHei", 9, "bold"))

        self._line(461, 272, 490, 272)
        self._arrow(540, 253, 540, 226)
        self._arrow(540, 291, 540, 322)
        upper_phase, lower_phase = self._phase_labels()
        self._text(568, 236, upper_phase, font=("Microsoft YaHei", 9, "bold"))
        self._text(568, 310, lower_phase, font=("Microsoft YaHei", 9, "bold"))
        self._text(900, 250, "RF 输出", font=("Microsoft YaHei", 10, "bold"))

    def _draw_ssb_mixer(self) -> None:
        sideband = "下边带" if self.swap_iq_lo_var.get() else "上边带"
        self._title(f"单边带混频（{sideband}）")
        upper_mixer = (600, 145)
        lower_mixer = (600, 390)
        sum_node = (820, 268)
        split_x = 318
        input_y = 270
        signal_phase_box = (360, 370)
        lo_x = 740
        lo_y = 270
        lo_phase_box = (562, 246)
        lo_phase_center_x = lo_phase_box[0] + 38

        self._mixer(*upper_mixer)
        self._mixer(*lower_mixer)
        self._sum(*sum_node, "SUM")
        self._phase_box(*signal_phase_box, text="90°", width=82, height=40)
        self._lo_symbol(lo_x, lo_y, r=28)
        self._phase_box(*lo_phase_box, text="移相器", width=76, height=48)

        self._arrow(286, input_y, split_x, input_y)
        self._dot(split_x, input_y, NAVY)
        self._line(split_x, input_y, split_x, upper_mixer[1], upper_mixer[0] - 38, upper_mixer[1])
        self._arrow(upper_mixer[0] - 50, upper_mixer[1], upper_mixer[0] - 38, upper_mixer[1])
        self._text(440, 122, "I 直通", font=("Microsoft YaHei", 10, "bold"))

        self._line(split_x, input_y, split_x, signal_phase_box[1] + 20, signal_phase_box[0], signal_phase_box[1] + 20)
        self._arrow(
            signal_phase_box[0] + 82,
            signal_phase_box[1] + 20,
            lower_mixer[0] - 38,
            lower_mixer[1],
        )
        self._text(420, 350, "Q 移相", font=("Microsoft YaHei", 10, "bold"))

        self._line(upper_mixer[0] + 38, upper_mixer[1], sum_node[0], upper_mixer[1])
        self._arrow(sum_node[0], upper_mixer[1], sum_node[0], sum_node[1] - 38)
        self._line(lower_mixer[0] + 38, lower_mixer[1], sum_node[0], lower_mixer[1])
        self._arrow(sum_node[0], lower_mixer[1], sum_node[0], sum_node[1] + 38)
        self._arrow(sum_node[0] + 38, sum_node[1], 934, sum_node[1])
        self._text(890, 220, "RF 输出", font=("Microsoft YaHei", 10, "bold"))

        self._line(lo_x - 28, lo_y, lo_phase_box[0] + 76, lo_y)
        self._arrow(lo_phase_center_x, lo_phase_box[1], lo_phase_center_x, upper_mixer[1] + 38)
        self._arrow(lo_phase_center_x, lo_phase_box[1] + 48, lo_phase_center_x, lower_mixer[1] - 38)
        upper_phase, lower_phase = self._phase_labels()
        self._text(lo_phase_center_x + 28, 198, upper_phase, font=("Microsoft YaHei", 9, "bold"))
        self._text(lo_phase_center_x + 28, 338, lower_phase, font=("Microsoft YaHei", 9, "bold"))

    def _draw_dual_input_mixer(self) -> None:
        suffix = "（交换 IQ）" if self.swap_iq_lo_var.get() else ""
        self._title(f"双输入独立边带混频{suffix}")
        orange_bus_x = 330
        green_bus_x = 315
        upper_sum = (520, 210)
        lower_sum = (520, 405)
        upper_mixer = (680, 210)
        lower_mixer = (680, 405)
        final_sum = (850, 308)

        self._phase_box(395, 76, width=72, height=36)
        self._phase_box(395, 470, width=72, height=36)
        self._sum(*upper_sum, "I_SUM", r=29)
        self._sum(*lower_sum, "Q_SUM", r=29)
        self._mixer(*upper_mixer, r=29)
        self._mixer(*lower_mixer, r=29)
        self._sum(*final_sum, "SUM", r=29)
        self._lo_symbol(590, 308, r=24)
        self._phase_box(642, 284, width=76, height=48, text="移相器")

        self._line(286, 150, orange_bus_x, 150, fill=COLOR_INPUT_1)
        self._dot(orange_bus_x, 150, COLOR_INPUT_1)
        self._line(orange_bus_x, 150, orange_bus_x, 94, fill=COLOR_INPUT_1)
        self._arrow(orange_bus_x, 94, 395, 94, fill=COLOR_INPUT_1)
        self._line(467, 94, upper_sum[0], 94, upper_sum[0], upper_sum[1] - 29, fill=COLOR_INPUT_1)
        self._arrow(upper_sum[0], upper_sum[1] - 43, upper_sum[0], upper_sum[1] - 29, fill=COLOR_INPUT_1)
        self._line(orange_bus_x, 150, orange_bus_x, lower_sum[1], fill=COLOR_INPUT_1)
        self._arrow(orange_bus_x, lower_sum[1], lower_sum[0] - 29, lower_sum[1], fill=COLOR_INPUT_1)
        self._text(512, 130, "I1", fill=COLOR_INPUT_1, font=("Microsoft YaHei", 10, "bold"))
        self._text(404, 382, "Q1", fill=COLOR_INPUT_1, font=("Microsoft YaHei", 10, "bold"))

        self._line(286, 405, green_bus_x, 405, fill=COLOR_INPUT_2)
        self._dot(green_bus_x, 405, COLOR_INPUT_2)
        self._line(green_bus_x, 405, green_bus_x, upper_sum[1], fill=COLOR_INPUT_2)
        self._arrow(green_bus_x, upper_sum[1], upper_sum[0] - 29, upper_sum[1], fill=COLOR_INPUT_2)
        self._line(green_bus_x, 405, green_bus_x, 488, fill=COLOR_INPUT_2)
        self._arrow(green_bus_x, 488, 395, 488, fill=COLOR_INPUT_2)
        self._line(467, 488, lower_sum[0], 488, lower_sum[0], lower_sum[1] + 29, fill=COLOR_INPUT_2)
        self._arrow(lower_sum[0], lower_sum[1] + 43, lower_sum[0], lower_sum[1] + 29, fill=COLOR_INPUT_2)
        self._text(404, 188, "I2", fill=COLOR_INPUT_2, font=("Microsoft YaHei", 10, "bold"))
        self._text(512, 456, "Q2", fill=COLOR_INPUT_2, font=("Microsoft YaHei", 10, "bold"))

        self._arrow(upper_sum[0] + 29, upper_sum[1], upper_mixer[0] - 29, upper_mixer[1])
        self._arrow(lower_sum[0] + 29, lower_sum[1], lower_mixer[0] - 29, lower_mixer[1])
        self._line(upper_mixer[0] + 29, upper_mixer[1], final_sum[0], upper_mixer[1])
        self._arrow(final_sum[0], upper_mixer[1], final_sum[0], final_sum[1] - 29)
        self._line(lower_mixer[0] + 29, lower_mixer[1], final_sum[0], lower_mixer[1])
        self._arrow(final_sum[0], lower_mixer[1], final_sum[0], final_sum[1] + 29)
        self._arrow(final_sum[0] + 29, final_sum[1], 934, final_sum[1])
        self._text(902, 286, "输出", font=("Microsoft YaHei", 10, "bold"))

        self._line(614, 308, 642, 308)
        self._arrow(680, 284, 680, upper_mixer[1] + 29)
        self._arrow(680, 332, 680, lower_mixer[1] - 29)
        upper_phase, lower_phase = self._phase_labels()
        self._text(704, 262, upper_phase, font=("Microsoft YaHei", 9, "bold"))
        self._text(704, 354, lower_phase, font=("Microsoft YaHei", 9, "bold"))

    def _title(self, text: str) -> None:
        self._text(620, 16, text, font=("Microsoft YaHei", 14, "bold"))

    def _mixer(self, x: int, y: int, *, r: int = 38) -> None:
        self.canvas.create_oval(
            x - r,
            y - r,
            x + r,
            y + r,
            fill=TEAL,
            outline=NAVY,
            width=3,
            tags=("diagram",),
        )
        cross = int(r * 0.66)
        self._line(x - cross, y - cross, x + cross, y + cross, width=3)
        self._line(x - cross, y + cross, x + cross, y - cross, width=3)

    def _sum(self, x: int, y: int, label: str, *, r: int = 38) -> None:
        self.canvas.create_oval(
            x - r,
            y - r,
            x + r,
            y + r,
            fill=TEAL,
            outline=NAVY,
            width=3,
            tags=("diagram",),
        )
        cross = int(r * 0.68)
        self._line(x - cross, y, x + cross, y, width=3)
        self._line(x, y - cross, x, y + cross, width=3)
        self._text(x, y + r + 17, label, font=("Microsoft YaHei", 9, "bold"))

    def _lo_symbol(self, x: int, y: int, *, r: int = 31) -> None:
        self.canvas.create_oval(
            x - r,
            y - r,
            x + r,
            y + r,
            fill=TEAL,
            outline=NAVY,
            width=3,
            tags=("diagram",),
        )
        self._text(x, y, "LO", font=("Microsoft YaHei", 12, "bold"))

    def _phase_box(
        self,
        x: int,
        y: int,
        *,
        width: int = 70,
        height: int = 38,
        text: str = "90°",
    ) -> None:
        self.canvas.create_rectangle(
            x,
            y,
            x + width,
            y + height,
            fill=TEAL,
            outline=NAVY,
            width=3,
            tags=("diagram",),
        )
        self._text(x + width // 2, y + height // 2, text, font=("Microsoft YaHei", 10, "bold"))

    def _phase_labels(self) -> tuple[str, str]:
        if self.swap_iq_lo_var.get():
            return "0°", "90°"
        return "90°", "0°"

    def _dot(self, x: int, y: int, fill: str) -> None:
        radius = 5
        self.canvas.create_oval(
            x - radius,
            y - radius,
            x + radius,
            y + radius,
            fill=fill,
            outline=fill,
            tags=("diagram",),
        )

    def _arrow(self, *coords: int, fill: str = NAVY, width: int = 3) -> None:
        self.canvas.create_line(
            *coords,
            fill=fill,
            width=width,
            arrow=tk.LAST,
            arrowshape=(14, 16, 6),
            tags=("diagram",),
        )

    def _line(self, *coords: int, fill: str = NAVY, width: int = 3) -> None:
        self.canvas.create_line(*coords, fill=fill, width=width, tags=("diagram",))

    def _text(
        self,
        x: int,
        y: int,
        text: str,
        *,
        fill: str = NAVY,
        font: tuple[str, int] | tuple[str, int, str] = ("Microsoft YaHei", 10),
    ) -> None:
        self.canvas.create_text(x, y, text=text, fill=fill, font=font, tags=("diagram",))

    @staticmethod
    def _entry_number(value: float) -> str:
        return f"{value:.9g}"


def main() -> None:
    root = tk.Tk()
    MixerDemoApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
