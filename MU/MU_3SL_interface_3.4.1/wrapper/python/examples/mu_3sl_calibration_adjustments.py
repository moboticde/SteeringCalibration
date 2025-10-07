#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Copyright 2022 iC-Haus GmbH

Software and its documentation is provided by iC-Haus GmbH or contributors "AS IS" and is
subject to the ZVEI General Conditions for the Supply of Products and Services with iC-Haus
amendments and the ZVEI Software clause with iC-Haus amendments (http://www.ichaus.de/EULA).
"""

import mu_3sl_interface as mu_3sl
import mu_3sl_interface.calibration as mu_3sl_calibration

import math
import matplotlib.pyplot as plt
import matplotlib.ticker as plticker
import numpy as np


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


def print_analyze_result_log(analyze_result: mu_3sl.AnalyzeResult):
    print(analyze_result.log(mu_3sl.AdjustmentMessageLogLevel.ALL))


def print_analog_analyze_result_adjustable_log(
        calibration: mu_3sl.Calibration,
        analyze_result: mu_3sl.AnalyzeResult):
    adjustable, adjustment_message = calibration.is_analog_analyze_result_adjustable(analyze_result,
                                                                                     mu_3sl.AdjustmentMessageLogLevel.ALL)
    if adjustable:
        print("Analyze result is adjustable.\nMessage:\n{}\n".format(adjustment_message))
    else:
        print("Analyze result is not adjustable!\nMessage:\n{}\n".format(adjustment_message))


def optional_print_optimized_nonius_track_offset_table(analyze_result: mu_3sl.AnalyzeResult,
                                                       noniusCurveCsvFilePath: str):
    nonius_track_offset_table = analyze_result.optimized_nonius_track_offset_table()
    print("Optimized nonius track offset table:")
    print("SPO_BASE: {:2d}".format(nonius_track_offset_table.spo_base))
    for i in range(16):
        if i >= 10:
            print("SPO_{:d}:   {:2d}".format(i, nonius_track_offset_table[i]))
        else:
            print("SPO_{:d}:    {:2d}".format(i, nonius_track_offset_table[i]))
    print("")

    nonius_phase_range_limit = analyze_result.nonius_phase_range_limit()
    nonius_phase_margin_max = analyze_result.nonius_phase_margin_max()
    nonius_phase_margin_min = analyze_result.nonius_phase_margin_min()
    nonius_phase_margin_max_percent = (
            nonius_phase_margin_max / nonius_phase_range_limit * 100)
    nonius_phase_margin_min_percent = (
            nonius_phase_margin_min / -nonius_phase_range_limit * 100)
    print("Nonius phase margin: Max.: {:d} ({:.3f}%) Min.: {:d} ({:.3f}%)".format(
        nonius_phase_margin_max,
        nonius_phase_margin_max_percent,
        nonius_phase_margin_min,
        nonius_phase_margin_min_percent)
    )

    print("Nonius phase range limit: {:d}".format(analyze_result.nonius_phase_range_limit()))

    print("Nonius upper phase margin: {:f}%".format(analyze_result.nonius_upper_phase_margin()))
    print("Nonius lower phase margin: {:f}%".format(analyze_result.nonius_lower_phase_margin()))

    # Copy nonius analyzed curve data to have it after delete analyzeResult
    # TODO

    phase_error = analyze_result.nonius_phase_errors()
    track_offset_curve = analyze_result.nonius_track_offset_curve()
    phase_margin = analyze_result.nonius_phase_margin()
    single_turn_position = analyze_result.nonius_position(mu_3sl_calibration.Unit.DEGREE, False)
    continuous_single_turn_position = analyze_result.nonius_position(mu_3sl_calibration.Unit.DEGREE, True)

    single_turns_start_index = []
    lastSingleTurnStartIndex = 0
    single_turns_start_index.append(0)
    for i in range(int(1), int(len(single_turn_position))):
        if (abs(single_turn_position[i] - single_turn_position[i - 1]) > (360 / 2)):
            single_turns_start_index.append(i)
            lastSingleTurnStartIndex = i
    single_turns_start_index.append(len(single_turn_position) - 1)

    nonius_curve_fig, (nonius_curve_plot, nonius_curve_continuous_plot) = plt.subplots(2, 1)
    nonius_curve_fig.canvas.manager.set_window_title("Nonius Curves")
    nonius_curve_fig.set_size_inches((210 - 25 - 15) / 25.4, 250 / 25.4)

    for i in range(1, int(len(single_turns_start_index))):
        x = single_turn_position[single_turns_start_index[i - 1]:(single_turns_start_index[i] - 1)]
        label_hidden_prefix = ''
        if i > 1:
            label_hidden_prefix = '_'
        nonius_curve_plot.plot(x,
                               phase_error[
                               single_turns_start_index[i - 1]:(single_turns_start_index[i] - 1)],
                               label=label_hidden_prefix + 'Error', color='red', alpha=0.9)

    for i in range(1, int(len(single_turns_start_index))):
        x = single_turn_position[single_turns_start_index[i - 1]:(single_turns_start_index[i] - 1)]
        label_hidden_prefix = ''
        if i > 1:
            label_hidden_prefix = '_'
        nonius_curve_plot.plot(x,
                               phase_margin[
                               single_turns_start_index[i - 1]:(single_turns_start_index[i] - 1)],
                               label=label_hidden_prefix + 'Result',
                               color='lime', alpha=0.9)

    for i in range(1, int(len(single_turns_start_index))):
        x = single_turn_position[single_turns_start_index[i - 1]:(single_turns_start_index[i] - 1)]
        label_hidden_prefix = ''
        if i > 1:
            label_hidden_prefix = '_'
        nonius_curve_plot.plot(x,
                               track_offset_curve[
                               single_turns_start_index[i - 1]:(single_turns_start_index[i] - 1)],
                               label=label_hidden_prefix + 'SPO', color='midnightblue', alpha=0.9)

    optimize_number_of_ticks = len(nonius_curve_plot.get_xticks())
    plot_range = (max(single_turn_position) - min(single_turn_position))
    optimal_ticker_base = math.pow(2, round(math.log2(plot_range / optimize_number_of_ticks / 90))) * 90
    degree_loc = plticker.MultipleLocator(base=optimal_ticker_base)
    nonius_curve_plot.xaxis.set_major_locator(degree_loc)

    nonius_curve_plot.set_title("Nonius Curve")
    nonius_curve_plot.legend()
    nonius_curve_plot.set_xlabel("Reference Angle (degrees)")
    nonius_curve_plot.set_ylabel("Track Error (LSB)")
    nonius_curve_plot.axhline(nonius_phase_range_limit, linewidth=1.0, ls='-', color='cyan')
    nonius_curve_plot.axhline(-nonius_phase_range_limit, linewidth=1.0, ls='-', color='cyan')

    nonius_curve_plot.axhline(max(phase_error), linewidth=0.5, ls='-', color='red')
    nonius_curve_plot.axhline(min(phase_error), linewidth=0.5, ls='-', color='red')

    nonius_curve_plot.axhline(max(phase_margin), linewidth=0.5, ls='-', color='lime')
    nonius_curve_plot.axhline(min(phase_margin), linewidth=0.5, ls='-', color='lime')

    nonius_curve_continuous_plot.plot(continuous_single_turn_position, phase_error, label='Error',
                                      color='red', alpha=0.9)
    nonius_curve_continuous_plot.plot(continuous_single_turn_position, phase_margin, label='Result',
                                      color='lime', alpha=0.9)
    nonius_curve_continuous_plot.plot(continuous_single_turn_position, track_offset_curve, label='SPO',
                                      color='midnightblue', alpha=0.9)
    nonius_curve_continuous_plot.set_title("Continuous Nonius Curve")
    nonius_curve_continuous_plot.legend()
    nonius_curve_continuous_plot.set_xlabel("Reference Angle (degrees)")
    nonius_curve_continuous_plot.set_ylabel("Track Error (LSB)")
    nonius_curve_continuous_plot.axhline(nonius_phase_margin_max, linewidth=1.0, ls='-',
                                         color='cyan')
    nonius_curve_continuous_plot.axhline(nonius_phase_margin_min, linewidth=1.0, ls='-',
                                         color='cyan')

    nonius_curve_fig.tight_layout()

    def nonius_curve_fig_on_resize(event):
        nonius_curve_fig.tight_layout()
        nonius_curve_fig.canvas.draw()

    nonius_curve_fig_cid = nonius_curve_fig.canvas.mpl_connect(
        'resize_event', nonius_curve_fig_on_resize)

    plt.show()


def optional_print_optimized_nonius_track_offset_parameters(analyze_result: mu_3sl.AnalyzeResult):
    nonius_track_offset_table = analyze_result.optimized_nonius_track_offset_table()
    nonius_track_offset_table_parameters = mu_3sl.nonius_track_offset_table_parameters(nonius_track_offset_table)
    print("Optimized nonius track offset parameter values:")
    print("SPO_BASE: {:4d} (0x{:02X})".format(
        nonius_track_offset_table_parameters.spo_base,
        nonius_track_offset_table_parameters.spo_base))
    for i in range(15):
        if i >= 10:
            print("SPO_{}:   {:4d} (0x{:02X})".format(
                i,
                nonius_track_offset_table_parameters.spo_n[i],
                nonius_track_offset_table_parameters.spo_n[i]))
        else:
            print("SPO_{}:    {:4d} (0x{:02X})".format(
                i,
                nonius_track_offset_table_parameters.spo_n[i],
                nonius_track_offset_table_parameters.spo_n[i]))
    print("")
