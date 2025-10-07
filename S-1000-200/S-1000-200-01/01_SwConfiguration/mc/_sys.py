# -*- coding: utf-8 -*-
#=================================================================================================================================#
#                                                                      Copyright (c) 1997-2020 by miControl. All rights reserved. #
# File     : _sys.py                                                                                                              #
#                                                                                                                                 #
# Project  :                                                                                                                      #
# System   : Python                                                                                                               #
# Version  : 1.00.00.00                                                                                                           #
# Customer :                                                                                                                      #
# Company  : miControl                                                                                                            #
#                                                                                                                                 #
# Author   : miControl Development Team                                                                                           #
# Team     : dariusz Parma (dP)  mailto:dp@miControl.de                                                                           #
# Date     : 31.10.2008                                                                                                           #
#=================================================================================================================================#
# Brief:    SYS functions for simulation (replaces for the mc_sys built-in functions for non mPLC environment)
#
#----------------------------------------------------------------------------------------------------------------------------------
# History:                                                  (Symbol legend: + Added, - Removed, ~ Changed, ! Correction, # Comment)
#
#==================================================================================================================================

def GetCode ():
   return 0x00010001                                        # natives Python

def GetVersion():
   import sys
   return sys.hexversion                                    # version of Python

def SetOnPause (func):
   pass

def SetOnContinue (func):
   pass

def SetOnStop (func):
   pass
