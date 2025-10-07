#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Copyright 2022 iC-Haus GmbH

Software and its documentation is provided by iC-Haus GmbH or contributors "AS IS" and is
subject to the ZVEI General Conditions for the Supply of Products and Services with iC-Haus
amendments and the ZVEI Software clause with iC-Haus amendments (http://www.ichaus.de/EULA).
"""

import mu_3sl_interface as mu_3sl


print("Library version: {}".format(mu_3sl.__version__))

# Construct a new instance of a virtual chip object and obtain a handle for it.
mu = mu_3sl.MuHandle()

mu.use_revision(mu_3sl.Revision.MU_Y2)


try:
    mu.set_register(0x00, 0x00)
except Exception as e: print(e)
try:
    mu.set_register(0x01, 0x00)
except Exception as e: print(e)
try:
    mu.set_register(0x02, 0x00)
except Exception as e: print(e)
try:
    mu.set_register(0x03, 0x00)
except Exception as e: print(e)
try:
    mu.set_register(0x04, 0x00)
except Exception as e: print(e)
try:
    mu.set_register(0x05, 0x88)
except Exception as e: print(e)

# ...

mu.save_params("write_config_file_output.cfg")
