# -*- coding: utf-8 -*-
#=================================================================================================================================#
#                                                                      Copyright (c) 1997-2020 by miControl. All rights reserved. #
# File     : iom.py                                                                                                               #
#                                                                                                                                 #
# Project  :                                                                                                                      #
# System   : Python                                                                                                               #
# Version  : (see ClassVersion)                                                                                                   #
# Customer :                                                                                                                      #
# Company  : miControl                                                                                                            #
#                                                                                                                                 #
# Author   : miControl Development Team                                                                                           #
# Team     : dariusz Parma (dP)  mailto:dp@miControl.de                                                                           #
# Date     : 16.01.2004                                                                                                           #
#=================================================================================================================================#
# Brief:    Iom class for miControl I/O-Devices
#
#----------------------------------------------------------------------------------------------------------------------------------
# History:                                                  (Symbol legend: + Added, - Removed, ~ Changed, ! Correction, # Comment)
#  04.05.2017 dP: ~Modulename wurde von io auf iom geändert.
#                 (wegen Namenkonfikt mit python io-Modul)
#
#==================================================================================================================================
if __package__:
   from .ds401 import Ds401
else:
   from ds401  import Ds401

__all__ = ["Iom"]

#=================================================================================================================================#
class Iom (Ds401):

   # Var's ------------------------------------------------------------------------------------------------------------------------
   #
   ClassVersion = (1,0x02, 0x00,0x00)

   # Constructor ------------------------------------------------------------------------------------------------------------------
   #
   def __init__(self, node_id=1, interface=1, pdo_mode=0):
      Ds401.__init__(self, node_id, interface)

      self.EnablePdoMode(pdo_mode)

# TEST ----------------------------------------------------------------------------------------------------------------------------
#
def test():
   import time

   print("\n=== Test start...")

   m = Iom(1,1)

   m.EnablePdoMode(0)         # SDO Transmission

   print("Din = %d" % (m.Din(0)))

   m.Dout(0,0x55)
   time.sleep(1)
   m.Dout(0,0xAA)
   time.sleep(1)
   m.Dout(0,0x80)

   for i in range(0,8):
      m.DoutBit(i,1)
      time.sleep(0.1)
      m.DoutBit(i,0)
      time.sleep(0.1)

   m.EnablePdoMode(1)         # PDO Transmission

   print("Din = %d" % (m.Din(0)))

   m.Dout(0,0x55)
   time.sleep(1)
   m.Dout(0,0xAA)
   time.sleep(1)
   m.Dout(0,0x80)

   for i in range(0,8):
      m.DoutBit(i,1)
      time.sleep(0.1)
      m.DoutBit(i,0)
      time.sleep(0.1)

   print("\n=== Test end.")

#==================================================================================================================================
if __name__ == '__main__':
   test()
