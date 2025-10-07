# -*- coding: utf-8 -*-
#=================================================================================================================================#
#                                                                      Copyright (c) 1997-2020 by miControl. All rights reserved. #
# File     : ds401.py                                                                                                             #
#                                                                                                                                 #
# Project  :                                                                                                                      #
# System   : Python                                                                                                               #
# Version  : (see self.ClassVersion)                                                                                              #
# Customer :                                                                                                                      #
# Company  : miControl                                                                                                            #
#                                                                                                                                 #
# Author   : miControl Development Team                                                                                           #
# Team     : dariusz Parma (dP)  mailto:dp@miControl.de                                                                           #
# Date     : 16.01.2004                                                                                                           #
#=================================================================================================================================#
# Brief:    Ds401 class for CANopen miControl I/O-Devices
#
#----------------------------------------------------------------------------------------------------------------------------------
# History:                                                  (Symbol legend: + Added, - Removed, ~ Changed, ! Correction, # Comment)
#
#==================================================================================================================================
if __package__:
   from .base        import Can
   from .ds301       import Ds301
   from .cop_cobid   import COBID_DIN, COBID_DOUT, COBID_AIN, COBID_AOUT
else:
   from base         import Can
   from ds301        import Ds301
   from cop_cobid    import COBID_DIN, COBID_DOUT, COBID_AIN, COBID_AOUT

__all__ = ["Ds401","ds401"]

#==================================================================================================================================
class Ds401(Ds301):

   ClassVersion = (1,0x01, 0x01,0x00)

   # Variables --------------------------------------------------------------------------------------------------------------------

   # Constructor/Destructor -------------------------------------------------------------------------------------------------------
   #
   def __init__(self, node_id, interface):
      Ds301.__init__(self, node_id, interface)
      self.PdoModeFlag    = 0
      self.StartFlag      = 0
      self.DoutInitFlag   = 0
      self.DoutBytesCount = 0
      self.DoutState      = []

   def __del__(self):
      Ds301.__del__(self)

   # Control functions ------------------------------------------------------------------------------------------------------------
   #
   def _start (self):
      self.StartNode()
      self.StartFlag = 1

   def _dout_init (self):
      self.DoutBytesCount = self.SdoRd(0x6200, 0) & 0xFF
      self.DoutState      = []

      for i in range(1, self.DoutBytesCount+1):
         self.DoutState.append(self.SdoRd(0x6200, i))

      self.DoutInitFlag = 1


   def EnablePdoMode (self, en=1):
      self.PdoModeFlag = en

      if self.PdoModeFlag:
         self._start()
         self._dout_init()

   # DS401 Objects ----------------------------------------------------------------------------------------------------------------

   # Digital Inputs (Din)
   #
   def Din (self, nr):                                   # Read dig. Input 8-Bit
      if self.PdoModeFlag:
         dat = Can.PdoRd(COBID_DIN+self.NodeId)
         return dat[nr]
      else:
         return self.SdoRd(0x6000, nr+1)

   def DinPolarity         (self, nr, value=None):    return self.Sdo(0x6002, nr+1, value)   # Polarity of dig. Input 8-Bit
   def DinEnableInt        (self, value=None):        return self.Sdo(0x6005, 0,    value)   # Interrupt enable
   def DinIntMaskAny       (self, nr, value=None):    return self.Sdo(0x6006, nr+1, value)   # Interrupt on any  change
   def DinIntMaskL2H       (self, nr, value=None):    return self.Sdo(0x6007, nr+1, value)   # Interrupt on L->H change
   def DinIntMaskH2L       (self, nr, value=None):    return self.Sdo(0x6008, nr+1, value)   # Interrupt on H->L change

   def DinBit              (self, nr):                return self.Sdo(0x6020, nr+1)
   def DinBitPolarity      (self, nr, value=None):    return self.Sdo(0x6030, nr+1, value)
   def DinBitIntMaskAny    (self, nr, value=None):    return self.Sdo(0x6050, nr+1, value)   # Interrupt on any  change
   def DinBitIntMaskL2H    (self, nr, value=None):    return self.Sdo(0x6060, nr+1, value)   # Interrupt on L->H change
   def DinBitIntMaskH2L    (self, nr, value=None):    return self.Sdo(0x6070, nr+1, value)   # Interrupt on H->L change

   def DinWord             (self, nr):                return self.Sdo(0x6100, nr+1)
   def DinWordPolarity     (self, nr, value=None):    return self.Sdo(0x6102, nr+1, value)
   def DinWordIntMaskAny   (self, nr, value=None):    return self.Sdo(0x6106, nr+1, value)   # Interrupt on any  change
   def DinWordIntMaskL2H   (self, nr, value=None):    return self.Sdo(0x6107, nr+1, value)   # Interrupt on L->H change
   def DinWordIntMaskH2L   (self, nr, value=None):    return self.Sdo(0x6108, nr+1, value)   # Interrupt on H->L change

   # Digital Outputs (Dout)
   #
   def Dout (self, nr, value=None):                      # Write/Read dig. Output 8-Bit
      if self.PdoModeFlag and (not (value == None)):
         if not self.DoutInitFlag:
            self._dout_init()

         self.DoutState[nr] = value

         Can.PdoWr(COBID_DOUT+self.NodeId, self.DoutState)
      else:
         return self.Sdo(0x6200, nr+1, value)

   def DoutPolarity        (self, nr, value=None):    return self.Sdo(0x6202, nr+1, value)
   def DoutErrorMode       (self, nr, value=None):    return self.Sdo(0x6206, nr+1, value)
   def DoutErrorState      (self, nr, value=None):    return self.Sdo(0x6207, nr+1, value)
   def DoutFilterMask      (self, nr, value=None):    return self.Sdo(0x6208, nr+1, value)

   def DoutBit (self, nr, value=None):
      if self.PdoModeFlag and (not (value == None)):
         if not self.DoutInitFlag:
            self._dout_init()

         byte_nr = nr / 8
         bit_nr  = nr % 8

         if value:
            self.DoutState[byte_nr] = self.DoutState[byte_nr] |  (1<<bit_nr)
         else:
            self.DoutState[byte_nr] = self.DoutState[byte_nr] & ~(1<<bit_nr)

         Can.PdoWr(COBID_DOUT+self.NodeId, self.DoutState)
      else:
         return self.Sdo(0x6220, nr+1, value)

   def DoutBitPolarity     (self, nr, value=None):    return self.Sdo(0x6240, nr+1, value)
   def DoutBitErrorMode    (self, nr, value=None):    return self.Sdo(0x6250, nr+1, value)
   def DoutBitErrorState   (self, nr, value=None):    return self.Sdo(0x6260, nr+1, value)
   def DoutBitFilterMask   (self, nr, value=None):    return self.Sdo(0x6270, nr+1, value)

   def DoutWord (self, nr, value=None):
      if self.PdoModeFlag and (not (value == None)):
         if not self.DoutInitFlag:
            self._dout_init()

         self.DoutState[nr*2  ] =  value     & 0xFF
         self.DoutState[nr*2+1] = (value>>8) & 0xFF

         Can.PdoWr(COBID_DOUT+self.NodeId, self.DoutState)
      else:
         return self.Sdo(0x6300, nr+1, value)

   def DoutWordPolarity    (self, nr, value=None):    return self.Sdo(0x6302, nr+1, value)
   def DoutWordErrorMode   (self, nr, value=None):    return self.Sdo(0x6306, nr+1, value)
   def DoutWordErrorState  (self, nr, value=None):    return self.Sdo(0x6307, nr+1, value)
   def DoutWordFilterMask  (self, nr, value=None):    return self.Sdo(0x6308, nr+1, value)

   # Analog Inputs (Ain)
   #
   def Ain                 (self, nr):                return self.SdoRd(0x6401, nr+1)        # Read Analogue Input 16-Bit

   # Analog Outputs (Aout)
   #
   def Aout                (self, nr, value=None):    return self.Sdo(0x6411, nr+1, value)   # Write Analogue Output 16-Bit

# for compatibility reason
ds401 = Ds401

# TEST ----------------------------------------------------------------------------------------------------------------------------
#
def test ():
   import time
   from .common import Msg

   print("\n=== Test start...")

   #m = Ds401(1,0xFFFF)       # print-interface
   m = Ds401(1,1)

   Msg.Print("Din(0)                = 0x%02X\n" %  m.Din(0)                )
   Msg.Print("DinPolarity(0)        = 0x%02X\n" %  m.DinPolarity(0)        )
   Msg.Print("DinEnableInt()        = 0x%02X\n" %  m.DinEnableInt()        )
   Msg.Print("DinIntMaskAny(0)      = 0x%02X\n" %  m.DinIntMaskAny(0)      )
   Msg.Print("DinIntMaskL2H(0)      = 0x%02X\n" %  m.DinIntMaskL2H(0)      )
   Msg.Print("DinIntMaskH2L(0)      = 0x%02X\n" %  m.DinIntMaskH2L(0)      )

   Msg.Print("DinBit(0)             = 0x%02X\n" %  m.DinBit(0)             )
   Msg.Print("DinBitPolarity(0)     = 0x%02X\n" %  m.DinBitPolarity(0)     )
   Msg.Print("DinBitIntMaskAny(0)   = 0x%02X\n" %  m.DinBitIntMaskAny(0)   )
   Msg.Print("DinBitIntMaskL2H(0)   = 0x%02X\n" %  m.DinBitIntMaskL2H(0)   )
   Msg.Print("DinBitIntMaskH2L(0)   = 0x%02X\n" %  m.DinBitIntMaskH2L(0)   )

   #Msg.Print("DinWord(0)            = 0x%02X\n" %  m.DinWord(0)            )
   #Msg.Print("DinWordPolarity(0)    = 0x%02X\n" %  m.DinWordPolarity(0)    )
   #Msg.Print("DinWordIntMaskAny(0)  = 0x%02X\n" %  m.DinWordIntMaskAny(0)  )
   #Msg.Print("DinWordIntMaskL2H(0)  = 0x%02X\n" %  m.DinWordIntMaskL2H(0)  )
   #Msg.Print("DinWordIntMaskH2L(0)  = 0x%02X\n" %  m.DinWordIntMaskH2L(0)  )

   Msg.Print("Dout(0)               = 0x%02X\n" %  m.Dout(0)               )
   Msg.Print("DoutPolarity(0)       = 0x%02X\n" %  m.DoutPolarity(0)       )
   Msg.Print("DoutErrorMode(0)      = 0x%02X\n" %  m.DoutErrorMode(0)      )
   Msg.Print("DoutErrorState(0)     = 0x%02X\n" %  m.DoutErrorState(0)     )
   Msg.Print("DoutFilterMask(0)     = 0x%02X\n" %  m.DoutFilterMask(0)     )

   Msg.Print("DoutBit(0)            = 0x%02X\n" %  m.DoutBit(0)            )
   Msg.Print("DoutBitPolarity(0)    = 0x%02X\n" %  m.DoutBitPolarity(0)    )
   Msg.Print("DoutBitErrorMode(0)   = 0x%02X\n" %  m.DoutBitErrorMode(0)   )
   Msg.Print("DoutBitErrorState(0)  = 0x%02X\n" %  m.DoutBitErrorState(0)  )
   Msg.Print("DoutBitFilterMask(0)  = 0x%02X\n" %  m.DoutBitFilterMask(0)  )

   #Msg.Print("DoutWord(0)           = 0x%02X\n" %  m.DoutWord(0)           )
   #Msg.Print("DoutWordPolarity(0)   = 0x%02X\n" %  m.DoutWordPolarity(0)   )
   #Msg.Print("DoutWordErrorMode(0)  = 0x%02X\n" %  m.DoutWordErrorMode(0)  )
   #Msg.Print("DoutWordErrorState(0) = 0x%02X\n" %  m.DoutWordErrorState(0) )
   #Msg.Print("DoutWordFilterMask(0) = 0x%02X\n" %  m.DoutWordFilterMask(0) )

   #Msg.Print("Ain(0)                = 0x%04X\n" %  m.Ain(0)                )
   #Msg.Print("Aout(0)               = 0x%04X\n" %  m.Aout(0)               )


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
