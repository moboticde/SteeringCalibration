# -*- coding: utf-8 -*-
#=================================================================================================================================#
#                                                                      Copyright (c) 1997-2020 by miControl. All rights reserved. #
# File     : _can.py                                                                                                              #
#                                                                                                                                 #
# Project  :                                                                                                                      #
# System   : Python                                                                                                               #
# Version  : 1.01.00.00                                                                                                           #
# Customer :                                                                                                                      #
# Company  : miControl                                                                                                            #
#                                                                                                                                 #
# Author   : miControl Development Team                                                                                           #
# Team     : dariusz Parma (dP)  mailto:dp@miControl.de                                                                           #
# Date     : 15.03.2003                                                                                                           #
#=================================================================================================================================#
# Brief:    CAN functions for simulation (replaces for the mc_can built-in functions for non mPLC environment)
#
#----------------------------------------------------------------------------------------------------------------------------------
# History:                                                  (Symbol legend: + Added, - Removed, ~ Changed, ! Correction, # Comment)
#  12.05.2004 dP: !PdoWr, !PdoRd - bad parameters
#  11.09.2004 dP: +tx_cob_id=0xFFFFFFFF, +rx_cob_id=0xFFFFFFFF
#                 for mPLC 2.47.00.00
#  01.07.2013 dP: +SdoXx_xxx, XxxxMsgBuf - Funktionen
#
#==================================================================================================================================

def Open ():
   print("Can.Open()")

def Reopen ():
   print("Can.Reopen()")

def IsOpened ():
   return True

def Close ():
   print("Can.Close()")

def SetBaudrate (baudrate):
   print("Can.SetBaudrate(%d)" % baudrate)

def PdoWr (cob_id, dat):
   txt = "Can.PdoWr(0x%04X, [" % (cob_id)

   for i in range(0,len(dat)):
      txt += "0x%02X," % (dat[i])

   txt += "])"

   print(txt)

def PdoRd (cob_id):
   print("Can.PdoRd(0x%04X)" % (cob_id))
   return [0,0,0,0,0,0,0,0]


def SdoWr (nodeid, index, subindex, val, timeout=0xFFFF, tx_cob_id=0xFFFFFFFF, rx_cob_id=0xFFFFFFFF):
   print("Can.SdoWr(%d, 0x%04X,%d, %d)" % (nodeid, index, subindex, val))

def SdoWr_ui8 (nodeid, index, subindex, val, timeout=0xFFFF, tx_cob_id=0xFFFFFFFF, rx_cob_id=0xFFFFFFFF):
   print("Can.SdoWr_ui8(%d, 0x%04X,%d, %d)" % (nodeid, index, subindex, val))

def SdoWr_ui16 (nodeid, index, subindex, val, timeout=0xFFFF, tx_cob_id=0xFFFFFFFF, rx_cob_id=0xFFFFFFFF):
   print("Can.SdoWr_ui16(%d, 0x%04X,%d, %d)" % (nodeid, index, subindex, val))

def SdoWr_ui32 (nodeid, index, subindex, val, timeout=0xFFFF, tx_cob_id=0xFFFFFFFF, rx_cob_id=0xFFFFFFFF):
   print("Can.SdoWr_ui32(%d, 0x%04X,%d, %d)" % (nodeid, index, subindex, val))

def SdoWr_i8 (nodeid, index, subindex, val, timeout=0xFFFF, tx_cob_id=0xFFFFFFFF, rx_cob_id=0xFFFFFFFF):
   print("Can.SdoWr_i8(%d, 0x%04X,%d, %d)" % (nodeid, index, subindex, val))

def SdoWr_i16 (nodeid, index, subindex, val, timeout=0xFFFF, tx_cob_id=0xFFFFFFFF, rx_cob_id=0xFFFFFFFF):
   print("Can.SdoWr_i16(%d, 0x%04X,%d, %d)" % (nodeid, index, subindex, val))

def SdoWr_i32 (nodeid, index, subindex, val, timeout=0xFFFF, tx_cob_id=0xFFFFFFFF, rx_cob_id=0xFFFFFFFF):
   print("Can.SdoWr_i32(%d, 0x%04X,%d, %d)" % (nodeid, index, subindex, val))


def SdoRd (nodeid, index, subindex, timeout=0xFFFF, tx_cob_id=0xFFFFFFFF, rx_cob_id=0xFFFFFFFF):
   print("Can.SdoRd(%d, 0x%04X,%d)" % (nodeid, index, subindex))
   return 0

def SdoRd_ui8 (nodeid, index, subindex, timeout=0xFFFF, tx_cob_id=0xFFFFFFFF, rx_cob_id=0xFFFFFFFF):
   print("Can.SdoRd_ui8(%d, 0x%04X,%d)" % (nodeid, index, subindex))
   return 0

def SdoRd_ui16 (nodeid, index, subindex, timeout=0xFFFF, tx_cob_id=0xFFFFFFFF, rx_cob_id=0xFFFFFFFF):
   print("Can.SdoRd_ui16(%d, 0x%04X,%d)" % (nodeid, index, subindex))
   return 0

def SdoRd_ui32 (nodeid, index, subindex, timeout=0xFFFF, tx_cob_id=0xFFFFFFFF, rx_cob_id=0xFFFFFFFF):
   print("Can.SdoRd_ui32(%d, 0x%04X,%d)" % (nodeid, index, subindex))
   return 0

def SdoRd_i8 (nodeid, index, subindex, timeout=0xFFFF, tx_cob_id=0xFFFFFFFF, rx_cob_id=0xFFFFFFFF):
   print("Can.SdoRd_i8(%d, 0x%04X,%d)" % (nodeid, index, subindex))
   return 0

def SdoRd_i16 (nodeid, index, subindex, timeout=0xFFFF, tx_cob_id=0xFFFFFFFF, rx_cob_id=0xFFFFFFFF):
   print("Can.SdoRd_i16(%d, 0x%04X,%d)" % (nodeid, index, subindex))
   return 0

def SdoRd_i32 (nodeid, index, subindex, timeout=0xFFFF, tx_cob_id=0xFFFFFFFF, rx_cob_id=0xFFFFFFFF):
   print("Can.SdoRd_i32(%d, 0x%04X,%d)" % (nodeid, index, subindex))
   return 0


def EnableMsgBuf ():
   print("Can.EnableMsgBuf()")

def DisableMsgBuf ():
   print("Can.DisableMsgBuf()")

def SetMsgBufSize (size):
   print("Can.SetMsgBufSize(%d)" % (size))

def PutMsg (cob_id, dat):
   txt = "Can.PutMsg(0x%04X, [" % (cob_id)

   for i in range(0,len(dat)):
      txt += "0x%02X," % (dat[i])

   txt += "])"

   print(txt)

def GetMsg ():
   print("Can.GetMsg()")
   return [0, 0, [0,0,0,0,0,0,0,0] , 0]   # [net, cob_id, [dat], time_stamp_10us]

def IsMsg ():
   print("Can.IsMsg()")
   return False

def GetMsgCount ():
   print("Can.GetMsgCount()")
   return 0
