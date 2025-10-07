# -*- coding: utf-8 -*-
#=================================================================================================================================#
#                                                                      Copyright (c) 1997-2020 by miControl. All rights reserved. #
# File     : ds301.h                                                                                                              #
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
# Brief:    Ds301 class for CANopen miControl Devices
#
#----------------------------------------------------------------------------------------------------------------------------------
# History:                                                  (Symbol legend: + Added, - Removed, ~ Changed, ! Correction, # Comment)
#
#  25.02.2004 dP: +UserNodeId, +UserBaudrate, +AutoOperational, +MsgOnBootup
#  01.03.2004 dP: +IsEnabledDs402, +EnableDs402, +DisableDs402
#  13.05.2004 dP: +IsDisabledDs402
#  17.05.2004 dP: +ParamRxPdo_InhibitTime, +ParamTxPdo_InhibitTime
#  30.07.2004 dP: +CmdCpuReset (ab Firmware cop1.69.00.26)
#  09.08.2004 dP: ~timeouts for SaveParam
#  11.10.2004 dP: ~timeouts for SaveParam (timeout = 21000ms)
#  13.10.2004 dP: ~CmdCpuReset timeout is now 50 ms
#  15.02.2005 dP: V1.10.01.00 !SaveParam_App, !LoadParam_App
#  12.09.2006 dP: V1.20.00.00 +: Sdo_RxCobId, Sdo_TxCobId, Sdo_CobId, UseSdo
#                 This Functions working only with Firmware
#                 greater of 1.80.00.00
#  31.10.2006 dP: !UserBaudrate
#  03.11.2006 dP: V1.21.00.00 +: +GuardCobId, +ConsumerHeartbeatTime,
#                                +ProducerHeartbeatTime
#
#==================================================================================================================================
if __package__:
   from .cop_base import *
else:
   from cop_base  import *

__all__ = ["Ds301","ds301"]

#==================================================================================================================================
class Ds301 (CopBase):

   ClassVersion = (1,0x21, 0x00,0x00)

   # DS301 Objects ----------------------------------------------------------------------------------------------------------------
   #
   def DeviceType                (self):                       return self.SdoRd(0x1000, 0)

   def ErrorReg                  (self):                       return self.SdoRd(0x1001, 0)
   def ManufStatusReg            (self):                       return self.SdoRd(0x1002, 0)

   def ErrorField                (self, subindex, value=None): return self.Sdo(0x1003, subindex, value)
   def ClearErrorField           (self):                       self.SdoWr(0x1003, 0, 0)

   def SyncMsgCobId              (self, cob_id=None):          return self.Sdo  (0x1005, 0, cob_id)

   def ManufDeviceName           (self):                       return self.SdoRd(0x1008, 0)
   def ManufHwVer                (self):                       return self.SdoRd(0x1009, 0)
   def ManufSwVer                (self):                       return self.SdoRd(0x100A, 0)

   def GuardTime                 (self, time_ms=None):         return self.Sdo  (0x100C, 0, time_ms)
   def LifeTimeFactor            (self, factor=None):          return self.Sdo  (0x100D, 0, factor )

   def GuardCobId                (self, cob_id=None):          return self.Sdo  (0x100E, 0, cob_id)

   def ConsumerHeartbeat (self, nr, node_id=None, time_ms=None):
      if (node_id==None) and (time_ms==None):
         value = self.SdoRd(0x1016,nr)
         return ((value >> 16) & 0xFF), (value & 0xFFFF)
      else:
         if (time_ms==None):
            time_ms = 0
         self.SdoWr(0x1016, nr, ((node_id & 0xFF) << 16) | (time_ms & 0xFFFF))

   def DisableConsumerHeartbeat (self, nr):                    self.ConsumerHeartbeat(nr, node_id=0, time_ms=0)

   def ProducerHeartbeatTime     (self, time_ms=None):         return self.Sdo  (0x1017, 0, time_ms)
   def DisableProducerHeartbeat  (self):                       return self.ProducerHeartbeatTime(0)

   def SaveParam (self, subindex):
      self.SdoWr(0x1010, subindex, 0x65766173, timeout=21000)                    # timeout = 2048/2*20ms = 20480ms (2048 = EEPROM_Size)

   def SaveParam_All             (self):                       self.SaveParam(1) # Saved objects range = 1000h - 9FFFh
   def SaveParam_Comm            (self):                       self.SaveParam(2) #                     = 1000h - 1FFFh
   def SaveParam_App             (self):                       self.SaveParam(3) #                     = 6000h - 6FFFh
   def SaveParam_2000            (self):                       self.SaveParam(5) #                     = 2000h - 2FFFh
   def SaveParam_3000            (self):                       self.SaveParam(6) #                     = 3000h - 3FFFh

   def LoadParam (self, subindex):
      try:
         self.SdoWr(0x1011, subindex, 0x64616F6C)
      except:
         import time
         time.sleep(1.0)

   def LoadParam_All             (self):                       return self.LoadParam(1)   # Restored objects range = 1000h - 9FFFh
   def LoadParam_Comm            (self):                       return self.LoadParam(2)   #                        = 1000h - 1FFFh
   def LoadParam_App             (self):                       return self.LoadParam(3)   #                        = 6000h - 6FFFh
   def LoadParam_2000            (self):                       return self.LoadParam(5)   #                        = 2000h - 2FFFh
   def LoadParam_3000            (self):                       return self.LoadParam(6)   #                        = 3000h - 3FFFh

   def TimeStampCobId (self, cob_id=None):
      if cob_id is not None:
         self.Sdo(0x1012, 0, cob_id & ~0xC0000000)             # TimeStamp - Disable
         self.Sdo(0x1012, 0, cob_id)                           #
      else:
         return self.Sdo(0x1012, 0, cob_id)

   def EmcyCobId (self, cob_id=None):
      if cob_id is not None:
         self.Sdo(0x1014, 0, cob_id |  0x80000000)             # EMCY - Disable
         self.Sdo(0x1014, 0, cob_id & ~0x80000000)             # EMCY - Enable
      else:
         return self.Sdo(0x1014, 0, cob_id)

   def Identity                  (self, subindex):             return self.SdoRd(0x1018, subindex)
   def Identity_VendorId         (self):                       return self.Identity(1)
   def Identity_ProductCode      (self):                       return self.Identity(2)
   def Identity_RevisionNumber   (self):                       return self.Identity(3)
   def Identity_SerialNumber     (self):                       return self.Identity(4)

   def ServerSdoParam            (self, subindex):             return self.SdoRd(0x1200, subindex)
   def ServerSdoParam_c2s_CobId  (self):                       return self.ServerSdoParam(1)         # Client To Server CobId
   def ServerSdoParam_s2c_CobId  (self):                       return self.ServerSdoParam(2)         # Server To Client CobId

   def ErrorBehaviour            (self, subindex, value=None): return self.Sdo (0x1029, subindex, value)

   def _sdo_cob_id_ (self, sdo_nr, subindex, cob_id=None, ext=False, disable=False):
      index = 0x1200 + sdo_nr-1

      if cob_id==None:
         return self.SdoRd(index, subindex)
      else:
         cob_id &= ~0xC0000000

         if ext:     cob_id |= 0x20000000
         if disable: cob_id |= 0x80000000

         if not disable:
            self.SdoWr(index, subindex, cob_id | 0x80000000)

         self.SdoWr(index, subindex, cob_id)

   def Sdo_RxCobId (self, sdo_nr, cob_id=None, ext=False, disable=False):
      return self._sdo_cob_id_(sdo_nr, 1, cob_id, ext)

   def Sdo_TxCobId (self, sdo_nr, cob_id=None, ext=False, disable=False):
      return self._sdo_cob_id_(sdo_nr, 2, cob_id, ext)

   def Sdo_CobId (self, sdo_nr, tx_cob_id=None, rx_cob_id=None, ext=False, disable=False):
      if rx_cob_id==None and rx_cob_id==None:
         return self.Sdo_RxCobId(sdo_nr), self.Sdo_TxCobId(sdo_nr)
      else:
         self.Sdo_RxCobId(sdo_nr, rx_cob_id, ext, disable)
         self.Sdo_TxCobId(sdo_nr, tx_cob_id, ext, disable)

   def UseSdo (self, sdo_nr, tx_cob_id=None, rx_cob_id=None, ext=False):
      if sdo_nr == 0:
         self.Sdo_BaseCobId(tx_cob_id=0xFFFFFFFF, rx_cob_id=0xFFFFFFFF)    # Standard
      else:
         if tx_cob_id == None:
            tx_cob_id = self.Sdo_RxCobId(sdo_nr) - self.NodeId             # read rx_cob_id from slave
         else:
            self.Sdo_RxCobId(sdo_nr, tx_cob_id+self.NodeId, ext)

         if rx_cob_id == None:
            rx_cob_id = self.Sdo_TxCobId(sdo_nr) - self.NodeId             # read tx_cob_id from slave
         else:
            self.Sdo_TxCobId(sdo_nr, rx_cob_id+self.NodeId, ext)

         if (tx_cob_id & 0x80000000) or (rx_cob_id & 0x80000000):
            pass
         else:
            self.Sdo_BaseCobId(tx_cob_id, rx_cob_id, ext)                  # switch master to new SDO

   # Parameters and Mapping of PDO's ----------------------------------------------------------------------------------------------
   #
   # pdo_nr - nummer of PDO = [1..7, 21]
   #
   # Mappinglist (mapp_list):
   #
   # A list of all mapped objects is in the form:
   #  [[index0, subindex0, bits0], [index1, subindex1, bits1], ... , [indexN, subindexN, bitsN]]
   #
   def PdoMapping (self, pdo_nr, index_base, mapp_list=None):

      index = index_base+(pdo_nr-1)

      if mapp_list == None:
         n_of_elements = self.SdoRd(index, 0)
         ret_list      = []
         mapp          = [0,0,0]

         for i in range(1,n_of_elements+1):
            mapp_entry = self.SdoRd(index, i)
            mapp[0] = (mapp_entry >> 16) & 0xFFFF
            mapp[1] = (mapp_entry >> 8 ) & 0xFF
            mapp[2] = (mapp_entry & 0xFF)

            ret_list.append(list(mapp))

         return ret_list
      else:
         #
         # ToDo dP: check the data type of mapp_list
         #
         n_of_elements = 0;

         self.SdoWr(index, 0, 0)                            #  Mapping Disable

         try:
            for mapp in mapp_list:
               mapp_entry    = ((mapp[0] & 0xFFFF)<<16) | ((mapp[1] & 0xFF)<<8) | (mapp[2] & 0xFF)
               self.SdoWr(index, n_of_elements+1, mapp_entry)
               n_of_elements = n_of_elements+1
         finally:
            self.SdoWr(index, 0, n_of_elements)             #  Mapping Enable

   def RxPdo_Param (self, pdo_nr, subindex, value=None):
      return self.Sdo(0x1400+(pdo_nr-1), subindex, value)

   def RxPdo_CobId (self, pdo_nr, cob_id=None, rtr=False, ext=False):
      if cob_id is not None:
         cob_id &= ~0xC0000000

         if not rtr:
            cob_id = cob_id | 0x40000000
         if ext:
            cob_id = cob_id | 0x20000000

         self.RxPdo_Param(pdo_nr, 1, cob_id |  0x80000000)  # PDO - Disable
         self.RxPdo_Param(pdo_nr, 1, cob_id & ~0x80000000)  # PDO - Enable
      else:
         return self.RxPdo_Param(pdo_nr, 1, cob_id)

   def RxPdo_TransmissionType  (self, pdo_nr, tx_type=None):
      return self.RxPdo_Param(pdo_nr, 2, tx_type)

   def RxPdo_InhibitTime (self, pdo_nr, t_ms=None):         # for RxPdo its ignored
      if t_ms == None:
         return self.RxPdo_Param(pdo_nr, 3)/10
      else:
         self.RxPdo_Param(pdo_nr, 3, t_ms*10)

   def RxPdo_Mapping (self, pdo_nr, mapp_list=None):
      return self.PdoMapping (pdo_nr, 0x1600, mapp_list)


   def TxPdo_Param (self, pdo_nr, subindex, value=None):
      return self.Sdo(0x1800+(pdo_nr-1), subindex, value)

   def TxPdo_CobId (self, pdo_nr, cob_id=None, rtr=True, ext=False):
      if cob_id is not None:
         cob_id &= ~0xC0000000

         if not rtr: cob_id = cob_id | 0x40000000
         if ext:     cob_id = cob_id | 0x20000000

         self.TxPdo_Param(pdo_nr, 1, cob_id |  0x80000000)   # PDO - Disable
         self.TxPdo_Param(pdo_nr, 1, cob_id & ~0x80000000)   # PDO - Enable
      else:
         return self.TxPdo_Param(pdo_nr, 1, cob_id)

   def TxPdo_TransmissionType (self, pdo_nr, tx_type=None):
      return self.TxPdo_Param(pdo_nr, 2, tx_type)

   def TxPdo_InhibitTime (self, pdo_nr, t_ms=None):
      if t_ms == None:
         return self.TxPdo_Param(pdo_nr, 3)/10
      else:
         self.TxPdo_Param(pdo_nr, 3, t_ms*10)

   def TxPdo_Mapping (self, pdo_nr, mapp_list=None):
      return self.PdoMapping (pdo_nr, 0x1A00, mapp_list)


   # miControl specific objects - (Range: 2000h-2FFFh) ----------------------------------------------------------------------------
   #
   def __par_pass_wren_wait (self, index, subindex, value=None):     # helper function
      if value == None:
         return self.SdoRd(index, subindex)
      else:
         self.SdoWr(index, 1, 0x6E657277)                            # password: MSB..LSB == "nerw"   write enable
         self.SdoWr(index, subindex, value, timeout=500)

   def UserNodeId (self, node_id=None):                              # node_id = [-1..127]-{0}
      return self.__par_pass_wren_wait(0x2000, 2, node_id)

   def UserBaudrate (self, baudrate_kbaud=None):
      if baudrate_kbaud == None:
         baudrate = [1000,800,500,250,125,100,50,20,10]
         bcode = self.SdoRd(0x2000, 3)

         if (bcode >= 0) and (bcode < len(baudrate)):
            return baudrate[bcode]
         else:
            return bcode
      else:
         bcode = baudrate_kbaud

         if baudrate_kbaud >= 10:
            if   baudrate_kbaud == 1000: bcode = 0             # CAN_BAUDRATE_1M
            elif baudrate_kbaud ==  800: bcode = 1             # CAN_BAUDRATE_800k
            elif baudrate_kbaud ==  500: bcode = 2             # CAN_BAUDRATE_500k
            elif baudrate_kbaud ==  250: bcode = 3             # CAN_BAUDRATE_250k
            elif baudrate_kbaud ==  125: bcode = 4             # CAN_BAUDRATE_125k
            elif baudrate_kbaud ==  100: bcode = 5             # CAN_BAUDRATE_100k
            elif baudrate_kbaud ==   50: bcode = 6             # CAN_BAUDRATE_50k
            elif baudrate_kbaud ==   20: bcode = 7             # CAN_BAUDRATE_20k
            elif baudrate_kbaud ==   10: bcode = 8             # CAN_BAUDRATE_10k

         self.SdoWr(0x2000, 1, 0x6E657277)                     # password: MSB..LSB == "nerw"   write enable
         self.SdoWr(0x2000, 3, bcode, timeout=500)

   def AutoOperational (self, delay_ms=None):                  # after delay_ms go self in operational state
      return self.__par_pass_wren_wait(0x2000, 4, delay_ms)

   def MsgOnBootup (self, bit_mask=None):                      # bit0==1 send the GUARD object on Boot-Up (default: bit0=1 - yes)
      return self.__par_pass_wren_wait(0x2000, 5, bit_mask)    # bit1==1 send the EMCY  object on Boot-Up (default: bit1=0 - no )


   def IsEnabledDs402 (self):    return     self.SdoRd(0x2002, 2)
   def IsDisabledDs402(self):    return not self.SdoRd(0x2002, 2)
   def EnableDs402    (self):    self.__par_pass_wren_wait(0x2002, 2, 1)
   def DisableDs402   (self):    self.__par_pass_wren_wait(0x2002, 2, 0)

   def CmdCpuReset (self, delay_ms=100):                       # >= cop1.69.00.26
      self.SdoWr (0x2009, 3, delay_ms  )                       #
      self.SdoWr (0x2009, 1, 0x6E657277)                       # password: MSB..LSB == "nerw"   write enable
      try:
         self.SdoWr (0x2009, 2, 0x9999, timeout=50)            # Command: CPU-Reset
      except:
         pass

   #- obsolete -
   def CobIdSyncMsg                 (self, cob_id=None):          return self.SyncMsgCobId  (cob_id)
   def CobIdTimeStamp               (self, cob_id=None):          return self.TimeStampCobId(cob_id)
   def CobIdEmcy                    (self, cob_id=None):          return self.EmcyCobId     (cob_id)

   def MappingPdo                   (self, pdo_nr, index_base, mapp_list=None):           return self.PdoMapping              (pdo_nr, index_base, mapp_list)

   def ParamRxPdo                   (self, pdo_nr, subindex, value=None):                 return self.RxPdo_Param             (pdo_nr, subindex, value)
   def ParamRxPdo_CobId             (self, pdo_nr, cob_id=None, rtr=False, ext=False):    return self.RxPdo_CobId             (pdo_nr, cob_id, rtr, ext)
   def ParamRxPdo_TransmissionType  (self, pdo_nr, tx_type=None):                         return self.RxPdo_TransmissionType  (pdo_nr, tx_type)
   def ParamRxPdo_InhibitTime       (self, pdo_nr, t_ms=None):                            return self.RxPdo_InhibitTime       (pdo_nr, t_ms)
   def MappingRxPdo                 (self, pdo_nr, mapp_list=None):                       return self.RxPdo_Mapping           (pdo_nr, mapp_list)

   def ParamTxPdo                   (self, pdo_nr, subindex, value=None):                 return self.TxPdo_Param             (pdo_nr, subindex, value)
   def ParamTxPdo_CobId             (self, pdo_nr, cob_id=None, rtr=True, ext=False):     return self.TxPdo_CobId             (pdo_nr, cob_id, rtr, ext)
   def ParamTxPdo_TransmissionType  (self, pdo_nr, tx_type=None):                         return self.TxPdo_TransmissionType  (pdo_nr, tx_type)
   def ParamTxPdo_InhibitTime       (self, pdo_nr, t_ms=None):                            return self.TxPdo_InhibitTime       (pdo_nr, t_ms)
   def MappingTxPdo                 (self, pdo_nr, mapp_list=None):                       return self.TxPdo_Mapping           (pdo_nr, mapp_list)

   def RxPdoParam                   (self, pdo_nr, subindex, value=None):                 return self.RxPdo_Param             (pdo_nr, subindex, value)
   def TxPdoParam                   (self, pdo_nr, subindex, value=None):                 return self.TxPdo_Param             (pdo_nr, subindex, value)

# for compatibility reason
ds301 = Ds301

# TEST ----------------------------------------------------------------------------------------------------------------------------
#
def test ():
   from .common import Msg

   Msg.Print("\n=== Test start...")

   #m = Ds301(1,0xFFFF)       # Print-interface
   m = Ds301(1,1)

   Msg.Print("DeviceType                      = %s\n"    % hex(m.DeviceType()))

   Msg.Print("ErrorReg                        = %d\n"    % m.ErrorReg())
   Msg.Print("ManufStatusReg                  = %04X\n"  % m.ManufStatusReg())
   Msg.Print("ErrorField                      = %d\n"    % m.ErrorField(0))

   m.ErrorField(0,0)          # Clear ErrorList

   Msg.Print("SyncMsgCobId                    = %08X\n"  % m.SyncMsgCobId())

   Msg.Print("ManufDeviceName                 = %s\n"    % hex(m.ManufDeviceName()))
   Msg.Print("ManufHwVer                      = %s\n"    % hex(m.ManufHwVer()))
   Msg.Print("ManufSwVer                      = %s\n"    % hex(m.ManufSwVer()))

   Msg.Print("GuardTime                       = %d\n"    % m.GuardTime())
   Msg.Print("LifeTimeFactor                  = %d\n"    % m.LifeTimeFactor())

   Msg.Print("TimeStampCobId                  = %08X\n"  % m.TimeStampCobId())
   Msg.Print("EmcyCobId                       = %08X\n"  % m.EmcyCobId())

   try   :  Msg.Print("Identity_VendorId               = 0x%04X\n" % m.Identity_VendorId())
   except:  pass

   try   :  Msg.Print("Identity_ProductCode            = 0x%04X\n" % m.Identity_ProductCode())
   except:  pass

   try   :  Msg.Print("Identity_RevisionNumber         = 0x%04X\n" % m.Identity_RevisionNumber())
   except:  pass

   try   :  Msg.Print("Identity_SerialNumber           = 0x%04X\n" % m.Identity_SerialNumber())
   except:  pass

   Msg.Print("ServerSdoParam_c2s_CobId        = %s" % hex(m.ServerSdoParam_c2s_CobId()))
   Msg.Print("ServerSdoParam_s2c_CobId        = %s" % hex(m.ServerSdoParam_s2c_CobId()))

   for i in range(0,4):
      try   :  Msg.Print("ErrorBehaviour(%d)               = %d\n" % (i, m.ErrorBehaviour(i)))
      except:  pass

   pdos = [1,2,3,4,5,6,7,21]

   for p in pdos:
      try   :  Msg.Print("ParamRxPdo_CobId(%d)             = 0x%04X\n" % (p, m.ParamRxPdo_CobId(p)))
      except:  pass

   for p in pdos:
      try   :  Msg.Print("ParamRxPdo_TransmissionType(%d)  = %d\n"     % (p, m.ParamRxPdo_TransmissionType(p)))
      except:  pass

   for p in pdos:
      try   :  Msg.Print("MappingRxPdo(%d)                 = %s\n"     % (p, str(m.MappingRxPdo(p))))
      except:  pass

   for p in pdos:
      try   :  Msg.Print("ParamTxPdo_CobId(%d)             = 0x%04X\n" % (p, m.ParamTxPdo_CobId(p)))
      except:  pass

   for p in pdos:
      try   :  Msg.Print("ParamTxPdo_TransmissionType(%d)  = %d\n"     % (p, m.ParamTxPdo_TransmissionType(p)))
      except:  pass

   for p in pdos:
      try   :  Msg.Print("MappingTxPdo(%d)                 = %s\n"     % (p, str(m.MappingTxPdo(p))))
      except:  pass

   Msg.Print("\n=== Test end.")

#==================================================================================================================================
if __name__ == '__main__':
   test()
