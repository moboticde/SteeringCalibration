# -*- coding: utf-8 -*-
#=================================================================================================================================#
#                                                                      Copyright (c) 1997-2020 by miControl. All rights reserved. #
# File     : _ibs.py                                                                                                              #
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
# Brief:    Interbus functions for simulation (replaces for the mc_ibs built-in functions for non mPLC environment)
#
#----------------------------------------------------------------------------------------------------------------------------------
# History:                                                  (Symbol legend: + Added, - Removed, ~ Changed, ! Correction, # Comment)
#
#==================================================================================================================================

def Init ():
   return 0

def Exit ():
   pass

def StartBus ():
   pass

def StopBus ():
   pass

def RegisterPdo (segment_nr, segment_pos, pdo_type, byte_offset, type):
   return 0

def UnregisterPdo (pdo_handle):
   pass

def PdoRd (pdo_handle):
   pass

def PdoWr (pdo_handle, val):
   pass

def SdoRd (segment_nr, segment_pos, index, subindex, type):
   return 0

def SdoWr (segment_nr, segment_pos, index, subindex, type, dat):
   #print("Ibs.SdoWr(%d, %04Xh,%02X, %d)" % (segment_nr, segment_pos, index, subindex, type, dat))
   return 0
