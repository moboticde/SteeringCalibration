#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import getopt
import math
import sys

import matplotlib.pyplot as plt
import matplotlib.ticker as plticker
import numpy as np


def show_nonius_curve(phase_error: list[int], track_offset_curve: list[int], phase_margin: list[int],
                      single_turn_position: list[int], continuous_single_turn_position: list[int],
                      master_period_code: int,
                      disable_continuous: bool = False, output_nonius_curve_pdf_path: str | None = None,
                      do_not_show: bool = False):
    nonius_calibration_max_allow_phase_error = pow(2, 14 - 1 - master_period_code)
    nonius_calibration_min_allow_phase_error = -nonius_calibration_max_allow_phase_error

    if master_period_code > 6:
        nonius_calibration_max_allow_phase_error = pow(2, 14 - 1 - int(master_period_code / 2))
        nonius_calibration_min_allow_phase_error = -nonius_calibration_max_allow_phase_error

    single_turns_start_index = []
    lastSingleTurnStartIndex = 0
    single_turns_start_index.append(0)
    for i in range(int(1), int(len(single_turn_position))):
        if (abs(single_turn_position[i] - single_turn_position[i - 1]) > (360 / 2)):
            single_turns_start_index.append(i)
            lastSingleTurnStartIndex = i
    single_turns_start_index.append(len(single_turn_position) - 1)

    nonius_curve_continuous_plot = None

    if disable_continuous:
        nonius_curve_fig, (nonius_curve_plot) = plt.subplots(1, 1)
        nonius_curve_fig.set_size_inches((210 - 25 - 15) / 25.4, 250 / 25.4 / 2)
    else:
        nonius_curve_fig, (nonius_curve_plot, nonius_curve_continuous_plot) = plt.subplots(2, 1)
        nonius_curve_fig.set_size_inches((210 - 25 - 15) / 25.4, 250 / 25.4)
    nonius_curve_fig.canvas.manager.set_window_title("Nonius Curves")

    for i in range(1, int(len(single_turns_start_index))):
        x = single_turn_position[single_turns_start_index[i - 1]:(single_turns_start_index[i] - 1)]
        label_hidden_prefix = ''
        if i > 1:
            label_hidden_prefix = '_'
        nonius_curve_plot.plot(x,
                               phase_error[
                               single_turns_start_index[i - 1]:(single_turns_start_index[i] - 1)],
                               label=label_hidden_prefix + 'Error', color='red', alpha=0.9)
        if len(x) == 1:
            nonius_curve_plot.plot(x,
                                   phase_error[
                                   single_turns_start_index[i - 1]:(single_turns_start_index[i] - 1)],
                                   'o',
                                   label=label_hidden_prefix + 'Error', color='red', alpha=0.9,
                                   markersize=2)

    for i in range(1, int(len(single_turns_start_index))):
        x = single_turn_position[single_turns_start_index[i - 1]:(single_turns_start_index[i] - 1)]
        label_hidden_prefix = ''
        if i > 1:
            label_hidden_prefix = '_'
        nonius_curve_plot.plot(x,
                               phase_margin[
                               single_turns_start_index[i - 1]:(single_turns_start_index[i] - 1)],
                               label=label_hidden_prefix + 'Result',
                               color='lime', alpha=0.6)

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
    nonius_curve_plot.axhline(nonius_calibration_max_allow_phase_error, linewidth=1.0, ls='-', color='cyan')
    nonius_curve_plot.axhline(nonius_calibration_min_allow_phase_error, linewidth=1.0, ls='-', color='cyan')

    nonius_curve_plot.axhline(max(phase_error), linewidth=0.5, ls='-', color='red')
    nonius_curve_plot.axhline(min(phase_error), linewidth=0.5, ls='-', color='red')

    nonius_curve_plot.axhline(max(phase_margin), linewidth=0.5, ls='-', color='lime')
    nonius_curve_plot.axhline(min(phase_margin), linewidth=0.5, ls='-', color='lime')

    if not disable_continuous and nonius_curve_continuous_plot is not None:
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
        nonius_curve_continuous_plot.axhline(nonius_calibration_max_allow_phase_error, linewidth=1.0, ls='-',
                                             color='cyan')
        nonius_curve_continuous_plot.axhline(nonius_calibration_min_allow_phase_error, linewidth=1.0, ls='-',
                                             color='cyan')

    nonius_curve_fig.tight_layout()

    def nonius_curve_fig_on_resize(event):
        nonius_curve_fig.tight_layout()
        nonius_curve_fig.canvas.draw()

    nonius_curve_fig_cid = nonius_curve_fig.canvas.mpl_connect(
        'resize_event', nonius_curve_fig_on_resize)

    if output_nonius_curve_pdf_path is not None:
        nonius_curve_fig.savefig(output_nonius_curve_pdf_path, dpi=600, transparent=True,
                                 metadata={'Creator': 'iC-Haus MU_3SL example',
                                           'Author': 'iC-Haus example', 'Title': 'Nonius Curve'})

    if not do_not_show:
        plt.show()
    else:
        plt.close()


def main() -> int:
    if len(sys.argv) < 3:
        print("Usage:")
        print(
            "{0} <path to nonius curve csv file> <iC-MU master period count parameter code (MPC)>".format(
                sys.argv[0]))
        print("Example:")
        print("{0} nonius_curve.csv 4".format(sys.argv[0]))
        sys.exit(2)

    nonius_curve_file_path = sys.argv[1]
    master_period_code = int(sys.argv[2])

    output_nonius_curve_pdf_path = None
    disable_continuous = False
    do_not_show = False

    args_optlist, args_ = getopt.getopt(sys.argv[3:], '::',
                                        ['output-nonius-curve-pdf=', 'disable_continuous', 'do-not-show'])
    for opt, arg in args_optlist:
        if opt in ("--output-nonius-curve-pdf"):
            output_nonius_curve_pdf_path = arg
        if opt in ("--disable_continuous"):
            disable_continuous = True
        if opt in ("--do-not-show"):
            do_not_show = True

    # nonius curve diagram
    nonius_curve_data = np.genfromtxt(nonius_curve_file_path, delimiter=",",
                                      names=["phase_error", "track_offset_curve", "phase_margin",
                                             "single_turn_position", "continuous_single_turn_position"])
    phase_error = nonius_curve_data['phase_error'][1:].tolist()
    track_offset_curve = nonius_curve_data['track_offset_curve'][1:].tolist()
    phase_margin = nonius_curve_data['phase_margin'][1:].tolist()
    single_turn_position = nonius_curve_data['single_turn_position'][1:].tolist()
    continuous_single_turn_position = nonius_curve_data['continuous_single_turn_position'][1:].tolist()

    show_nonius_curve(phase_error, track_offset_curve, phase_margin,
                      single_turn_position, continuous_single_turn_position, master_period_code,
                      disable_continuous, output_nonius_curve_pdf_path, do_not_show)


if __name__ == '__main__':
    sys.exit(main())
