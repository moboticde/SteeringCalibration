from __future__ import annotations

import ctypes
import contextlib
import io
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest


class _FakeMuFunction:
    def __init__(self) -> None:
        self.argtypes = None
        self.restype = None

    def __call__(self, *args, **kwargs):
        return 0


class _FakeMuLibrary:
    def __getattr__(self, _name: str) -> _FakeMuFunction:
        fn = _FakeMuFunction()
        setattr(self, _name, fn)
        return fn


def _load_flash_config_zero_with_fake_mu():
    original_cdll = ctypes.CDLL
    original_modules = {
        name: sys.modules.get(name)
        for name in (
            "drivers.driver_can",
            "drivers.driver_cam_st",
            "drivers.driver_miControlF35",
        )
    }
    ctypes.CDLL = lambda *_args, **_kwargs: _FakeMuLibrary()
    try:
        driver_can = types.ModuleType("drivers.driver_can")
        driver_can.DriverCan = type("DriverCan", (), {})
        sys.modules["drivers.driver_can"] = driver_can

        driver_cam_st = types.ModuleType("drivers.driver_cam_st")
        driver_cam_st.AngleDetection = type("AngleDetection", (), {})
        sys.modules["drivers.driver_cam_st"] = driver_cam_st

        driver_micontrol = types.ModuleType("drivers.driver_miControlF35")
        driver_micontrol.MicontrolF35_CAN = type("MicontrolF35_CAN", (), {})
        sys.modules["drivers.driver_miControlF35"] = driver_micontrol

        module_path = Path(__file__).resolve().with_name("FlashConfigZero.py")
        spec = importlib.util.spec_from_file_location(
            "FlashConfigZero_test_import",
            module_path,
        )
        if spec is None or spec.loader is None:
            raise RuntimeError("Could not load FlashConfigZero.py for tests.")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        ctypes.CDLL = original_cdll
        for name, original in original_modules.items():
            if original is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original


fz = _load_flash_config_zero_with_fake_mu()
from drivers import driver_miControlF35 as mic_driver


@contextlib.contextmanager
def _temporary_visual_scale_cache():
    original_cache_path = fz.ZERO_VISUAL_SCALE_CACHE_PATH
    with tempfile.TemporaryDirectory() as tmpdir:
        fz.ZERO_VISUAL_SCALE_CACHE_PATH = Path(tmpdir) / "visual_zero_scale.json"
        try:
            yield fz.ZERO_VISUAL_SCALE_CACHE_PATH
        finally:
            fz.ZERO_VISUAL_SCALE_CACHE_PATH = original_cache_path


class _FakeVisualController:
    def __init__(self, angle_deg: float, counts_per_rev: float) -> None:
        self.angle_deg = float(angle_deg) % 360.0
        self.position = 0
        self.counts_per_rev = float(counts_per_rev)
        self.commands: list[int] = []
        self.rpms: list[int] = []

    def prepare_position_motion(self, rpm: int) -> bool:
        self.rpms.append(int(rpm))
        return True

    def get_steering_pos(self) -> int:
        return int(self.position)

    def set_steering_pos(self, target_position: int) -> None:
        target_position = int(target_position)
        if not fz._micon_i32_in_range(target_position):
            raise ValueError("target_position outside fake MiControl int32 range")
        delta_counts = target_position - self.position
        self.position = target_position
        self.commands.append(target_position)
        self.angle_deg = (self.angle_deg + delta_counts / self.counts_per_rev * 360.0) % 360.0

    def set_steering_relative(self, correction_counts: int) -> None:
        if not fz._micon_i32_in_range(correction_counts):
            raise ValueError("correction_counts outside fake MiControl int32 range")
        self.set_steering_pos(self.position + int(correction_counts))

    def get_velocity(self) -> int:
        return 0

    def get_ssi_direct_position(self) -> int:
        return int(round(self.angle_deg / 360.0 * 4096.0)) % 4096

    def get_ssi_single_turn_resolution(self) -> int:
        return int(abs(round(self.counts_per_rev)))


class _FakeBadResolutionController(_FakeVisualController):
    def get_ssi_single_turn_resolution(self) -> int:
        return 34


class _FakeSettlingZeroReferenceController:
    def __init__(self, steering_positions: list[int]) -> None:
        self.steering_positions = list(steering_positions)

    def get_steering_pos(self) -> int:
        if self.steering_positions:
            return self.steering_positions.pop(0)
        return 0

    def get_ssi_direct_position(self) -> int:
        return 3

    def get_ssi_encoder_status(self) -> int:
        return fz.CONTROLLER_SSI_READY_STATUS


def _run_visual_zero_quietly(
    mic: _FakeVisualController,
    desired_angle: float,
    read_angle_fn=None,
    require_strict_target: bool = False,
    cache_path: Path | None = None,
) -> float:
    original_sleep = fz.time.sleep
    original_cache_path = fz.ZERO_VISUAL_SCALE_CACHE_PATH
    fz.time.sleep = lambda _seconds: None
    read_angle_fn = read_angle_fn or (lambda: mic.angle_deg)
    try:
        if cache_path is not None:
            fz.ZERO_VISUAL_SCALE_CACHE_PATH = cache_path
            with contextlib.redirect_stdout(io.StringIO()):
                return fz._move_to_visual_zero(
                    mic,
                    mic.angle_deg,
                    desired_angle,
                    read_angle_fn,
                    require_strict_target=require_strict_target,
                )
        with _temporary_visual_scale_cache():
            with contextlib.redirect_stdout(io.StringIO()):
                return fz._move_to_visual_zero(
                    mic,
                    mic.angle_deg,
                    desired_angle,
                    read_angle_fn,
                    require_strict_target=require_strict_target,
                )
    finally:
        fz.time.sleep = original_sleep
        fz.ZERO_VISUAL_SCALE_CACHE_PATH = original_cache_path


class VisualZeroMathTests(unittest.TestCase):
    def test_visual_zero_error_is_literal_desired_minus_current(self):
        self.assertAlmostEqual(fz._visual_zero_error_deg(270.0, 18.39), 251.61)
        self.assertAlmostEqual(fz._visual_zero_error_deg(270.0, 312.0), -42.0)

    def test_visual_angle_distance_uses_shortest_wrap_for_verification(self):
        self.assertAlmostEqual(fz._visual_angle_distance_deg(0.0, 359.0), 1.0)
        self.assertAlmostEqual(fz._visual_angle_distance_deg(359.0, 0.0), -1.0)
        self.assertAlmostEqual(fz._visual_angle_distance_deg(270.0, 312.0), -42.0)

    def test_zero_write_target_tolerance_is_one_degree_and_wrap_aware(self):
        self.assertTrue(fz._visual_zero_is_within_target_tolerance(270.0, 270.99))
        self.assertTrue(fz._visual_zero_is_within_target_tolerance(0.0, 359.75))
        self.assertTrue(fz._visual_zero_is_within_target_tolerance(359.8, 0.1))
        self.assertFalse(fz._visual_zero_is_within_target_tolerance(270.0, 271.01))
        self.assertFalse(fz._visual_zero_is_within_target_tolerance(0.0, 358.9))

    def test_zero_target_check_reports_same_values_used_for_decision(self):
        passing = fz._check_visual_zero_target(0.0, 359.75)
        self.assertAlmostEqual(passing.angle_deg, 359.75)
        self.assertAlmostEqual(passing.target_deg, 0.0)
        self.assertAlmostEqual(passing.error_deg, 0.25)
        self.assertAlmostEqual(passing.tolerance_deg, 1.0)
        self.assertTrue(passing.ok)

        failing = fz._check_visual_zero_target(270.0, 271.01)
        self.assertAlmostEqual(failing.error_deg, -1.01)
        self.assertFalse(failing.ok)

    def test_large_errors_are_limited_with_sign_preserved(self):
        self.assertAlmostEqual(fz._limit_visual_step_deg(230.0, 60.0), 60.0)
        self.assertAlmostEqual(fz._limit_visual_step_deg(-108.0, 60.0), -60.0)
        self.assertAlmostEqual(fz._limit_visual_step_deg(4.0, 60.0), 4.0)

    def test_next_step_limit_tracks_feedback_quality(self):
        self.assertAlmostEqual(fz._next_visual_step_limit_deg(60.0, False), 30.0)
        self.assertAlmostEqual(fz._next_visual_step_limit_deg(7.0, False), 5.0)
        self.assertAlmostEqual(fz._next_visual_step_limit_deg(30.0, True), 37.5)
        self.assertAlmostEqual(fz._next_visual_step_limit_deg(60.0, True), 60.0)

    def test_visual_move_rpm_uses_fine_speed_for_small_steps(self):
        self.assertEqual(fz._visual_move_rpm_for_step(10.0), fz.ZERO_VISUAL_FINE_MOVE_RPM)
        self.assertEqual(fz._visual_move_rpm_for_step(-4.0), fz.ZERO_VISUAL_FINE_MOVE_RPM)
        self.assertEqual(fz._visual_move_rpm_for_step(10.1), fz.ZERO_VISUAL_MOVE_RPM)

    def test_correction_counts_preserve_learned_scale_sign(self):
        self.assertEqual(fz._visual_correction_counts(1.0, 170.0), 1)
        self.assertEqual(fz._visual_correction_counts(-1.0, 170.0), -1)
        self.assertEqual(fz._visual_correction_counts(1.0, -170.0), -1)
        self.assertEqual(fz._visual_correction_counts(-1.0, -170.0), 1)

    def test_acceptance_tolerance_respects_controller_resolution(self):
        self.assertAlmostEqual(fz._visual_acceptance_tolerance_deg(4096.0), 1.0)
        self.assertAlmostEqual(fz._visual_acceptance_tolerance_deg(170.0), 180.0 / 170.0)
        self.assertAlmostEqual(fz._visual_acceptance_tolerance_deg(-170.0), 180.0 / 170.0)

    def test_initial_visual_scale_uses_controller_ssi_resolution(self):
        mic = _FakeVisualController(angle_deg=210.0, counts_per_rev=4096.0)
        with _temporary_visual_scale_cache():
            self.assertAlmostEqual(fz._initial_visual_controller_counts_per_rev(mic), 4096.0)

    def test_initial_visual_scale_ignores_stale_cached_scale_outside_expected_regions(self):
        mic = _FakeVisualController(angle_deg=210.0, counts_per_rev=4096.0)
        mic.node_id = 50
        with _temporary_visual_scale_cache() as cache_path:
            cache_path.write_text(
                json.dumps(
                    {
                        "node_50": {
                            "controller_counts_per_rev": 104.151,
                            "updated_unix_s": 1,
                        }
                    }
                ),
                encoding="utf-8",
            )
            self.assertAlmostEqual(fz._initial_visual_controller_counts_per_rev(mic), 4096.0)

    def test_initial_visual_scale_falls_back_when_resolution_invalid(self):
        class InvalidResolutionController:
            def get_ssi_single_turn_resolution(self):
                return 0

        with _temporary_visual_scale_cache():
            self.assertAlmostEqual(
                fz._initial_visual_controller_counts_per_rev(InvalidResolutionController()),
                fz.ZERO_VISUAL_FALLBACK_CONTROLLER_COUNTS_PER_REV,
            )

    def test_micon_position_helpers_use_signed_32_bit_counter_range(self):
        self.assertTrue(fz._micon_i32_in_range(-(2**31)))
        self.assertTrue(fz._micon_i32_in_range(2**31 - 1))
        self.assertFalse(fz._micon_i32_in_range(-(2**31) - 1))
        self.assertFalse(fz._micon_i32_in_range(2**31))
        self.assertEqual(
            fz._expected_micon_counter_after_relative_move(100, -25),
            75,
        )

    def test_micon_expected_counter_rejects_overflow(self):
        with self.assertRaises(RuntimeError):
            fz._expected_micon_counter_after_relative_move(2**31 - 2, 10)

    def test_driver_steering_commands_use_signed_32_bit_range(self):
        self.assertEqual(mic_driver._checked_i32(2**31 - 1, "unit"), 2**31 - 1)
        with self.assertRaises(ValueError):
            mic_driver._checked_i32(2**31, "unit")

    def test_move_planner_caps_large_errors(self):
        step_deg, revs, counts, expected_delta = fz._plan_visual_zero_move(
            230.0,
            170.0,
            60.0,
        )
        self.assertAlmostEqual(step_deg, 60.0)
        self.assertAlmostEqual(revs, 60.0 / 360.0)
        self.assertEqual(counts, 28)
        self.assertAlmostEqual(expected_delta, 28 / 170.0 * 360.0)

    def test_move_planner_uses_reversed_scale_sign(self):
        step_deg, revs, counts, expected_delta = fz._plan_visual_zero_move(
            1.0,
            -170.0,
            60.0,
        )
        self.assertAlmostEqual(step_deg, 1.0)
        self.assertAlmostEqual(revs, 1.0 / 360.0)
        self.assertEqual(counts, -1)
        self.assertAlmostEqual(expected_delta, (-1 / -170.0) * 360.0)

    def test_camera_delta_chooses_wrap_that_matches_expected_motion(self):
        self.assertAlmostEqual(fz._visual_motion_delta_deg(10.0, 350.0, 20.0), 20.0)
        self.assertAlmostEqual(fz._visual_motion_delta_deg(350.0, 10.0, -20.0), -20.0)

    def test_camera_delta_can_detect_reversed_motion(self):
        self.assertAlmostEqual(fz._visual_motion_delta_deg(210.0, 270.0, 60.0), -60.0)

    def test_plausible_scale_accepts_reversed_sign(self):
        self.assertTrue(fz._scale_update_is_plausible(-170.0, -60.0, 60.0))
        self.assertTrue(fz._scale_update_is_plausible(4096.0, 2.4609375, 59.294117647))

    def test_implausible_scale_response_is_rejected(self):
        self.assertFalse(fz._scale_update_is_plausible(6.0, 140.0, 12.0))
        self.assertFalse(fz._scale_update_is_plausible(170.0, 1.0, 1.0))
        self.assertFalse(fz._scale_update_is_plausible(72.0, 140.0, 59.0))

    def test_scale_rejection_reason_explains_failed_gate(self):
        self.assertIsNone(fz._scale_update_rejection_reason(170.0, 60.0, 60.0))
        self.assertIn(
            "outside allowed range",
            fz._scale_update_rejection_reason(6.0, 140.0, 12.0),
        )
        self.assertIn(
            "below minimum feedback",
            fz._scale_update_rejection_reason(170.0, 1.0, 1.0),
        )
        self.assertIn(
            "ratio outside allowed range",
            fz._scale_update_rejection_reason(72.0, 140.0, 59.0),
        )

    def test_candidate_scale_helper_accepts_valid_feedback(self):
        self.assertAlmostEqual(
            fz._candidate_controller_counts_per_rev(28, 59.294117647, 59.294117647),
            170.0,
            places=6,
        )
        self.assertAlmostEqual(
            fz._candidate_controller_counts_per_rev(28, 2.4609375, 59.294117647),
            4096.0,
            places=6,
        )
        self.assertAlmostEqual(
            fz._candidate_controller_counts_per_rev(28, -59.294117647, 59.294117647),
            -170.0,
            places=6,
        )

    def test_candidate_scale_helper_rejects_bad_feedback(self):
        self.assertIsNone(fz._candidate_controller_counts_per_rev(1, 1.0, 2.0))
        self.assertIsNone(fz._candidate_controller_counts_per_rev(1, 140.0, 12.0))

    def test_direct_encoder_scale_helper_accepts_valid_probe(self):
        self.assertAlmostEqual(
            fz._candidate_controller_counts_per_rev_from_encoder(3, 102.4),
            120.0,
            places=6,
        )
        self.assertAlmostEqual(
            fz._candidate_controller_counts_per_rev_from_encoder(3, 3.0),
            4096.0,
            places=6,
        )
        self.assertIsNone(fz._candidate_controller_counts_per_rev_from_encoder(1, 1.0))

    def test_visual_zero_loop_converges_with_fake_controller(self):
        mic = _FakeVisualController(angle_deg=210.0, counts_per_rev=170.0)
        final_angle = _run_visual_zero_quietly(mic, 270.0)

        tolerance = fz._visual_acceptance_tolerance_deg(170.0)
        self.assertLessEqual(abs(fz._visual_angle_distance_deg(270.0, final_angle)), tolerance)
        self.assertGreaterEqual(len(mic.commands), 1)

    def test_visual_zero_loop_does_not_move_when_already_within_tolerance(self):
        mic = _FakeVisualController(angle_deg=270.25, counts_per_rev=4096.0)
        final_angle = _run_visual_zero_quietly(mic, 270.0)

        self.assertAlmostEqual(final_angle, 270.25)
        self.assertEqual(mic.commands, [])

    def test_visual_zero_loop_handles_wraparound_target(self):
        mic = _FakeVisualController(angle_deg=350.0, counts_per_rev=4096.0)
        final_angle = _run_visual_zero_quietly(mic, 10.0)

        self.assertLessEqual(abs(fz._visual_angle_distance_deg(10.0, final_angle)), 1.0)
        self.assertGreaterEqual(len(mic.commands), 2)

    def test_visual_zero_loop_recovers_from_one_stale_camera_read(self):
        mic = _FakeVisualController(angle_deg=210.0, counts_per_rev=4096.0)
        stale_angle = mic.angle_deg
        reads = 0

        def read_angle():
            nonlocal reads
            reads += 1
            if reads == 1:
                return stale_angle
            return mic.angle_deg

        final_angle = _run_visual_zero_quietly(mic, 270.0, read_angle)

        self.assertGreaterEqual(reads, 2)
        self.assertLessEqual(abs(fz._visual_angle_distance_deg(270.0, final_angle)), 1.0)
        self.assertGreaterEqual(len(mic.commands), 1)

    def test_visual_zero_loop_recovers_from_repeated_stale_camera_reads(self):
        mic = _FakeVisualController(angle_deg=210.0, counts_per_rev=4096.0)
        stale_angle = mic.angle_deg
        reads = 0

        def read_angle():
            nonlocal reads
            reads += 1
            if reads <= 2:
                return stale_angle
            return mic.angle_deg

        final_angle = _run_visual_zero_quietly(mic, 270.0, read_angle)

        self.assertGreaterEqual(reads, 3)
        self.assertLessEqual(abs(fz._visual_angle_distance_deg(270.0, final_angle)), 1.0)
        self.assertGreaterEqual(len(mic.commands), 1)

    def test_visual_zero_probe_learns_bad_reported_controller_resolution(self):
        with _temporary_visual_scale_cache() as cache_path:
            mic = _FakeBadResolutionController(angle_deg=207.0, counts_per_rev=120.0)
            final_angle = _run_visual_zero_quietly(mic, 270.0, cache_path=cache_path)

            self.assertLessEqual(abs(fz._visual_angle_distance_deg(270.0, final_angle)), 1.5)
            self.assertEqual(mic.commands[0], fz.ZERO_VISUAL_SCALE_PROBE_COUNTS)
            self.assertTrue(cache_path.is_file())

            second_mic = _FakeBadResolutionController(angle_deg=207.0, counts_per_rev=120.0)
            second_final_angle = _run_visual_zero_quietly(
                second_mic,
                270.0,
                cache_path=cache_path,
            )

            self.assertLessEqual(
                abs(fz._visual_angle_distance_deg(270.0, second_final_angle)),
                1.5,
            )
            self.assertEqual(second_mic.commands[0], fz.ZERO_VISUAL_SCALE_PROBE_COUNTS)

    def test_visual_zero_loop_learns_reversed_controller_scale(self):
        mic = _FakeVisualController(angle_deg=210.0, counts_per_rev=-170.0)
        final_angle = _run_visual_zero_quietly(mic, 270.0)

        tolerance = fz._visual_acceptance_tolerance_deg(-170.0)
        self.assertLessEqual(abs(fz._visual_angle_distance_deg(270.0, final_angle)), tolerance)
        self.assertGreaterEqual(len(mic.commands), 1)

    def test_visual_zero_loop_learns_high_resolution_controller_scale(self):
        mic = _FakeVisualController(angle_deg=210.0, counts_per_rev=4096.0)
        final_angle = _run_visual_zero_quietly(mic, 270.0)

        self.assertLessEqual(abs(fz._visual_angle_distance_deg(270.0, final_angle)), 1.0)
        self.assertEqual(len(mic.commands), 1)
        self.assertEqual(mic.commands[0], 683)
        self.assertEqual(mic.rpms, [fz.ZERO_VISUAL_MOVE_RPM])

    def test_visual_zero_loop_uses_fine_rpm_for_small_adjustment(self):
        mic = _FakeVisualController(angle_deg=262.0, counts_per_rev=4096.0)
        final_angle = _run_visual_zero_quietly(mic, 270.0)

        self.assertLessEqual(abs(fz._visual_angle_distance_deg(270.0, final_angle)), 1.0)
        self.assertEqual(mic.commands, [91])
        self.assertEqual(mic.rpms, [fz.ZERO_VISUAL_FINE_MOVE_RPM])

    def test_strict_visual_zero_mode_reaches_one_degree_target(self):
        mic = _FakeVisualController(angle_deg=210.0, counts_per_rev=4096.0)
        final_angle = _run_visual_zero_quietly(
            mic,
            270.0,
            require_strict_target=True,
        )

        self.assertTrue(fz._visual_zero_is_within_target_tolerance(270.0, final_angle))
        self.assertEqual(len(mic.commands), 1)

    def test_strict_visual_zero_mode_rejects_relaxed_only_result(self):
        mic = _FakeVisualController(angle_deg=210.2, counts_per_rev=130.0)

        with self.assertRaises(RuntimeError):
            _run_visual_zero_quietly(
                mic,
                270.0,
                require_strict_target=True,
            )

    def test_controller_zero_save_guard_restores_visual_zero(self):
        mic = _FakeVisualController(angle_deg=268.0, counts_per_rev=4096.0)
        original_sleep = fz.time.sleep
        fz.time.sleep = lambda _seconds: None
        try:
            with _temporary_visual_scale_cache():
                with contextlib.redirect_stdout(io.StringIO()):
                    final_angle = fz._restore_visual_zero_before_controller_save(
                        mic,
                        270.0,
                        lambda: mic.angle_deg,
                    )
        finally:
            fz.time.sleep = original_sleep

        self.assertTrue(fz._visual_zero_is_within_target_tolerance(270.0, final_angle))
        self.assertGreaterEqual(len(mic.commands), 1)

    def test_controller_zero_reference_verification_waits_for_settling_readback(self):
        mic = _FakeSettlingZeroReferenceController([57, 25, 8, 3])
        original_sleep = fz.time.sleep
        fz.time.sleep = lambda _seconds: None
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertTrue(fz._verify_controller_zero_reference(mic, "unit test"))
        finally:
            fz.time.sleep = original_sleep

    def test_zero_write_preservation_allows_only_zero_related_changes(self):
        before = {idx: (0, idx) for idx in range(fz.MU_STABLE_CONFIG_PARAM_LAST + 1)}
        after = dict(before)
        for idx in fz.ZERO_WRITE_ALLOWED_PARAM_INDEXES:
            if idx in after:
                after[idx] = (1, idx + 1)

        with contextlib.redirect_stdout(io.StringIO()):
            self.assertTrue(
                fz._verify_zero_write_preserved_nonzero_config(
                    before,
                    after,
                    "unit test allowed zero changes",
                )
            )

        after[69] = (9, 9)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertFalse(
                fz._verify_zero_write_preserved_nonzero_config(
                    before,
                    after,
                    "unit test blocked calibration change",
                )
            )


if __name__ == "__main__":
    unittest.main()
