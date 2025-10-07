# -*- coding: utf-8 -*-
#=================================================================================================================================#
#                                                                      Copyright (c) 1997-2020 by miControl. All rights reserved. #
# File     : dsa.py                                                                                                               #
#                                                                                                                                 #
# Project  :                                                                                                                      #
# System   : Python                                                                                                               #
# Version  : (see self.ClassVersion)                                                                                              #
# Customer :                                                                                                                      #
# Company  : miControl                                                                                                            #
#                                                                                                                                 #
# Author   : miControl Development Team                                                                                           #
# Team     : dariusz Parma (dP)  mailto:dp@miControl.de                                                                           #
# Date     : 18.02.2003                                                                                                           #
#=================================================================================================================================#
# Brief:    Dsa class for miControl DSA-Devices
#
#----------------------------------------------------------------------------------------------------------------------------------
# History:                                                  (Symbol legend: + Added, - Removed, ~ Changed, ! Correction, # Comment)
#  11.09.2003 dP: +Factorgroup
#  12.09.2003 dP: +Timeout for StoreParam, RestoreParam,
#                  DefaultParam and ClearParam
#  19.02.2004 dP: !MesVelTime, !MesVel_cnt
#                 ~Timeouts @ StoreParam,ClearParam = 2sec
#  01.03.2004 dP: +VelKx_xxxxx for moving phases
#  20.03.2004 dP: +Home - functions
#  12.05.2004 dP: !HomeMethod, !HomeOffset, !HomeAcc, !HomeMaxIndexPath
#                 (no Subindex on call of self.Par)
#  17.05.2004 dP: +PosWindow, +PosWindowTime, +PosWindowDisable
#  19.06.2004 dP: +PrintInfos
#  08.08.2004 dP: +timeout for Sp,Gp,Par,Sdo,SdoWr,SdoRd
#  09.08.2004 dP: +MesVel for Firmware >= 1.69.00.61
#  09.08.2004 dP: ~timeouts for StoreParam, ClearParam
#  12.08.2004 dP: +DevMinUpError
#  06.10.2004 dP: +DinBit2ParValue, DoutBit2ParValue
#                 ~DevDinXxxxx, DevDoutXxxxx
#                 +DevContinueMode
#                 +CurrDynLimitXxxx (for Firmware >= 1.64.00.71)
#  16.01.2005 dP: new Parameters for V1.71.xx.xx.
#  02.02.2007 dP: !Din(nr) Version(1,0x40, 0x01,0x00)
#  04.01.2009 dP: +VelKaff
#  29.01.2010 dP: +Completion of parameters V1.85.03.91
#  02.12.2013 dP: +ReleaseSw
#  23.03.2017 dP: !Event_CmdOnSpecError  V1.42.01.00
#
#==================================================================================================================================
if __package__:
   from .pyx      import *
   from .common   import Msg
   from .ds301    import Ds301
   from .ds402    import ds402                     # Important: no import Ds402 !
else:
   from pyx       import *
   from common    import Msg
   from ds301     import Ds301
   from ds402     import ds402                     # Important: no import Ds402 !

__all__ = ["Dsa","dsa"]

#==================================================================================================================================
class Dsa (Ds301):

   # Var's ------------------------------------------------------------------------------------------------------------------------
   #
   ClassVersion = (1,0x42, 0x01,0x00)
   Ds402        = None

   # Constructor/Destructor -------------------------------------------------------------------------------------------------------
   #
   def __init__(self, node_id=1, interface=1):
      Ds301.__init__(self, node_id, interface)
      self.Ds402 = ds402(node_id, interface)

   # Common Functions -------------------------------------------------------------------------------------------------------------
   #
   def VersionToString16(self, ver):
      return "%X.%02X" % ((ver>>8)&0xFF,ver&0xFF)

   def VersionToString32 (self, ver, rel=0):
      if rel:
         txt = "%X.%02X.%02X.%02X_%04X" % ((ver>>24)&0xFF,(ver>>16)&0xFF,(ver>>8)&0xFF,ver&0xFF, rel)
      else:
         txt ="%X.%02X.%02X.%02X" % ((ver>>24)&0xFF,(ver>>16)&0xFF,(ver>>8)&0xFF,ver&0xFF)

      return txt

   def _IoBit2ParValue(self, io_nr, active_level, io_nr_start):   # io_nr is 0-based
      if io_nr is None:
         return None

      nr = abs(io_nr)

      if nr in range(0,8):
         nr = io_nr_start + nr
      else:
         nr = io_nr

      if active_level is None:
         return nr
      elif active_level == 0:
         return 0
      elif active_level < 0:     # LowActive
         return -abs(nr)
      else:                      # HighActive
         return  abs(nr)

   def DinBit2ParValue(self, io_nr, active_level=None):     # io_nr is 0-based; active_level=0 Off; active_level>0 HighActive; active_level<0 LowActive
      return self._IoBit2ParValue(io_nr, active_level, self.DIN_BIT0)

   def DoutBit2ParValue(self, io_nr, active_level=None):    # io_nr is 0-based; active_level=0 Off; active_level>0 HighActive; active_level<0 LowActive
      return self._IoBit2ParValue(io_nr, active_level, self.DOUT_BIT0)

   # Device -----------------------------------------------------------------------------------------------------------------------
   #
   def Cmd                    (self, cmd=None)     :  self.Par(0x0000,0x00, cmd)
   def CmdExecOnChange        (self, cmd=None)     :  self.Par(0x0000,0x01, cmd)
   def CmdData0               (self, value=None)   :  self.Par(0x0000,0x10, value)
   def CmdData1               (self, value=None)   :  self.Par(0x0000,0x11, value)
   def ClrError               (self)               :  self.Sp(0x0000, 0x01)
   def ClearError             (self)               :  self.Sp(0x0000, 0x01)
   def QuickStop              (self)               :  self.Sp(0x0000, 0x02)
   def Halt                   (self)               :  self.Sp(0x0000, 0x03)
   def Continue               (self)               :  self.Sp(0x0000, 0x04)
   def Update                 (self)               :  self.Sp(0x0000, 0x05)
   def StoreParam             (self)               :  self.Sp(0x0000, 0x80, timeout=5000)
   def RestoreParam           (self)               :  self.Sp(0x0000, 0x81, timeout=500 )
   def DefaultParam           (self)               :  self.Sp(0x0000, 0x82, timeout=500 )
   def ClearParam             (self)               :  self.Sp(0x0000, 0x83, timeout=5000)

   def SetError               (self, value)        :  self.Sp(0x0000,8, value)
   def GetError               (self)               :  return self.Gp(0x0001)
   def GetLastParExecError    (self)               :  return self.Gp(0x0001,4)

   def GetStatus              (self)               :  return self.Gp(0x0002)

   def Mode                   (self, mode=None)    :  return self.Par(0x0003,0, mode)
   def ModeOff                (self)               :  self.Sp(0x0003, 0)
   def ModeCurr               (self)               :  self.Sp(0x0003, 2)
   def ModeVel                (self)               :  self.Sp(0x0003, 3)
   def ModeSVel               (self)               :  self.Sp(0x0003, 5)
   def ModePos                (self)               :  self.Sp(0x0003, 7)

   def Disable                (self)               :  self.Sp(0x0004, 0)
   def Enable                 (self)               :  self.Sp(0x0004, 1)
   def AutoEnable             (self, value=None)   :  self.Par(0x0004, 1, value)

   def __event_cmd (self, index, subindex, cmd_list=None):
      if cmd_list == None:
         cmd_list = []

         for i in xrange(0,15):
            try:
               cmd = self.Gp(index, subindex+i)
            except:
               cmd = 0
            if cmd:
               cmd_list.append(cmd)
            else:
               break
         return cmd_list
      else:
         if type(cmd_list) != list:
            raise Exception("Argument \"cmd_list\" is not a list !")

         i = 0
         for cmd in cmd_list:
            self.Sp(index, subindex+i, cmd)
            i += 1
         try:
            self.Sp(index, subindex+i, 0)
         except:
            pass

   def Event_CmdOnError          (self, cmd_list=None):  return self.__event_cmd(0x0010, 0x11, cmd_list)    # RW, >=V1.85.00.64
   def Event_CmdOnWarning        (self, cmd_list=None):  return self.__event_cmd(0x0010, 0x21, cmd_list)    # RW, >=V1.85.00.64
   def Event_CmdOnCommError      (self, cmd_list=None):  return self.__event_cmd(0x0010, 0x31, cmd_list)    # RW, >=V1.85.00.64
   def Event_CmdOnGuardingError  (self, cmd_list=None):  return self.__event_cmd(0x0010, 0x41, cmd_list)    # RW, >=V1.85.00.64

   def Event_CmdOnSpecError (self, nr, err=None, cmd_list=None):                                            # RW, >=V1.85.00.64, nr=1..4
      if err==None and cmd_list==None:
         return (self.Gp(0x0012, 0x10 + (nr-1)*0x10), self.__event_cmd(0x0012, 0x11 + (nr-1)*0x10))
      else:
         self.Sp(0x0012, 0x10 + (nr-1)*0x10, err)
         self.__event_cmd(0x0012, 0x11 + (nr-1)*0x10, cmd_list)

   def Event_CmdOnUserCmd (self, nr, cmd_list=None):  return self.__event_cmd(0x0014, 0x11 + (nr-1)*0x10, cmd_list)  # RW, >=V1.85.00.81  nr=1..8

   def DevCode                (self)               :  return self.Gp(0x0020)
   def DevSubCode             (self)               :  return self.Gp(0x0020,1)   # >= V1.53

   def MainVersionSw          (self)               :  return self.Gp(0x0023,0)
   def SubVersionSw           (self)               :  return self.Gp(0x0023,1)   # >= V1.53
   def VersionSw              (self)               :  return ((self.MainVersionSw()<<16) | self.SubVersionSw())

   def ReleaseSw              (self):
      try:
         return self.Gp(0x0023,2)
      except:
         return 0

   def VersionHw              (self)               :  return self.Gp(0x0024)

   def MainVersionSwString    (self)               :  return self.VersionToString16(self.MainVersionSw())
   def SubVersionSwString     (self)               :  return self.VersionToString16(self.SubVersionSw())                   # >= V1.53
   def VersionSwString        (self)               :  return self.VersionToString32(ver=self.VersionSw(), rel=self.ReleaseSw())

   def VersionHwString        (self)               :  return self.VersionToString16(self.VersionHw())

   def DevMaxUp               (self)               :  return self.Gp(0x0031)
   def DevMaxIm               (self)               :  return self.Gp(0x0032)

   def DevDinEnable           (self, value=None, active_level=None): return self.Par(0x0050,0, self.DinBit2ParValue(value, active_level))    # io_nr is 0-based; active_level=0 Off; active_level>0 HighActive; active_level<0 LowActive
   def DevDinClearError       (self, value=None, active_level=None): return self.Par(0x0051,0, self.DinBit2ParValue(value, active_level))
   def DevDinStartStop        (self, value=None, active_level=None): return self.Par(0x0052,0, self.DinBit2ParValue(value, active_level))

   def DevDinLimitPos         (self, value=None, active_level=None): return self.Par(0x0055,0, self.DinBit2ParValue(value, active_level))
   def DevDinLimitNeg         (self, value=None, active_level=None): return self.Par(0x0056,0, self.DinBit2ParValue(value, active_level))
   def DevDinReference        (self, value=None, active_level=None): return self.Par(0x0057,0, self.DinBit2ParValue(value, active_level))    # >= V1.64.00.03

   def DevDoutError           (self, value=None, active_level=None): return self.Par(0x0060,0, self.DoutBit2ParValue(value, active_level))
   def DevDoutErrorReadyMoving(self, value=None, active_level=None): return self.Par(0x0061,0, self.DoutBit2ParValue(value, active_level))

   def DevContinueMode        (self, value=None)   :  return self.Par(0x0080,0, value)

   def DevMinUpError          (self, value=None)   :  return self.Par(0x0090,0, value)                      # in [mV]

   # I/O --------------------------------------------------------------------------------------------------------------------------
   #
   def Ain                    (self, nr=0)            :  return self.Gp(0x0100+nr)

   def AinOffset              (self, nr, value=None)  :  return self.Par(0x0108,nr, value)               # RW, >= V1.85.00.76
   def AinDeadband            (self, nr, value=None)  :  return self.Par(0x010A,nr, value)               # RW  db==0: OFF;    >= V1.85.00.87

                                                         # db = value_of_AinDeadband >  0:
                                                         #                           ^out                     if abs(ain) < db:
                                                         #                           |        /                  ain = 0
                                                         #                   -db     |       /         in     elif ain > 0:
                                                         #          ----------+------+------+------------>       ain -= db
                                                         #                   /       |     db                 else:
                                                         #                  /        |                           ain += db
                                                         #                           |
                                                         #
                                                         # db = value_of_AinDeadband <  0:
                                                         #                           ^out                     if abs(ain) < db:
                                                         #                           |   /                       ain = 0
                                                         #                     -db   |  |           in
                                                         #          --------------+--+--+------------>
                                                         #                        |  |   db
                                                         #                       /   |
                                                         #                           |

   def AinUe                  (self)               :  return self.Gp(0x0110)     #  [mV] Ue=+24V for Electronic
   def AinUp                  (self)               :  return self.Gp(0x0111)     #  [mV] Up=+XXV for Power
   def AinUm                  (self)               :  return self.Gp(0x0112)     #  [mV]
   def AinIm                  (self)               :  return self.Gp(0x0113)     #  [mA]
   def AinTemp                (self)               :  return self.Gp(0x0114,0)   #  [0.1 degreeC]
   def AinTempMotor           (self)               :  return self.Gp(0x0114,3)   #  [0.1 degreeC]
   def AinTrim                (self, nr=0)         :  return self.Gp(0x0115+nr)  #  [-1000..+1000]

   def Din                    (self, nr=0)         :  return self.Gp(0x0120,nr)
   def DinP0                  (self)               :  return self.Gp(0x0120)
   def DinHall                (self)               :  return self.Gp(0x0128,0)
   def DinEnc                 (self)               :  return self.Gp(0x0128,1)   # only for mcIO-C3,C4,D3,D4
   def DinDipSwitch           (self)               :  return self.Gp(0x0129)
   def DinNodeId              (self)               :  return self.Gp(0x0129,1)   # >= V1.71.01.10

   def Dout (self, p1, p2=None):
      if p2==None:               # Dout(value)              portnummer==0
         self.Sp(0x0150, p1)
      else:
         self.Sp(0x0150, p1, p2) # Dout(port_nummer, value)

   def DoutP0                 (self, value)        :  self.Sp(0x0150, value)

   def LedsEnable             (self, value=None)   :  self.Par(0x0158,0, value)
   def LedsState              (self, value=None)   :  self.Par(0x0158,1, value)

   # Current - Mode ---------------------------------------------------------------------------------------------------------------
   #
   def Curr                   (self, value=None)   :  return self.Par(0x0200,0, value) # Current Desired Value

   def CurrSource             (self, value=None)   :  return self.Par(0x0204,0, value)
   def CurrSourcePar          (self)               :  self.CurrSource(0x0200)
   def CurrSourceAin          (self, ain_nr)       :  self.CurrSource(0x0100+ain_nr)   # ain_nr = 0..n
   def CurrReference          (self, value=None)   :  return self.Par(0x0205,0, value) # Reference value for analog input

   def CurrKp                 (self, value=None)   :  return self.Par(0x0210,0, value)
   def CurrKi                 (self, value=None)   :  return self.Par(0x0211,0, value)

   def CurrLimitMax           (self, value=None)   :  return self.Par2([0x0221,0], [0x0223,0], value)
   def CurrLimitMaxPos        (self, value=None)   :  return self.Par(0x0221,0, value)
   def CurrLimitMaxNeg        (self, value=None)   :  return self.Par(0x0223,0, value)

   def CurrDynLimitMode       (self, value=None)   :  return self.Par(0x0224,0, value) # Curr                        >= 1.64.00.71
   def CurrDynLimitOff        (self)               :  self.CurrDynLimitMode(0)         #  |   +-------------+ Ipeak
   def CurrDynLimitOn         (self)               :  self.CurrDynLimitMode(1)         #  |   |              \
   def CurrDynLimitPeak       (self, value=None)   :  return self.Par(0x0224,1, value) #  |   |               \
   def CurrDynLimitCont       (self, value=None)   :  return self.Par(0x0224,2, value) #  |   |                +-------- Icont
   def CurrDynLimitTime       (self, value=None)   :  return self.Par(0x0224,3, value) # -+---+-------------+----------------->t
                                                                                       #      +--LimitTime--+

   def CurrAcc                (self, acc   =None)  :  return self.Par2([0x0240,0],[0x0241,0],acc)
   def CurrAcc_dI             (self, di_mA =None)  :  return self.Par (0x0240,0, di_mA)
   def CurrAcc_dT             (self, dt_ms =None)  :  return self.Par (0x0241,0, dt_ms)

   def CurrDec                (self, dec   =None)  :  return self.Par2([0x0242,0],[0x0243,0],dec)
   def CurrDec_dI             (self, di_mA =None)  :  return self.Par (0x0242,0, di_mA)
   def CurrDec_dT             (self, dt_ms =None)  :  return self.Par (0x0243,0, dt_ms)

   def CurrDecQuickStop       (self, dec   =None)  :  return self.Par2([0x0244,0],[0x0245,0],dec)
   def CurrDecQuickStop_dI    (self, di_mA =None)  :  return self.Par (0x0244,0, di_mA)
   def CurrDecQuickStop_dT    (self, dt_ms =None)  :  return self.Par (0x0245,0, dt_ms)

   def CurrRampType           (self, value =None)  :  self.Par(0x024C,0, value)
   def CurrRampDisable        (self)               :  self.Sp (0x024C, 0)
   def CurrRampEnable         (self)               :  self.Sp (0x024C, 1)

   def CurrRampState          (self)               :  return self.Gp(0x024D)

   def ActTrgCurr             (self)               :  return self.Gp(0x0260)                 #  >= V1.71.00.04
   def ActCmdCurr             (self)               :  return self.Gp(0x0261)                 #  >= V1.71.00.04
   def ActCurr                (self)               :  return self.Gp(0x0262)
   def ActAvgCurr             (self)               :  return self.Gp(0x0262,1)               #  >= V1.85.00.73
   def ActCurrFollowingError  (self)               :  return self.Gp(0x0263)                 #  >= V1.71.00.04

   def AvgCurrFilterLevel     (self, value=None)   :  return self.Par(0x02A0,0x10, value)    #  >= V1.85.00.73

   # aliases
   def TrgCurr                (self)               :  return self.Gp(0x0260)                 #  >= V1.71.00.04
   def CmdCurr                (self)               :  return self.Gp(0x0261)                 #  >= V1.71.00.04
   def CurrFollowingError     (self)               :  return self.Gp(0x0263)                 #  >= V1.71.00.04

   def CurrSampleTime         (self)               :  return self.Gp  (0x02A0,0)

   # VEL - Mode -------------------------------------------------------------------------
   #
   def Vel                    (self, value=None)   :  return self.Par(0x0300,0, value)

   def VelScale               (self, value=None)   :  return self.Par2([0x0302,0],[0x0303,0],value)
   def VelScaleNum            (self, value=None)   :  return self.Par (0x0302,0, value)
   def VelScaleDen            (self, value=None)   :  return self.Par (0x0303,0, value)

   def VelSource              (self, value=None)   :  return self.Par(0x0304,0, value)
   def VelSourcePar           (self)               :  self.VelSource (0x0300)
   def VelSourceAin           (self, ain_nr)       :  self.VelSource (0x0100+ain_nr)   # ain_nr = 0..n
   def VelReference           (self, value=None)   :  return self.Par(0x0305,0, value) # Reference value for analog input

   def VelDimension           (self, value=None)   :  return self.Par2([0x030A,0],[0x030B,0],value)
   def VelDimensionNum        (self, value=None)   :  return self.Par (0x030A,0, value) # Numerator
   def VelDimensionDen        (self, value=None)   :  return self.Par (0x030B,0, value) # Denominator

   def VelKp                  (self, value=None, phase=0):  return self.Par(0x0310,phase, value)
   def VelKi                  (self, value=None, phase=0):  return self.Par(0x0311,phase, value)
   def VelKd                  (self, value=None, phase=0):  return self.Par(0x0312,phase, value)
   def VelILimit              (self, value=None, phase=0):  return self.Par(0x0313,phase, value)   # >= V1.46
   def VelKvff                (self, value=None)         :  return self.Par(0x0314,0,     value)   # >= V1.64.00.04
   def VelKaff                (self, value=None)         :  return self.Par(0x0315,0,     value)   # >= V1.82.02.07
   def VelKIxR                (self, value=None)         :  return self.Par(0x0317,0,     value)
   def VelKdSampleTime        (self, value=None)         :  return self.Par(0x0318,0,     value)   # >= V1.52

   def VelKp_Stop             (self, value=None)   :  return self.VelKp(value, 1)   #
   def VelKp_AccPos           (self, value=None)   :  return self.VelKp(value, 2)   # ...Pos - Positiv
   def VelKp_ConstPos         (self, value=None)   :  return self.VelKp(value, 3)   #
   def VelKp_DecPos           (self, value=None)   :  return self.VelKp(value, 4)   #
   def VelKp_AccNeg           (self, value=None)   :  return self.VelKp(value, 5)   # ...Neg - Negativ
   def VelKp_ConstNeg         (self, value=None)   :  return self.VelKp(value, 6)   #
   def VelKp_DecNeg           (self, value=None)   :  return self.VelKp(value, 7)   #   VELOCITY PROFILE:
                                                                                    #
   def VelKi_Stop             (self, value=None)   :  return self.VelKi(value, 1)   #       AccPos          DecPos
   def VelKi_AccPos           (self, value=None)   :  return self.VelKi(value, 2)   #       |               |
   def VelKi_ConstPos         (self, value=None)   :  return self.VelKi(value, 3)   #       |    ConstPos   |
   def VelKi_DecPos           (self, value=None)   :  return self.VelKi(value, 4)   #       |  +----------+ |
   def VelKi_AccNeg           (self, value=None)   :  return self.VelKi(value, 5)   #         /            \
   def VelKi_ConstNeg         (self, value=None)   :  return self.VelKi(value, 6)   #   Stop /              \                  Stop
   def VelKi_DecNeg           (self, value=None)   :  return self.VelKi(value, 7)   # 0 ----+                +                +----
                                                                                    #                         \              /
   def VelKd_Stop             (self, value=None)   :  return self.VelKd(value, 1)   #                          \            /
   def VelKd_AccPos           (self, value=None)   :  return self.VelKd(value, 2)   #                         | +----------+ |
   def VelKd_ConstPos         (self, value=None)   :  return self.VelKd(value, 3)   #                         |   ConstNeg   |
   def VelKd_DecPos           (self, value=None)   :  return self.VelKd(value, 4)   #                         |              |
   def VelKd_AccNeg           (self, value=None)   :  return self.VelKd(value, 5)   #                         AccNeg         DecNeg
   def VelKd_ConstNeg         (self, value=None)   :  return self.VelKd(value, 6)   #
   def VelKd_DecNeg           (self, value=None)   :  return self.VelKd(value, 7)   #

   def VelILimit_Stop         (self, value=None)   :  return self.VelILimit(value, 1)
   def VelILimit_AccPos       (self, value=None)   :  return self.VelILimit(value, 2)
   def VelILimit_ConstPos     (self, value=None)   :  return self.VelILimit(value, 3)
   def VelILimit_DecPos       (self, value=None)   :  return self.VelILimit(value, 4)
   def VelILimit_AccNeg       (self, value=None)   :  return self.VelILimit(value, 5)
   def VelILimit_ConstNeg     (self, value=None)   :  return self.VelILimit(value, 6)
   def VelILimit_DecNeg       (self, value=None)   :  return self.VelILimit(value, 7)

   def VelLimitMax            (self, value=None)   :  return self.Par2([0x0321,0], [0x0323,0], value)
   def VelLimitMaxPos         (self, value=None)   :  return self.Par (0x0321,0, value)
   def VelLimitMaxNeg         (self, value=None)   :  return self.Par (0x0323,0, value)

   def VelAcc                 (self, acc   =None)  :  return self.Par2([0x0340,0],[0x0341,0],acc)
   def VelAcc_dV              (self, dv_rpm=None)  :  return self.Par (0x0340,0, dv_rpm)
   def VelAcc_dT              (self, dt_ms =None)  :  return self.Par (0x0341,0, dt_ms )

   def VelDec                 (self, dec   =None)  :  return self.Par2([0x0342,0],[0x0343,0],dec)
   def VelDec_dV              (self, dv_rpm=None)  :  return self.Par (0x0342,0, dv_rpm)
   def VelDec_dT              (self, dt_ms =None)  :  return self.Par (0x0343,0, dt_ms )

   def VelDecQuickStop        (self, dec   =None)  :  return self.Par2([0x0344,0],[0x0345,0],dec)
   def VelDecQuickStop_dV     (self, dv_rpm=None)  :  return self.Par (0x0344,0, dv_rpm)
   def VelDecQuickStop_dT     (self, dt_ms =None)  :  return self.Par (0x0345,0, dt_ms )

   def VelRampType            (self, value =None)  :  return self.Par(0x034C,0, value)
   def VelRampDisable         (self)               :  self.Sp (0x034C, 0)
   def VelRampEnable          (self)               :  self.Sp (0x034C, 1)

   def VelRampState           (self)               :  return self.Gp(0x034D)

   def VelFeedback            (self, value=None)   :  return self.Par(0x0350,0, value)
   def VelFeedbackAuto        (self)               :  self.Sp(0x0350,      0)
   def VelFeedbackAin0        (self)               :  self.Sp(0x0350, 0x0100)
   def VelFeedbackUm          (self)               :  self.Sp(0x0350, 0x0112)
   def VelFeedbackEmk         (self)               :  self.Sp(0x0350, 0x0112)
   def VelFeedbackHall        (self)               :  self.Sp(0x0350, 0x094A)
   def VelFeedbackEnc         (self)               :  self.Sp(0x0350, 0x096A)
   def VelFeedbackEnc2        (self)               :  self.Sp(0x0350, 0x096A)

   def ActTrgVel              (self)               :  return self.Gp (0x0360)             # >= V.1.85.03.30
   def ActCmdVel              (self)               :  return self.Gp (0x0361)             # >= V.1.85.03.30
   def ActVel                 (self, value=None)   :  return self.Par(0x0362,0, value)    # >= V.1.85.03.30
   def ActVelFollowingError   (self)               :  return self.Gp (0x0363)             # >= V.1.85.03.30

   def VelFeedbackReference   (self, value=None)   :  return self.Par(0x0350,3, value)

   def VelAcc_rpm2            (self, acc=None)     :  return self.Par(0x0380,0, acc)
   def VelDec_rpm2            (self, dec=None)     :  return self.Par(0x0381,0, dec)
   def VelDecQuickStop_rpm2   (self, dec=None)     :  return self.Par(0x0382,0, dec)

   def VelSampleTime          (self, st_us=None)   :  return self.Par(0x03A0,0, st_us)

   def VelBlockageGuarding_VelLow (self, value=None): return self.Par(0x03C0,1, value)    # -1 = OFF
   def VelBlockageGuarding_VelHigh(self, value=None): return self.Par(0x03C0,2, value)    # -1 = BlockageGuarding_VelLow + 10%
   def VelBlockageGuarding_Time   (self, t_ms =None):
      if t_ms == None:
         return self.Gp(0x03C0,3)*100
      else:
         self.Sp(0x03C0,3, t_ms/100)

   # aliases
   def TrgVel                 (self)               :  return self.Gp (0x0360)             # >= V.1.85.03.30
   def CmdVel                 (self)               :  return self.Gp (0x0361)             # >= V.1.85.03.30
   def VelFollowingError      (self)               :  return self.Gp (0x0363)             # >= V.1.85.03.30

   # SVel Mode - (old Name: Pwm Mode) ---------------------------------------------------------------------------------------------
   #
   def SVel                   (self, value=None)   :  return self.Par (0x0500,0, value)

   def SVelScale              (self, value=None)   :  return self.Par2([0x0502,0],[0x0503,0],value)
   def SVelScaleNum           (self, value=None)   :  return self.Par (0x0502,0, value)
   def SVelScaleDen           (self, value=None)   :  return self.Par (0x0503,0, value)

   def SVelSource             (self, value=None)   :  return self.Par (0x0504,0, value)
   def SVelSourcePar          (self)               :  self.SVelSource (0x0500)
   def SVelSourceAin          (self, ain_nr=0)     :  self.SVelSource (0x0100+ain_nr)        # ain_nr = 0..n
   def SVelReference          (self, value=None)   :  return self.Par (0x0505,0, value)      # Reference value for analog input

   def SVelKp                 (self, value=None)   :  return self.Par (0x0510,0, value)
   def SVelKi                 (self, value=None)   :  return self.Par (0x0511,0, value)
   def SVelKIxR               (self, value=None)   :  return self.Par (0x0517,0, value)

   def SVelFeedback           (self, value=None)   :  return self.Par (0x0550,0, value)
   def SVelFeedbackAuto       (self)               :  return self.Par (0x0550,0, 0)
   def SVelFeedbackUm         (self)               :  return self.Par (0x0550,0, 0x0112)
   def SVelFeedbackEmk        (self)               :  return self.Par (0x0550,0, 0x0112)
   def SVelFeedbackHall       (self)               :  return self.Par (0x0550,0, 0x094A)
   def SVelFeedbackEnc        (self)               :  return self.Par (0x0550,0, 0x096A)

   def SVelSampleTime         (self)               :  return self.Gp  (0x05A0,0)

   def SVelMaxVel             (self, value=None)   :  return self.Par (0x05A1,0, value)

   # POS - Mode -------------------------------------------------------------------------------------------------------------------
   #
   def PosMode                   (self, mode=None) :  return self.Par(0x0708,0, mode)
   def PosModeInterp             (self)            :  return self.Par(0x0708,0, 1)
   def PosModeModulo             (self)            :  return self.Par(0x0708,0, 2)

   def PosLimit                  (self, pos=None)  :  return self.Par2([0x0720,0],[0x0720,1],pos)
   def PosLimitMin               (self, pos=None)  :  return self.Par (0x0720,0, pos)
   def PosLimitMax               (self, pos=None)  :  return self.Par (0x0720,1, pos)

   def PosFollowingErrorWindow   (self, value=None):  return self.Par(0x0732,0, value)
   def PosFollowingErrorWindowDyn(self, value=None):  return self.Par(0x0732,1, value)

   def PosFollowingErrorTime     (self, value=None):  return self.Par(0x0733,0, value)
   def PosFollowingErrorTimeDyn  (self, value=None):  return self.Par(0x0733,1, value)

   def PosWindow                 (self, value=None):  return self.Par(0x073A,0, value)    # >= V1.69.00.30
   def PosWindowTime             (self, value=None):  return self.Par(0x073B,0, value)    # >= V1.69.00.30
   def PosWindowDisable          (self):              return self.PosWindow(0xFFFFFFFF)   # >= V1.69.00.30
   def PosWindowTimeout          (self, value=None):  return self.Par(0x073B,1, value)    # >= V1.70.00.00

   def PosReachedConfigFlags     (self, value=None):  return self.Par(0x073C,0, value)

   def PosRampType               (self, value=None):  return self.Par(0x074C,0, value)
   def PosRampState              (self)            :  return self.Gp(0x074D)

   def ActTrgPos                 (self)            :  return self.Gp (0x0760)             # >= V1.71.00.04
   def ActCmdPos                 (self)            :  return self.Gp (0x0761)
   def ActPos                    (self, value=None):  return self.Par(0x0762,0, value)
   def ActPosFollowingError      (self)            :  return self.Gp (0x0763)
   def ActIndexPos               (self)            :  return self.Gp (0x0764)             # >= V1.58
   def ActOrigin                 (self)            :  return self.Par(0x0765)             # >= V1.85.03.22

   def ActTrgPos_cnt             (self)            :  return self.Gp (0x0770)             # >= V1.71.00.04
   def ActCmdPos_cnt             (self)            :  return self.Gp (0x0771)             # >= V1.50
   def ActPos_cnt                (self, value=None):  return self.Par(0x0772,0, value)    # >= V1.50
   def ActPosFollowingError_cnt  (self)            :  return self.Gp (0x0773)             # >= V1.50
   def ActIndexPos_cnt           (self)            :  return self.Gp (0x0774)             # >= V1.58
   def ActOrigin_cnt             (self)            :  return self.Par(0x0775)             # >= V1.85.03.22

   def MovA                      (self, value)     :  self.Sp(0x0790, value)
   def Mova                      (self, value)     :  self.Sp(0x0790, value)

   def MovR                      (self, value)     :  self.Sp(0x0791, value)
   def Movr                      (self, value)     :  self.Sp(0x0791, value)

   def IsMovCompleted (self):
      if self.PosRampState() == 0:
         return 1
      else:
         return 0

   def PosGearBacklashCompPath   (self, value=None):  return self.Par(0x07A4,1, value)    # RW, 0=disabled; >0 pos. dir; <0 neg. dir
   def PosGearBacklashCompVel    (self, value=None):  return self.Par(0x07A4,2, value)    # RW

   # aliases
   def TrgPos                    (self)            :  return self.Gp (0x0760)             #  >= V1.71.00.04
   def CmdPos                    (self)            :  return self.Gp (0x0761)
   def Pos                       (self, value=None):  return self.Par(0x0762,0, value)
   def PosFollowingError         (self)            :  return self.Gp (0x0763)
   def IndexPos                  (self)            :  return self.Gp (0x0764)             # >= V1.58
   def Origin                    (self)            :  return self.Par(0x0765)             # >= V1.85.03.22

   # aliases
   def TrgPos_cnt                (self)            :  return self.Gp (0x0770)             # >= V1.71.00.04
   def CmdPos_cnt                (self)            :  return self.Gp (0x0771)             # >= V1.50
   def Pos_cnt                   (self, value=None):  return self.Par(0x0772,0, value)
   def PosFollowingError_cnt     (self)            :  return self.Gp (0x0773)             # >= V1.50
   def IndexPos_cnt              (self)            :  return self.Gp (0x0774)             # >= V1.58
   def Origin_cnt                (self)            :  return self.Par(0x0775)             # >= V1.85.03.22

   # Homing Functions (Firmware >= V1.64.00.03)
   #
   def HomingCmd                 (self,cmd)        :  self.Sp(0x07B0,cmd)
   def HomingStart               (self)            :  self.HomeCmd(1)
   def HomingBreak               (self)            :  self.HomeCmd(2)

   def HomingStatus              (self)            :  return self.Gp(0x07B1,0)
   def HomingError               (self)            :  return self.Gp(0x07B1,1)
   def HomingState               (self)            :  return self.Gp(0x07B1,2)
   def HomingRef2Index           (self)            :  return self.Gp(0x07B1,3)
   def HomingRef2Index_cnt       (self)            :  return self.Gp(0x07B1,4)

   def HomingMethod              (self, nr  =None) :  return self.Par(0x07B2,0, nr  )
   def HomingOffset              (self, offs=None) :  return self.Par(0x07B3,0, offs)
   def HomingVelSwitch           (self, vel =None) :  return self.Par(0x07B4,0, vel )
   def HomingVelZero             (self, vel =None) :  return self.Par(0x07B4,1, vel )
   def HomingAcc                 (self, acc =None) :  return self.Par(0x07B5,0, acc )
   def HomingDec                 (self, dec =None) :  return self.Par(0x07B5,1, dec )
   def HomingMaxIndexPath        (self, path=None) :  return self.Par(0x07B6,0, path)
   def HomingIndexOffset         (self, pos =None) :  return self.Par(0x07B6,1, pos )  # >= V1.71.00.04

   # Interpolation
   #
   def InterpMethod              (self, value=None):  return self.Par(0x07C2,0, value) # >= V1.71.01.19
   def InterpTime                (self, t_us=None) :  return self.Par(0x07C2,1, t_us)  # >= V1.71.01.19
   def InterpReference           (self, rounds=None): return self.Par(0x07C2,2, rounds)# >= V1.71.01.19
   def InterpBufConfig           (self, value=None):  return self.Par(0x07C5,0, value) # >= V1.71.01.19
   def InterpData                (self, value=None):  return self.Par(0x07C6,0, value) # >= V1.71.01.19
   def InterpActTrgPos           (self, value=None):  return self.Par(0x07C7,0, value) # >= V1.71.01.19
   def InterpActCmdPos           (self, value=None):  return self.Par(0x07C7,1, value) # >= V1.71.01.19
   def InterpActPos              (self, value=None):  return self.Par(0x07C7,2, value) # >= V1.71.01.19

   def PosModuloMethod           (self, value=None):  return self.Par(0x07C8,0, value)
   def PosModuloValue            (self, value=None):  return self.Par(0x07C9,0, value)

   # obsolete functions
   def PosModeInterpolation      (self)            :  return self.Par(0x0708,0, 1)
   def PosInterpolationMethod    (self, value=None):  return self.Par(0x07C2,0, value) # >= V1.71.01.19
   def PosInterpolationTime      (self, t_us=None) :  return self.Par(0x07C2,1, t_us)  # >= V1.71.01.19
   def PosInterpolationReference (self, rounds=None): return self.Par(0x07C2,2, rounds)# >= V1.71.01.19
   def PosInterpolationBufConfig (self, value=None):  return self.Par(0x07C5,0, value) # >= V1.71.01.19
   def PosInterpolationData      (self, value=None):  return self.Par(0x07C6,0, value) # >= V1.71.01.19

   # System -----------------------------------------------------------------------------------------------------------------------
   #
   def PwmFreq                (self, freq_Hz=None) :  return self.Par(0x0830,0, freq_Hz)

   def PwmMode                (self, value=None)   :  return self.Par(0x0830,1, value)
   def PwmModeSym             (self)               :  return self.Par(0x0830,1, 0)
   def PwmModeAsym            (self)               :  return self.Par(0x0830,1, 1)

   def PwmModeParam           (self, value=None)   :  return self.Par(0x0830,2, value)

   def SysClock               (self)               :  return self.Gp(0x0850,0)
   def SysTimer2ms            (self, value=None)   :  return self.Par(0x0850,2, value)

   # Motor ------------------------------------------------------------------------------------------------------------------------
   #
   def MotorType              (self, value=None)   :  return self.Par(0x0900,0, value)
   def MotorTypeDC            (self)               :  self.Sp(0x0900, 0)
   def MotorTypeBLDC          (self)               :  self.Sp(0x0900, 1)

   def MotorNn                (self, value=None)   :  return self.Par(0x0901,0, value)
   def MotorUn                (self, value=None)   :  return self.Par(0x0902,0, value)
   def MotorPolN              (self, value=None)   :  return self.Par(0x0910,0, value)

   def MotorPolarity          (self, value=None)   :  return self.Par(0x0911,0, value)

   # Hall
   def HallType               (self, value=None)   :  return self.Par(0x0940,0, value)       # *RW 0=120, 1=60
   def HallType120            (self)               :  self.Sp(0x0940, 0)
   def HallType60             (self)               :  self.Sp(0x0940, 1)

   def HallResolution         (self, value=None)      :  return self.Par(0x0942,0, value)    # RW
   def HallDiagErrCounter     (self, nr, value=None)  :  return self.Par(0x0944,nr, value)   # RW

   def HallActSector          (self, value=None)      :  return self.Par(0x0945,0, value)    # RW uint8
   def HallTuningSector       (self, nr, value=None)  :  return self.Par(0x0946,nr, value)   # RW uint8
   def HallTuningStart        (self)                  :  self.Sp (0x0946, 6, 1)
   def HallTuningCurr         (self, value=None)      :  self.Par(0x0946, 7, value)
   def HallTuningWrEnable     (self)                  :  self.Sp (0x0946, 8, 0x55AA)

   def HallDoutPulse_Mode        (self, value=None)   :  return self.Par(0x0949,0, value)    #  RW uint8   Bit0=Enabled   (dP: 02.10.2006 16:52 - wurde vom _ConfigFlags auf _Mode umbennant)
   def HallDoutPulse_MaskDoutA   (self, value=None)   :  return self.Par(0x0949,1, value)    #  RW uint8
   def HallDoutPulse_MaskDoutB   (self, value=None)   :  return self.Par(0x0949,2, value)    #  RW uint8
   def HallDoutPulse_ModuloValue (self, value=None)   :  return self.Par(0x0949,3, value)    #  RW uint16

   def HallActPos             (self, value=None)      :  return self.Par(0x094A,0, value)    #  RW, >= V1.52
   def HallCounter            (self, nr, value=None)  :  return self.Par(0x094D,nr, value)   #  RW, >= V1.82.02.16

   # Encoder
   def EncResolution          (self, value=None)   :  return self.Par(0x0962,0, value)
   def EncResolution_lines    (self, value=None)   :  return self.Par(0x0963,0, value)
   def EncDiagEnable          (self, value=None)   :  return self.Par(0x0964,0, value)       #  RW, >= V1.82.02.50
   def EncDiagStatus          (self)               :  return self.Gp (0x0964,1)              #  RW, >= V1.82.02.50
   def EncActPos              (self, value=None)   :  return self.Par(0x096A,0, value)       #  RW, >= V1.52
   def EncActIndexPos         (self)               :  return self.Gp (0x096B)
   def EncActIndexCount       (self, value=None)   :  return self.Par(0x096C,0, value)
   def EncActRawPos           (self, value=None)   :  return self.Par(0x096F,0x10, value)    #  RW, >= V1.85.00.42
   def EncCmd                 (self, value=None)   :  return self.Par(0x096F,0x00, value)    #  RW, >= V1.85.00.42
   def EncStatus              (self)               :  return self.Gp (0x096F,0x01)           #  RW, >= V1.85.00.42

   # obsolete functions
   def Polarity               (self, value=None)   :  return self.Par(0x0911,0, value)
   def MotorHallType          (self, value=None)   :  return self.Par(0x0940,0, value)       #  RW 0=120, 1=60
   def MotorHallType120       (self)               :  self.Sp(0x0940, 0)
   def MotorHallType60        (self)               :  self.Sp(0x0940, 1)
   def MotorEncResolution     (self, value=None)   :  return self.Par(0x0962,0, value)
   def MotorEnc2Resolution    (self, value=None)   :  return self.Par(0x0962,0, value)
   def Enc2Resolution         (self, value=None)   :  return self.Par(0x0962,0, value)
   #
   def ActHallPos             (self, value=None)   :  return self.Par(0x094A,0, value)       #  RW, >= V1.52
   #
   def ActEncPos              (self, value=None)   :  return self.Par(0x096A,0, value)       #  RW, >= V1.52
   def ActEnc2Pos             (self, value=None)   :  return self.Par(0x096A,0, value)       #  RW, >= V1.52
   def ActEncIndexPos         (self)               :  return self.Gp (0x096B)
   def ActEncIndexCount       (self, value=None)   :  return self.Par(0x096C,0, value)
   #
   def ActPosEnc2             (self, value=None)   :  return self.Par(0x096A,0, value)       #  RW, >= V1.52
   def ActPosHall             (self, value=None)   :  return self.Par(0x094A,0, value)       #  RW, >= V1.52
   def ActPosEnc              (self, value=None)   :  return self.Par(0x096A,0, value)       #  RW, >= V1.52
   def ActIndexPosEnc         (self)               :  return self.Gp (0x096B)
   def ActIndexCountEnc       (self, value=None)   :  return self.Par(0x096C,0, value)
   def ActRawPosEnc           (self, value=None)   :  return self.Par(0x096F,0x10, value)    #  RW, >= V1.85.00.42

   # Measurement -(ab V1.45)-------------------------------------------------------------
   #
   def MesVelTime             (self, time_ms=None) :  return self.Par(0x0A02,0, time_ms)
   def MesVel_cnt             (self)               :  return self.Gp (0x0A04,0)              # [counts/MesVelTime]
   def MesVel                 (self)               :  return self.Gp (0x0A04,1)              # [user], >= V1.69.00.61

   # Factorgroup -(ab V1.50)-------------------------------------------------------------------------------------------------------
   #
   def FctControl             (self, value=None)   :  return self.Par(0x0B00,0, value)
   def FctPrecision           (self, value=None)   :  return self.Par(0x0B00,1, value)
   def FctPolarity            (self, value=None)   :  return self.Par(0x0B10,0, value)
   def FctPosNotationIndex    (self, value=None)   :  return self.Par(0x0B11,0, value)
   def FctPosDimIndex         (self, value=None)   :  return self.Par(0x0B12,0, value)
   def FctVelNotationIndex    (self, value=None)   :  return self.Par(0x0B13,0, value)
   def FctVelDimIndex         (self, value=None)   :  return self.Par(0x0B14,0, value)
   def FctAccNotationIndex    (self, value=None)   :  return self.Par(0x0B15,0, value)
   def FctAccDimIndex         (self, value=None)   :  return self.Par(0x0B16,0, value)
   #
   def FctPosScale            (self, value=None)   :  return self.ParFraction(0x0B17, value) # value = [numerator,denominator]
   def FctVelScale            (self, value=None)   :  return self.ParFraction(0x0B18, value) # value = [numerator,denominator]
   def FctGearRatio           (self, value=None)   :  return self.ParFraction(0x0B19, value) # value = [numerator,denominator]
   def FctFeedConstant        (self, value=None)   :  return self.ParFraction(0x0B1A, value) # value = [numerator,denominator]

   # Helper Functions -------------------------------------------------------------------------------------------------------------
   #
   def PrintInfos (self, extd=0, clrerr=True):
      version        = self.VersionSwString()
      device_code    = self.DevCode()
      device_subcode = self.DevSubCode()

      Msg.Print("Version Soft.  = %s\n"    % version)
      Msg.Print("Device Code    = %04Xh\n" % device_code)
      Msg.Print("Device SubCode = %04Xh\n" % device_subcode)

      if extd:
         pass

      err = self.GetError()

      Msg.Print("Error          = %d\n" % err)

      if clrerr:
         if (err == -318) or (err == -316):  #DSA Parameter Error (CRC32 or BadVersion)
            self.ClearParam()
         self.ClearError()

   # Constants --------------------------------------------------------------------------------------------------------------------

   # Commands
   CMD_Nop           = 0x00
   CMD_ClearError    = 0x01
   CMD_QuickStop     = 0x02
   CMD_Halt          = 0x03
   CMD_Continue      = 0x04
   CMD_Update        = 0x05
   CMD_ModeOff       = 0x10
   CMD_ModeCurr      = 0x12
   CMD_ModeVel       = 0x13
   CMD_ModeSVel      = 0x15
   CMD_ModePos       = 0x17
   CMD_Disable       = 0x20
   CMD_Enable        = 0x21
   CMD_Curr          = 0x30
   CMD_Vel           = 0x31
   CMD_SVel          = 0x32
   CMD_Mova          = 0x33
   CMD_Movr          = 0x34
   CMD_MovUpdate     = 0x36
   CMD_HOME_None     = 0x50
   CMD_HOME_Start    = 0x51
   CMD_HOME_Break    = 0x52
   CMD_HOME_Halt     = 0x53
   CMD_HOME_Restart  = 0x54
   CMD_HOME_SetPos   = 0x58
   CMD_UserCmd1      = 0x71
   CMD_UserCmd2      = 0x72
   CMD_UserCmd3      = 0x73
   CMD_UserCmd4      = 0x74
   CMD_UserCmd5      = 0x75
   CMD_UserCmd6      = 0x76
   CMD_UserCmd7      = 0x77
   CMD_UserCmd8      = 0x78

   # DIN/DOUT Nummers of Bits for DevDin.... functions
   DIN_BIT0  = 0x0130
   DIN_BIT1  = 0x0131
   DIN_BIT2  = 0x0132
   DIN_BIT3  = 0x0133
   DIN_BIT4  = 0x0134
   #...
   DIN_BIT7  = 0x0137      # for future use
   #
   DOUT_BIT0 = 0x0160
   DOUT_BIT1 = 0x0161
   DOUT_BIT2 = 0x0162
   DOUT_BIT3 = 0x0163
   DOUT_BIT4 = 0x0164
   #...
   DOUT_BIT7 = 0x0167      # for future use

   # GetStatus (Bits)
   STAT_Enabled         = (1 <<  0)
   STAT_Error           = (1 <<  1)
   STAT_Warning         = (1 <<  2)
   STAT_Moving          = (1 <<  3)
   STAT_Reached         = (1 <<  4)
   STAT_Limit           = (1 <<  5)
   STAT_FollowingError  = (1 <<  6)
   STAT_HomingDone      = (1 <<  7)
   STAT_Toggle          = (1 <<  8)
   STAT_CmdToggle       = (1 <<  9)
   STAT_CmdError        = (1 << 10)
   STAT_StopOrHalt      = (1 << 11)
   STAT_LimitCurrent    = (1 << 12)
   STAT_LimitVel        = (1 << 13)
   STAT_LimitPos        = (1 << 14)
   STAT_LimitPwm        = (1 << 15)

   # Bits of HomingStatus
   HOME_STAT_Active     = (1<<0)
   HOME_STAT_Error      = (1<<1)
   HOME_STAT_Warning    = (1<<2)
   HOME_STAT_Break      = (1<<3)
   HOME_STAT_Done       = (1<<4)
   HOME_STAT_IndexFound = (1<<5)
   HOME_STAT_VelSlow    = (1<<6)
   HOME_STAT_DirNeg     = (1<<7)

   # Values of HomeState()
   HOME_STATE_Idle               = 0
   HOME_STATE_Start              = 1
   HOME_STATE_Wait4Ref           = 2
   HOME_STATE_Wait4RefRelease    = 3
   HOME_STATE_Wait4EndNeg        = 4
   HOME_STATE_Wait4EndNegRelease = 5
   HOME_STATE_Wait4EndPos        = 6
   HOME_STATE_Wait4EndPosRelease = 7
   HOME_STATE_Wait4Index         = 8
   HOME_STATE_Wait4MoveCompleted = 0x10   # Tmp-State
   HOME_STATE_Break              = 0x20   # Tmp-State
   HOME_STATE_Done               = 0x21   # Tmp-State
   HOME_STATE_End                = 0x22   # Tmp-State

   # Obsolete functions names (only for for compatibility reason) -----------------------------------------------------------------
   #
   def DevVersionSw           (self)               :  return self.VersionSw()
   def DevVersionHw           (self)               :  return self.VersionHw()
   def DevVersionSwString     (self)               :  return self.VersionSwString()
   def DevVersionHwString     (self)               :  return self.VersionHwString()
   #
   def DevDinErrorClear       (self, value=None, active_level=None): return self.DevDinClearError(value, active_level)
   def DevDinHwLimitPos       (self, value=None)   :  return self.DevDinLimitPos(value)
   def DevDinHwLimitNeg       (self, value=None)   :  return self.DevDinLimitNeg(value)
   def DevDinReferenz         (self, value=None)   :  return self.DevDinReference(value)
   #
   def ModePwm                (self)               :  self.ModeSVel()
   def ModeVPos               (self)               :  self.ModePos()
   #
   def CurrDesValue           (self, value=None)   :  return self.Curr(value)
   def CurrDesValueSource     (self, value=None)   :  return self.CurrSource(value)
   #
   def VelDesValue            (self, value=None)   :  return self.Vel(value)
   def VelDesValueScaleNum    (self, value=None)   :  return self.VelScaleNum(value)
   def VelDesValueScaleDen    (self, value=None)   :  return self.VelScaleDen(value)
   def VelDesValueSource      (self, value=None)   :  return self.VelSource(value)
   def VelDesValueReference   (self, value=None)   :  return self.VelReference(value)  # Reference value for analog input
   #
   def Pwm                    (self, value=None)   :  return self.SVel(value)
   def PwmScaleNum            (self, value=None)   :  return self.SVelScaleNum(value)
   def PwmScaleDen            (self, value=None)   :  return self.SVelScaleDen(value)
   def PwmSource              (self, value=None)   :  return self.SVelSource(value)
   def PwmKp                  (self, value=None)   :  return self.SVelKp(value)
   def PwmKi                  (self, value=None)   :  return self.SVelKi(value)
   #
   def PwmDesValue            (self, value=None)   :  return self.SVel(value)
   def PwmDesValueScaleNum    (self, value=None)   :  return self.SVelScaleNum(value)
   def PwmDesValueScaleDen    (self, value=None)   :  return self.SVelScaleDen(value)
   def PwmDesValueSource      (self, value=None)   :  return self.SVelSource(value)

   def ActIndexCount          (self, value=None)   :  return self.ActIndexCountEnc(value)

   def HomeCmd                   (self,cmd)        :  self.HomingCmd(cmd)
   def HomeStart                 (self)            :  self.HomingStart()
   def HomeBreak                 (self)            :  self.HomingBreak()

   def HomeStatus                (self)            :  return self.HomingStatus()
   def HomeError                 (self)            :  return self.HomingError()
   def HomeState                 (self)            :  return self.HomingState()
   def HomeRef2Index             (self)            :  return self.HomingRef2Index()
   def HomeRef2Index_cnt         (self)            :  return self.HomingRef2Index_cnt()

   def HomeMethod                (self, nr  =None) :  return self.HomingMethod(nr)
   def HomeOffset                (self, offs=None) :  return self.HomingOffset(offs)
   def HomeVelSwitch             (self, vel =None) :  return self.HomingVelSwitch(vel)
   def HomeVelZero               (self, vel =None) :  return self.HomingVelZero(vel)
   def HomeAcc                   (self, acc =None) :  return self.HomingAcc(acc)
   def HomeDec                   (self, dec =None) :  return self.HomingDec(dec)
   def HomeMaxIndexPath          (self, path=None) :  return self.HomingMaxIndexPath(path)
   def HomeIndexOffset           (self, pos =None) :  return self.HomingIndexOffset(pos)

   def FctPosEncoderResolution(self, value=None)   :  return self.FctPosScale(value)   # value = [numerator,denominator]
   def FctVelEncoderResolution(self, value=None)   :  return self.FctVelScale(value)   # value = [numerator,denominator]
   #--

# for compatibility reason
dsa = Dsa

# TEST ----------------------------------------------------------------------------------------------------------------------------
#
def __test__():
   pass

#==================================================================================================================================
if __name__ == '__main__':
   __test__()
