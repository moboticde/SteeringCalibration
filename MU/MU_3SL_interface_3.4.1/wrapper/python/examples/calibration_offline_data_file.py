#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Copyright 2022 iC-Haus GmbH

Software and its documentation is provided by iC-Haus GmbH or contributors "AS IS" and is
subject to the ZVEI General Conditions for the Supply of Products and Services with iC-Haus
amendments and the ZVEI Software clause with iC-Haus amendments (http://www.ichaus.de/EULA).
"""

import mu_3sl_interface as mu_3sl
from mu_3sl_calibration_adjustments import *
import math
import sys
import os.path

import matplotlib.pyplot as plt
import matplotlib.ticker as plticker
import numpy as np


file_prefix_path = "measure/MU28S_34-32N/calibration_data"
if len(sys.argv) > 1:
    file_prefix_path = sys.argv[1]
noniusCurveCsvFilePath = "nonius_curve.csv"
if len(sys.argv) > 2:
    file_prefix_path = sys.argv[2]

enable_master_period_auto_detection = True
permissible_residual_errors_during_analog_calibration = 1.0

print("Library version: {}".format(mu_3sl.__version__))

revision_code = mu_3sl.Revision.MU_Y2
master_period_code = 4
n_master_periods = 1 << master_period_code

initial_master_adjustments = mu_3sl.AnalogTrackAdjustments()
initial_master_adjustments.cosine_gain = 0
initial_master_adjustments.sine_offset = 0
initial_master_adjustments.cosine_offset = 0
initial_master_adjustments.phase = 0
initial_master_adjustments.phase_range = 0
initial_nonius_adjustments = mu_3sl.AnalogTrackAdjustments()
initial_nonius_adjustments.cosine_gain = 0
initial_nonius_adjustments.sine_offset = 0
initial_nonius_adjustments.cosine_offset = 0
initial_nonius_adjustments.phase = 0
initial_nonius_adjustments.phase_range = 0

calibration = mu_3sl.Calibration(revision_code)

calibrationDataIdx = 0
while True:
    filepath = "{}_{}.csv".format(file_prefix_path, calibrationDataIdx)

    if not os.path.isfile(filepath):
        if calibrationDataIdx == 0:
            print('Error: Calibration data file not found!')
            exit(1)
        break

    file_csv_data = np.genfromtxt(filepath, delimiter=",", names=["master", "nonius"])
    master_raw_data = [int(i) for i in file_csv_data['master'][1:].tolist()]
    nonius_raw_data = [int(i) for i in file_csv_data['nonius'][1:].tolist()]

    # TODO: read from file header comment: fileRevisionCode, fileMasterPeriodCode, initial_master_adjustments, initial_nonius_adjustments

    print("---------------------------------------------------------------\n"
          "---------------- Acquire raw data (from file) -----------------\n"
          "---------------------------------------------------------------")

    print("Read master and nonius track raw data from file:\n\"{}\"\n".format(filepath))

    if calibrationDataIdx == 0:
        # TODO
        # revision_code          = fileRevisionCode
        # master_period_code      = fileMasterPeriodCode
        # n_master_periods = 1u << master_period_code

        calibration = mu_3sl.Calibration(revision_code)
        if not enable_master_period_auto_detection:
            calibration.preconfigure_number_of_master_periods(n_master_periods)
    calibrationDataIdx += 1

    calibration.set_current_analog_track_adjustments(initial_master_adjustments, initial_nonius_adjustments)

    print("Previous iC-MU analog parameters:")
    print_analog_adjustments(calibration)
    print("\n\n")

    print("---------------------------------------------------------------\n"
          "---------------------- Analyze raw data  ----------------------\n"
          "---------------------------------------------------------------")

    analyze_result = calibration.analyze_raw_data(master_raw_data, nonius_raw_data)
    print_analyze_result_log(analyze_result)

    print("Residual errors (relative changes in \"LSB\")")
    print_relative_adjustments(analyze_result)

    print_analog_analyze_result_adjustable_log(calibration, analyze_result)

    relativeMasterTrackAdjustments = analyze_result.relative_master_track_adjustments()
    relativeNoniusTrackAdjustments = analyze_result.relative_nonius_track_adjustments()

    if (abs(relativeMasterTrackAdjustments.cosine_gain_lsb)
            <= permissible_residual_errors_during_analog_calibration
            and abs(relativeNoniusTrackAdjustments.cosine_gain_lsb)
            <= permissible_residual_errors_during_analog_calibration
            and abs(relativeMasterTrackAdjustments.sine_offset_lsb)
            <= permissible_residual_errors_during_analog_calibration
            and abs(relativeNoniusTrackAdjustments.sine_offset_lsb)
            <= permissible_residual_errors_during_analog_calibration
            and abs(relativeMasterTrackAdjustments.cosine_offset_lsb)
            <= permissible_residual_errors_during_analog_calibration
            and abs(relativeNoniusTrackAdjustments.cosine_offset_lsb)
            <= permissible_residual_errors_during_analog_calibration
            and abs(relativeMasterTrackAdjustments.phase_lsb)
            <= permissible_residual_errors_during_analog_calibration
            and abs(relativeNoniusTrackAdjustments.phase_lsb)
            <= permissible_residual_errors_during_analog_calibration):
        print("\n"
              "All residual errors (absolute relative changes in \"LSB\") are smaller than {}.\n"
              "From this point, no further analog calibration step would be required.\n".format(
            permissible_residual_errors_during_analog_calibration))
        break

    print("---------------------------------------------------------------\n"
          "------------ Adjust the analyzed analog parameters ------------\n"
          "---------------------------------------------------------------")

    calibration.adjust_analog_by_analyze_result(analyze_result)

    print("iC-MU analog parameters after adjustment:")
    print_analog_adjustments(calibration)
    print("\n")

print("\n"
      "---------------------------------------------------------------\n"
      "------------ Adjust the analyzed nonius parameters ------------\n"
      "---------------------------------------------------------------\n")

optimized_nonius_track_offset_table = analyze_result.optimized_nonius_track_offset_table()
calibration.set_current_nonius_track_offset_table(optimized_nonius_track_offset_table)

# Generate a new analysis with the optimized nonius track offset table
analyze_result = calibration.analyze_raw_data(master_raw_data, nonius_raw_data)

number_of_calculated_master_periods = analyze_result.number_of_calculated_master_periods()
calculated_master_period_code = round(math.log2(number_of_calculated_master_periods))
optional_print_optimized_nonius_track_offset_table(analyze_result, noniusCurveCsvFilePath)
print("")
optional_print_optimized_nonius_track_offset_parameters(analyze_result)
