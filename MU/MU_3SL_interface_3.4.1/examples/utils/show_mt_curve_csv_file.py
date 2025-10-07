#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import numpy as np
import matplotlib.pyplot as plt
import sys
import getopt


if len(sys.argv) < 3:
    print("Usage:")
    print("{0} <path to mt curve csv file> <number of multi turn synchronization bits>".format(sys.argv[0]))
    print("Example:")
    print("{0} mt_sync_curve.csv 4".format(sys.argv[0]))
    sys.exit(2)

nonius_curve_file_path = sys.argv[1]
number_of_multi_turn_synchronization_bits = int(sys.argv[2])

output_virtual_error_curve_image_path = None
output_nonius_curve_pdf_path = None

args_optlist, args_ = getopt.getopt(sys.argv[3:], '::', ['output-nonius-curve-pdf='])
for opt, arg in args_optlist:
    if opt in ("--output-nonius-curve-pdf"):
        output_nonius_curve_pdf_path = arg


multi_turn_synchronization_tolerance = (360 - (360 / (1 << max(2, number_of_multi_turn_synchronization_bits)) * 2)) / 2



# nonius curve diagram
nonius_curve_data = np.genfromtxt(nonius_curve_file_path, delimiter=",", names=["position", "error"])
position = nonius_curve_data['position'][1:].tolist()
offset_error = nonius_curve_data['error'][1:].tolist()

nonius_curve_fig, (nonius_curve_plot) = plt.subplots(1, 1)
nonius_curve_fig.canvas.manager.set_window_title("Multi Turn Synchronization Error")
nonius_curve_fig.set_size_inches((210 - 25 - 15)/25.4, 250/25.4)

nonius_curve_plot.plot(position, offset_error)
nonius_curve_plot.set_title("Multi turn synchronization error")
nonius_curve_plot.set_xlabel("System single turn position in degree")
nonius_curve_plot.set_ylabel("Offset error in degree")
nonius_curve_plot.axhline(multi_turn_synchronization_tolerance, linewidth=1.0, ls='-', color='m')
nonius_curve_plot.axhline(-multi_turn_synchronization_tolerance, linewidth=1.0, ls='-', color='m')

nonius_curve_fig.tight_layout()
def nonius_curve_fig_on_resize(event):
    nonius_curve_fig.tight_layout()
    nonius_curve_fig.canvas.draw()
nonius_curve_fig_cid = nonius_curve_fig.canvas.mpl_connect(
    'resize_event', nonius_curve_fig_on_resize)

if output_nonius_curve_pdf_path is not None:
    nonius_curve_fig.savefig(output_nonius_curve_pdf_path, dpi=600, transparent=True, metadata={'Creator': 'iC-Haus MU_3SL example', 'Author': 'iC-Haus example', 'Title': 'Multi Turn Synchronization Error'})


plt.show()
