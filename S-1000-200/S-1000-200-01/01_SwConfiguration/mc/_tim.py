# -*- coding: utf-8 -*-
#=================================================================================================================================#
#                                                                      Copyright (c) 1997-2020 by miControl. All rights reserved. #
# File     : _tim.py                                                                                                              #
#                                                                                                                                 #
# Project  :                                                                                                                      #
# System   : Python                                                                                                               #
# Version  : 1.00.00.00                                                                                                           #
# Customer :                                                                                                                      #
# Company  : miControl                                                                                                            #
#                                                                                                                                 #
# Author   : miControl Development Team                                                                                           #
# Team     : dariusz Parma (dP)  mailto:dp@miControl.de                                                                           #
# Date     : 15.03.2003                                                                                                           #
#=================================================================================================================================#
# Brief:    TIM functions for simulation (replaces for the mc_tim built-in functions for non mPLC environment)
#
#----------------------------------------------------------------------------------------------------------------------------------
# History:                                                  (Symbol legend: + Added, - Removed, ~ Changed, ! Correction, # Comment)
#
#==================================================================================================================================
if __package__:
   from . import pyx
else:
   import pyx

def Delay (time_ms):
   pyx.sleep(time_ms / 1000.0)

def Sleep (time_ms):
   pyx.sleep(time_ms / 1000.0)

def Clock():
   return (pyx.clock() * 1000.0)
