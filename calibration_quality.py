from __future__ import annotations

import argparse
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Sequence

from interrupt_guard import install_deferred_keyboard_interrupt


DEFAULT_FINAL_RESIDUAL_CAP_LSB = 20.0
DEFAULT_MAX_PHASE_MARGIN_PCT = 50.0

_RESIDUAL_LINE_RE = re.compile(
    r"cosGain=(?P<cosine_gain>[+-]?\d+(?:\.\d+)?),"
    r"sinOff=(?P<sine_offset>[+-]?\d+(?:\.\d+)?),"
    r"cosOff=(?P<cosine_offset>[+-]?\d+(?:\.\d+)?),"
    r"phase=(?P<phase>[+-]?\d+(?:\.\d+)?)"
)
_HISTORY_LINE_RE = re.compile(
    r"label=(?P<label>[^,]+),"
    r"analog_valid=(?P<analog_valid>True|False),"
    r"master=(?P<master>[^|]+)\|"
    r"nonius=(?P<nonius>.+)"
)


@dataclass(frozen=True)
class ResidualVector:
    cosine_gain_lsb: float
    sine_offset_lsb: float
    cosine_offset_lsb: float
    phase_lsb: float

    @classmethod
    def from_values(cls, values: Iterable[float]) -> "ResidualVector":
        cosine_gain, sine_offset, cosine_offset, phase = values
        return cls(
            cosine_gain_lsb=float(cosine_gain),
            sine_offset_lsb=float(sine_offset),
            cosine_offset_lsb=float(cosine_offset),
            phase_lsb=float(phase),
        )

    @classmethod
    def from_report_line(cls, line: str) -> "ResidualVector":
        match = _RESIDUAL_LINE_RE.fullmatch(line.strip())
        if not match:
            raise ValueError(f"Could not parse residual line: {line!r}")
        return cls(
            cosine_gain_lsb=float(match.group("cosine_gain")),
            sine_offset_lsb=float(match.group("sine_offset")),
            cosine_offset_lsb=float(match.group("cosine_offset")),
            phase_lsb=float(match.group("phase")),
        )

    def max_abs(self) -> float:
        return max(
            abs(self.cosine_gain_lsb),
            abs(self.sine_offset_lsb),
            abs(self.cosine_offset_lsb),
            abs(self.phase_lsb),
        )

    def to_report_line(self) -> str:
        return (
            f"cosGain={self.cosine_gain_lsb:+.4f},"
            f"sinOff={self.sine_offset_lsb:+.4f},"
            f"cosOff={self.cosine_offset_lsb:+.4f},"
            f"phase={self.phase_lsb:+.4f}"
        )


@dataclass(frozen=True)
class AnalogResidualRun:
    label: str
    analog_valid: bool
    master_residuals: ResidualVector
    nonius_residuals: ResidualVector

    def to_report_line(self) -> str:
        return (
            f"label={self.label},"
            f"analog_valid={self.analog_valid},"
            f"master={self.master_residuals.to_report_line()}|"
            f"nonius={self.nonius_residuals.to_report_line()}"
        )


@dataclass(frozen=True)
class AcquisitionTiming:
    requested_frame_cycle_time_s: float
    actual_frame_cycle_time_s: float
    requested_clock_frequency_hz: float
    actual_clock_frequency_hz: float


@dataclass(frozen=True)
class CalibrationMetrics:
    analog_valid: bool
    nonius_valid: bool
    master_residuals: ResidualVector
    nonius_residuals: ResidualVector
    max_abs_analog_residual_lsb: float
    phase_range_limit_lsb: int
    phase_margin_max_lsb: int
    phase_margin_min_lsb: int
    max_abs_phase_margin_pct_of_range_limit: float
    upper_phase_margin_pct: float
    lower_phase_margin_pct: float
    max_abs_phase_error_lsb: int
    analyze_log: str = ""
    analog_residual_history: tuple[AnalogResidualRun, ...] = field(default_factory=tuple)
    acquisition_timing: AcquisitionTiming | None = None


@dataclass(frozen=True)
class QualityEvaluation:
    ok: bool
    reason: str
    failed_checks: tuple[str, ...]
    final_residual_cap_lsb: float
    max_phase_margin_pct: float


def evaluate_quality(
    metrics: CalibrationMetrics,
    final_residual_cap_lsb: float = DEFAULT_FINAL_RESIDUAL_CAP_LSB,
    max_phase_margin_pct: float = DEFAULT_MAX_PHASE_MARGIN_PCT,
) -> QualityEvaluation:
    failed_checks: list[str] = []

    if not metrics.analog_valid:
        failed_checks.append("analog analysis invalid")
    if not metrics.nonius_valid:
        failed_checks.append("nonius analysis invalid")
    if metrics.max_abs_analog_residual_lsb > final_residual_cap_lsb:
        failed_checks.append(
            f"analog residual {metrics.max_abs_analog_residual_lsb:.4f} LSB > "
            f"{final_residual_cap_lsb:.4f} LSB"
        )
    if metrics.max_abs_phase_margin_pct_of_range_limit > max_phase_margin_pct:
        failed_checks.append(
            f"nonius phase margin {metrics.max_abs_phase_margin_pct_of_range_limit:.3f}% "
            f"of range limit > {max_phase_margin_pct:.3f}%"
        )

    if failed_checks:
        reason = "; ".join(failed_checks)
        return QualityEvaluation(
            ok=False,
            reason=reason,
            failed_checks=tuple(failed_checks),
            final_residual_cap_lsb=float(final_residual_cap_lsb),
            max_phase_margin_pct=float(max_phase_margin_pct),
        )

    reason = (
        f"accepted: residual {metrics.max_abs_analog_residual_lsb:.4f} LSB <= "
        f"{final_residual_cap_lsb:.4f} LSB and nonius phase margin "
        f"{metrics.max_abs_phase_margin_pct_of_range_limit:.3f}% <= "
        f"{max_phase_margin_pct:.3f}% of range limit"
    )
    return QualityEvaluation(
        ok=True,
        reason=reason,
        failed_checks=(),
        final_residual_cap_lsb=float(final_residual_cap_lsb),
        max_phase_margin_pct=float(max_phase_margin_pct),
    )


def build_quality_report(
    attempt_idx: int,
    metrics: CalibrationMetrics,
    evaluation: QualityEvaluation,
) -> str:
    lines = [
        f"attempt={attempt_idx}",
        f"analog_valid={metrics.analog_valid}",
        f"nonius_valid={metrics.nonius_valid}",
        f"master_residuals_lsb={metrics.master_residuals.to_report_line()}",
        f"nonius_residuals_lsb={metrics.nonius_residuals.to_report_line()}",
        f"max_abs_analog_residual_lsb={metrics.max_abs_analog_residual_lsb:.4f}",
        f"final_residual_cap_lsb={evaluation.final_residual_cap_lsb:.4f}",
        f"phase_range_limit_lsb={metrics.phase_range_limit_lsb}",
        f"phase_margin_max_lsb={metrics.phase_margin_max_lsb}",
        f"phase_margin_min_lsb={metrics.phase_margin_min_lsb}",
        (
            "max_abs_phase_margin_pct_of_range_limit="
            f"{metrics.max_abs_phase_margin_pct_of_range_limit:.3f}"
        ),
        f"upper_phase_clearance_pct={metrics.upper_phase_margin_pct:.3f}",
        f"lower_phase_clearance_pct={metrics.lower_phase_margin_pct:.3f}",
        f"max_allowed_phase_margin_pct={evaluation.max_phase_margin_pct:.3f}",
        f"max_abs_phase_error_lsb={metrics.max_abs_phase_error_lsb}",
        f"quality_ok={evaluation.ok}",
        f"quality_gate_reason={evaluation.reason}",
    ]

    if metrics.acquisition_timing is not None:
        lines.extend(
            [
                (
                    "requested_frame_cycle_time_s="
                    f"{metrics.acquisition_timing.requested_frame_cycle_time_s:.12f}"
                ),
                (
                    "actual_frame_cycle_time_s="
                    f"{metrics.acquisition_timing.actual_frame_cycle_time_s:.12f}"
                ),
                (
                    "requested_clock_frequency_hz="
                    f"{metrics.acquisition_timing.requested_clock_frequency_hz:.3f}"
                ),
                (
                    "actual_clock_frequency_hz="
                    f"{metrics.acquisition_timing.actual_clock_frequency_hz:.3f}"
                ),
            ]
        )

    if metrics.analog_residual_history:
        lines.append("")
        lines.append("Analog residual history:")
        for index, run in enumerate(metrics.analog_residual_history, 1):
            lines.append(f"analog_history_{index:02d}={run.to_report_line()}")

    lines.append("")
    lines.append("Analyze result log:")
    lines.append(metrics.analyze_log or "<empty>")
    return "\n".join(lines)


def parse_quality_report(path: Path) -> CalibrationMetrics:
    text = path.read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines()
    analyze_idx = next(
        (index for index, line in enumerate(lines) if line.strip() == "Analyze result log:"),
        len(lines),
    )

    key_values: dict[str, str] = {}
    master_residuals = None
    nonius_residuals = None
    analog_residual_history: list[AnalogResidualRun] = []

    for raw_line in lines[:analyze_idx]:
        line = raw_line.strip()
        if not line or line == "Analog residual history:":
            continue
        if line.startswith("master_residuals_lsb="):
            master_residuals = ResidualVector.from_report_line(line.split("=", 1)[1])
            continue
        if line.startswith("nonius_residuals_lsb="):
            nonius_residuals = ResidualVector.from_report_line(line.split("=", 1)[1])
            continue
        if line.startswith("analog_history_"):
            match = _HISTORY_LINE_RE.fullmatch(line.split("=", 1)[1])
            if match:
                analog_residual_history.append(
                    AnalogResidualRun(
                        label=match.group("label"),
                        analog_valid=match.group("analog_valid") == "True",
                        master_residuals=ResidualVector.from_report_line(match.group("master")),
                        nonius_residuals=ResidualVector.from_report_line(match.group("nonius")),
                    )
                )
            continue
        if "=" in line:
            key, value = line.split("=", 1)
            key_values[key] = value

    if master_residuals is None or nonius_residuals is None:
        raise ValueError(f"Missing residual vectors in report: {path}")

    analyze_log = "\n".join(lines[analyze_idx + 1 :]).strip()

    timing = None
    if "requested_frame_cycle_time_s" in key_values and "actual_frame_cycle_time_s" in key_values:
        timing = AcquisitionTiming(
            requested_frame_cycle_time_s=float(key_values["requested_frame_cycle_time_s"]),
            actual_frame_cycle_time_s=float(key_values["actual_frame_cycle_time_s"]),
            requested_clock_frequency_hz=float(key_values.get("requested_clock_frequency_hz", "0")),
            actual_clock_frequency_hz=float(key_values.get("actual_clock_frequency_hz", "0")),
        )

    phase_margin_key = "max_abs_phase_margin_pct_of_range_limit"
    if phase_margin_key not in key_values and "max_abs_phase_margin_pct" in key_values:
        phase_margin_key = "max_abs_phase_margin_pct"

    return CalibrationMetrics(
        analog_valid=key_values["analog_valid"] == "True",
        nonius_valid=key_values["nonius_valid"] == "True",
        master_residuals=master_residuals,
        nonius_residuals=nonius_residuals,
        max_abs_analog_residual_lsb=float(key_values["max_abs_analog_residual_lsb"]),
        phase_range_limit_lsb=int(float(key_values["phase_range_limit_lsb"])),
        phase_margin_max_lsb=int(float(key_values["phase_margin_max_lsb"])),
        phase_margin_min_lsb=int(float(key_values["phase_margin_min_lsb"])),
        max_abs_phase_margin_pct_of_range_limit=float(key_values[phase_margin_key]),
        upper_phase_margin_pct=float(
            key_values["upper_phase_clearance_pct"]
            if "upper_phase_clearance_pct" in key_values
            else key_values["upper_phase_margin_pct"]
        ),
        lower_phase_margin_pct=float(
            key_values["lower_phase_clearance_pct"]
            if "lower_phase_clearance_pct" in key_values
            else key_values["lower_phase_margin_pct"]
        ),
        max_abs_phase_error_lsb=int(float(key_values["max_abs_phase_error_lsb"])),
        analyze_log=analyze_log if analyze_log != "<empty>" else "",
        analog_residual_history=tuple(analog_residual_history),
        acquisition_timing=timing,
    )


def collect_report_paths(paths: Sequence[Path | str]) -> list[Path]:
    report_paths: list[Path] = []
    for item in paths:
        path = Path(item)
        if path.is_dir():
            report_paths.extend(sorted(path.rglob("calibration_report_attempt_*.txt")))
        elif path.is_file():
            report_paths.append(path)
    return sorted(set(report_paths))


def analyze_report_paths(
    paths: Sequence[Path | str],
    final_residual_cap_lsb: float = DEFAULT_FINAL_RESIDUAL_CAP_LSB,
    max_phase_margin_pct: float = DEFAULT_MAX_PHASE_MARGIN_PCT,
) -> list[tuple[Path, CalibrationMetrics, QualityEvaluation]]:
    results: list[tuple[Path, CalibrationMetrics, QualityEvaluation]] = []
    for report_path in collect_report_paths(paths):
        metrics = parse_quality_report(report_path)
        evaluation = evaluate_quality(
            metrics,
            final_residual_cap_lsb=final_residual_cap_lsb,
            max_phase_margin_pct=max_phase_margin_pct,
        )
        results.append((report_path, metrics, evaluation))
    return results


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Offline smoke analysis for iC-MU calibration reports."
    )
    parser.add_argument(
        "paths",
        nargs="+",
        help="Calibration report files or directories that contain calibration_report_attempt_*.txt",
    )
    parser.add_argument(
        "--final-residual-cap-lsb",
        type=float,
        default=DEFAULT_FINAL_RESIDUAL_CAP_LSB,
        help="Final acceptance cap for max_abs_analog_residual_lsb.",
    )
    parser.add_argument(
        "--max-phase-margin-pct",
        type=float,
        default=DEFAULT_MAX_PHASE_MARGIN_PCT,
        help="Maximum allowed nonius phase margin percent of the phase range limit.",
    )
    parser.add_argument(
        "--min-phase-margin-pct",
        type=float,
        dest="max_phase_margin_pct",
        default=argparse.SUPPRESS,
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args(argv)

    results = analyze_report_paths(
        args.paths,
        final_residual_cap_lsb=args.final_residual_cap_lsb,
        max_phase_margin_pct=args.max_phase_margin_pct,
    )
    if not results:
        print("No calibration reports found.")
        return 1

    overall_ok = True
    for report_path, metrics, evaluation in results:
        status = "PASS" if evaluation.ok else "FAIL"
        overall_ok &= evaluation.ok
        print(
            f"[{status}] {report_path} "
            f"residual={metrics.max_abs_analog_residual_lsb:.4f} LSB "
            f"phase_margin={metrics.max_abs_phase_margin_pct_of_range_limit:.3f}% "
            f"max_allowed={evaluation.max_phase_margin_pct:.3f}% "
            f"upper_clearance={metrics.upper_phase_margin_pct:.3f}% "
            f"lower_clearance={metrics.lower_phase_margin_pct:.3f}% "
            f"reason={evaluation.reason}"
        )

    return 0 if overall_ok else 1


if __name__ == "__main__":
    restore_sigint = install_deferred_keyboard_interrupt(label="calibration quality analysis")
    try:
        raise SystemExit(main())
    finally:
        restore_sigint()
