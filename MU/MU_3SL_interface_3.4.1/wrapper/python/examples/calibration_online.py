#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Copyright 2022 iC-Haus GmbH

Software and its documentation is provided by iC-Haus GmbH or contributors "AS IS" and is
subject to the ZVEI General Conditions for the Supply of Products and Services with iC-Haus
amendments and the ZVEI Software clause with iC-Haus amendments (http://www.ichaus.de/EULA).
"""

import mu_3sl_interface as mu_3sl


acquire_frame_cycle_time_s = 187.5E-6
acquire_clock_frequency_hz = 2E6
# Calculation of the number of samples based on acquisition time in seconds
acquisition_time_s = 5.0
number_of_samples = round(acquisition_time_s / acquire_frame_cycle_time_s)
# number_of_samples = 10000; # min. 16 (recommended 128) values per period

print("Library version: {}".format(mu_3sl.__version__))

# Construct a new instance of a virtual chip object and obtain a handle for it.
mu = mu_3sl.MuHandle()

# Connect the interface (USB-BiSS adapter) MB5U
mu.set_interface(mu_3sl.Interface.MB5U, "")

revisionCode = mu.read_chip_revision()
mu.use_revision(revisionCode)

# Read all configuration parameters from the connected iC-MU* in the virtual chip object
mu.read_parameters()

calibration = mu.get_calibration()

master_period_code = mu.get_parameter(mu_3sl.Parameter.MPC)

print("\n" +
      "---------------------------------------------------------------\n" +
      "- Reset current analog track adjustments (loaded from EEPROM) -\n" +
      "---------------------------------------------------------------")

initialMasterAdjustments = mu_3sl.AnalogTrackAdjustments()
initialMasterAdjustments.cosine_gain = 0
initialMasterAdjustments.sine_offset = 0
initialMasterAdjustments.cosine_offset = 0
initialMasterAdjustments.phase = 0
initialMasterAdjustments.phase_range = 0

initialNoniusAdjustments = mu_3sl.AnalogTrackAdjustments()
initialNoniusAdjustments.cosine_gain = 0
initialNoniusAdjustments.sine_offset = 0
initialNoniusAdjustments.cosine_offset = 0
initialNoniusAdjustments.phase = 0
initialNoniusAdjustments.phase_range = 0

calibration.set_current_analog_track_adjustments(initialMasterAdjustments, initialNoniusAdjustments)

mu.set_calibration(calibration)
mu.write_parameters()

print("Initial iC-MU signal conditioning parameters:")


def print_analog_track_adjustments(adjustments: mu_3sl.AnalogTrackAdjustments,
                                   track_short_name: str):
    print(("Cosine gain (GX_{0}):     {1:4d} (0x{1:04X})\n" +
           "Sine offset (VOSS_{0}):   {2:4d} (0x{2:04X})\n" +
           "Cosine offset (VOSC_{0}): {3:4d} (0x{3:04X})\n" +
           "Phase (PH_{0}):           {4:4d} (0x{4:04X})\n" +
           "Phase range (PHR_{0}):    {5:4d} (0x{5:04X})").format(track_short_name,
                                                                  adjustments.cosine_gain,
                                                                  adjustments.sine_offset,
                                                                  adjustments.cosine_offset,
                                                                  adjustments.phase,
                                                                  adjustments.phase_range))


def print_analog_adjustments(calibration: mu_3sl.Calibration):
    masterTrackAdjustments = calibration.analog_master_track_adjustments()
    print_analog_track_adjustments(masterTrackAdjustments, "M")
    noniusTrackAdjustments = calibration.analog_nonius_track_adjustments()
    print_analog_track_adjustments(noniusTrackAdjustments, "N")


print_analog_adjustments(calibration)
print("")

print("\n" +
      "---------------------------------------------------------------\n" +
      "----------------- Analog Calibration of iC-MU -----------------\n" +
      "---------------------------------------------------------------")

mu.activate_calibration_configuration()
try:
    masterRawData, noniusRawData = mu.acquire_raw_data(number_of_samples, 0,
                                                       acquire_frame_cycle_time_s,
                                                       acquire_clock_frequency_hz)
finally:
    mu.deactivate_calibration_configuration()

analyze_result = calibration.analyze_raw_data(masterRawData, noniusRawData)

print(analyze_result.log(mu_3sl.CalibrationAnalyzeResultLogLevel.ALL))

print("Relative track adjustments (relative changes in \"LSB\")")


def print_relative_adjustments(analyze_result: mu_3sl.AnalyzeResult):
    relativeMasterTrackAdjustments = analyze_result.relative_master_track_adjustments()
    relativeNoniusTrackAdjustments = analyze_result.relative_nonius_track_adjustments()
    print(("Track:             Master |   Nonius\n" +
           "  Cosine gain:   {:8.4f} | {:8.4f}\n" +
           "  Sine offset:   {:8.4f} | {:8.4f}\n" +
           "  Cosine offset: {:8.4f} | {:8.4f}\n" +
           "  Phase adjust:  {:8.4f} | {:8.4f}\n").format(
        relativeMasterTrackAdjustments.cosine_gain_lsb,
        relativeNoniusTrackAdjustments.cosine_gain_lsb,
        relativeMasterTrackAdjustments.sine_offset_lsb,
        relativeNoniusTrackAdjustments.sine_offset_lsb,
        relativeMasterTrackAdjustments.cosine_offset_lsb,
        relativeNoniusTrackAdjustments.cosine_offset_lsb,
        relativeMasterTrackAdjustments.phase_lsb,
        relativeNoniusTrackAdjustments.phase_lsb)
    )


print_relative_adjustments(analyze_result)

is_adjustable, adjustment_message = calibration.is_analog_analyze_result_adjustable(
    analyze_result,
    mu_3sl.CalibrationAnalyzeResultLogLevel.ALL)
if is_adjustable:
    print("Analyze result is adjustable.\nMessage:\n{}".format(adjustment_message))
else:
    print("Analyze result is not adjustable.\nMessage:\n{}".format(adjustment_message))

calibration.adjust_analog_by_analyze_result(analyze_result)

print("iC-MU signal conditioning parameters after calibration:")
print_analog_adjustments(calibration)

mu.set_calibration(calibration)
mu.write_parameters()

print("\n" +
      "---------------------------------------------------------------\n" +
      "----------------- Nonius Calibration of iC-MU -----------------\n" +
      "---------------------------------------------------------------")

mu.activate_calibration_configuration()
try:
    masterRawData, noniusRawData = mu.acquire_raw_data(number_of_samples, 0,
                                                       acquire_frame_cycle_time_s,
                                                       acquire_clock_frequency_hz)
finally:
    mu.deactivate_calibration_configuration()

analyze_result = calibration.analyze_raw_data(masterRawData, noniusRawData)

print(analyze_result.log(mu_3sl.CalibrationAnalyzeResultLogLevel.ALL))

print("Residual errors (relative changes in \"LSB\")")
print_relative_adjustments(analyze_result)



def optionalPrintOptimizedNoniusTrackOffsetTable(analyze_result: mu_3sl.AnalyzeResult,
                                                 master_period_code: int):
    nonius_track_offset_table = analyze_result.optimized_nonius_track_offset_table()
    print("Optimized nonius track offset table:")
    print("SPO_BASE: {:2d}".format(nonius_track_offset_table.spo_base))
    for i in range(16):
        if i >= 10:
            print("SPO_{:d}:   {:2d}".format(i, nonius_track_offset_table[i]))
        else:
            print("SPO_{:d}:    {:2d}".format(i, nonius_track_offset_table[i]))
    print("")

    nonius_calibration_max_allow_phase_error = 1 << (14 - 1 - master_period_code)
    nonius_phase_margin_max = analyze_result.nonius_phase_margin_max()
    nonius_phase_margin_min = analyze_result.nonius_phase_margin_min()
    nonius_phase_margin_max_percent = (
            nonius_phase_margin_max / nonius_calibration_max_allow_phase_error * 100)
    nonius_phase_margin_min_percent = (
            nonius_phase_margin_min / -nonius_calibration_max_allow_phase_error * 100)
    print("Nonius phase margin: Max.: {:d} ({:.3f}%) Min.: {:d} ({:.3f}%)".format(
        nonius_phase_margin_max,
        nonius_phase_margin_max_percent,
        nonius_phase_margin_min,
        nonius_phase_margin_min_percent)
    )

    print("Nonius phase range limit: {:d}".format(analyze_result.nonius_phase_range_limit()))

    print("Nonius upper phase margin: {:f}%", analyze_result.nonius_upper_phase_margin())
    print("Nonius lower phase margin: {:f}%", analyze_result.nonius_lower_phase_margin())


optionalPrintOptimizedNoniusTrackOffsetTable(analyze_result, master_period_code)

optimized_nonius_track_offset_table = analyze_result.optimized_nonius_track_offset_table()
calibration.set_current_nonius_track_offset_table(optimized_nonius_track_offset_table)

mu.set_calibration(calibration)
mu.write_parameters()

mu.write_cmd_register(mu_3sl.Command.CRC_CALC)
mu.write_cmd_register(mu_3sl.Command.ABS_RESET)

print("\n" +
      "---------------------------------------------------------------\n" +
      "--------------- Send WRITE_ALL Command to iC-MU ---------------\n" +
      "---------------------------------------------------------------")

mu.write_cmd_register(mu_3sl.Command.WRITE_ALL)
