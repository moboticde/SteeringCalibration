# -*- coding: utf-8 -*-
#=================================================================================================================================#
#                                                                      Copyright (c) 1997-2020 by miControl. All rights reserved. #
# File     : cop_cobid.py                                                                                                         #
#                                                                                                                                 #
# Project  :                                                                                                                      #
# System   : Python                                                                                                               #
# Version  : 1.00.00.00                                                                                                           #
# Customer :                                                                                                                      #
# Company  : miControl                                                                                                            #
#                                                                                                                                 #
# Author   : miControl Development Team                                                                                           #
# Team     : dariusz Parma (dP)  mailto:dp@miControl.de                                                                           #
# Date     : 16.01.2004                                                                                                           #
#=================================================================================================================================#
# Brief:    CobId's constants for CANopen miControl Devices
#
#----------------------------------------------------------------------------------------------------------------------------------
# History:                                                  (Symbol legend: + Added, - Removed, ~ Changed, ! Correction, # Comment)
#
#==================================================================================================================================

# Standard CobId's (vom Sicht des Slaves) -----------------------------------------------------------------------------------------

COBID_NMT0     =  0x0000
COBID_SYNC     =  0x0080
COBID_TSTAMP   =  0x0100         # Time Stamp

COBID_EMCY     =  0x0080         # [0x0081..0x00FF] [ 129.. 255]

COBID_TxPdo1   =  0x0180         # [0x0181..0x01FF] [ 385.. 511]
COBID_RxPdo1   =  0x0200         # [0x0201..0x027F] [ 513.. 639]

COBID_TxPdo2   =  0x0280         # [0x0281..0x02FF] [ 641.. 767]
COBID_RxPdo2   =  0x0300         # [0x0301..0x037F] [ 769.. 895]

COBID_TxPdo3   =  0x0380         # [0x0381..0x03FF]
COBID_RxPdo3   =  0x0400         # [0x0401..0x047F]

COBID_TxPdo4   =  0x0480         # [0x0481..0x04FF]
COBID_RxPdo4   =  0x0500         # [0x0501..0x057F]

COBID_TxSDO    =  0x0580         # [0x0581..0x05FF] [1409..1535]
COBID_RxSDO    =  0x0600         # [0x0601..0x067F] [1537..1663]
COBID_GUARD    =  0x0700         # [0x0701..0x077F] [1793..1919]

COBID_DIN      =  COBID_TxPdo1   # Slave:TX Master:RX
COBID_DOUT     =  COBID_RxPdo1   # Slave:RX Master:TX
COBID_AIN      =  COBID_TxPdo2   # Slave:TX Master:RX
COBID_AOUT     =  COBID_RxPdo2   # Slave:RX Master:TX

COBID_TX_LMT   =  2020
COBID_RX_LMT   =  2021

COBID_TX_NMTI  =  2022

COBID_TX_DBT   =  2023
COBID_RX_DBT   =  2024

COBID_TX_NMT   =  2025
COBID_RX_NMT   =  2026

def GetCobId (node_id, base_cob_id):
   return (base_cob_id + node_id)
