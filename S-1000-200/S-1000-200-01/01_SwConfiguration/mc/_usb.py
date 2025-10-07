# -*- coding: utf-8 -*-
#=================================================================================================================================#
#                                                                      Copyright (c) 1997-2020 by miControl. All rights reserved. #
# File     : _usb.py                                                                                                              #
#                                                                                                                                 #
# Project  :                                                                                                                      #
# System   : Python                                                                                                               #
# Version  : 1.00.00.00                                                                                                           #
# Customer :                                                                                                                      #
# Company  : miControl                                                                                                            #
#                                                                                                                                 #
# Author   : miControl Development Team                                                                                           #
# Team     : dariusz Parma (dP)  mailto:dp@miControl.de                                                                           #
# Date     : 12.02.2006                                                                                                           #
#=================================================================================================================================#
# Brief:    USB functions for simulation (replaces for the mc_usb built-in functions for non mPLC environment)
#
#----------------------------------------------------------------------------------------------------------------------------------
# History:                                                  (Symbol legend: + Added, - Removed, ~ Changed, ! Correction, # Comment)
#
#==================================================================================================================================

def SdoWr (interf_nr, index, subindex, val, timeout=0xFFFF):
   print("Usb.SdoWr(%d, 0x%04X,%d, %d)" % (interf_nr, index, subindex, val))

def SdoRd (interf_nr, index, subindex, timeout=0xFFFF):
   print("Usb.SdoRd(%d, 0x%04X,%d)" % (interf_nr, index, subindex))
   return 0

def PdoWr (cob_id, dat):                        # Needed for miCAN-Stick2 Bootloader
   txt = "Usb.PdoWr(0x%04X, [" % (cob_id)

   for i in range(0,len(dat)):
      txt += "0x%02X," % (dat[i])

   txt += "])"

   print(txt)
