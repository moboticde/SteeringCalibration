# -*- coding: utf-8 -*-
#=================================================================================================================================#
#                                                                      Copyright (c) 1997-2020 by miControl. All rights reserved. #
# File     : _com.py                                                                                                              #
#                                                                                                                                 #
# Project  :                                                                                                                      #
# System   : Python                                                                                                               #
# Version  : 1.00.01.00                                                                                                           #
# Customer :                                                                                                                      #
# Company  : miControl                                                                                                            #
#                                                                                                                                 #
# Author   : miControl Development Team                                                                                           #
# Team     : dariusz Parma (dP)  mailto:dp@miControl.de                                                                           #
# Date     : 15.03.2003                                                                                                           #
#=================================================================================================================================#
# Brief:    COM functions for simulation (replaces for the mc_com built-in functions for non mPLC environment)
#
#----------------------------------------------------------------------------------------------------------------------------------
# History:                                                  (Symbol legend: + Added, - Removed, ~ Changed, ! Correction, # Comment)
#  14.09.2003 dP: +Subindex-Unterstützung
#
#==================================================================================================================================

def Sp (comnr, index, p1, p2=None):
   if p2 == None:
      print("Com.Sp(%d, 0x%04X, %d)" % (comnr, index, p1))         #p1=val
   else:
      print("Com.Sp(%d, 0x%04X.%d, %d)" % (comnr, index, p1, p2))  #p1=subindex, p2=val

def Gp (comnr, index, subindex=0):
   print("Com.Gp(%d, 0x%04X.%d)" % (comnr, index, subindex))
   return 0
