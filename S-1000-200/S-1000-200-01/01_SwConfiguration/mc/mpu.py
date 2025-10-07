# -*- coding: utf-8 -*-
#=================================================================================================================================#
#                                                                      Copyright (c) 1997-2020 by miControl. All rights reserved. #
# File     : mpu.py                                                                                                               #
#                                                                                                                                 #
# Project  :                                                                                                                      #
# System   : Python                                                                                                               #
# Version  : (see ClassVersion)                                                                                                   #
# Customer :                                                                                                                      #
# Company  : miControl                                                                                                            #
#                                                                                                                                 #
# Author   : miControl Development Team                                                                                           #
# Team     : dariusz Parma (dP)  mailto:dp@miControl.de                                                                           #
# Date     : 22.01.2004                                                                                                           #
#=================================================================================================================================#
# Brief:    Mpu class for miControl Devices
#*          MPU - Motion Process Unit
#
#----------------------------------------------------------------------------------------------------------------------------------
# History:                                                  (Symbol legend: + Added, - Removed, ~ Changed, ! Correction, # Comment)
#  11.05.2004 dP: +MpufSet, MpufGet, BoostReload, Boost
#  26.11.2004 dP: +MpuState (V1.05.00.00)
#  08.04.2005 dP: +Prg      (V1.06.00.00)
#  09.07.2007 dP: +Vars     (V1.07.00.00)
#
#==================================================================================================================================
if __package__:
   from .common      import Msg
   from .i18n        import _
   from .mpu_extd    import *
   from .mpu_asm     import *
   from .mpu_state   import *
   from .mpu_vars    import *
   from .display     import *
else:
   from common       import Msg
   from i18n         import _
   from mpu_extd     import *
   from mpu_asm      import *
   from mpu_state    import *
   from mpu_vars     import *
   from display      import *


__all__ = ["Mpu","mpu","Reg0","Reg1","Reg2","Reg3","Reg4","Reg5","Reg6","Reg7","Accu"]

Reg0 = [0x5050, 0]      # Registers
Reg1 = [0x5050, 1]
Reg2 = [0x5050, 2]
Reg3 = [0x5050, 3]
Reg4 = [0x5050, 4]
Reg5 = [0x5050, 5]
Reg6 = [0x5050, 6]
Reg7 = [0x5050, 7]

Accu = Reg0             # Accumulator (= Reg0)

#==================================================================================================================================
class Mpu (MpuExtd, MpuState):

   # Var's ------------------------------------------------------------------------------------------------------------------------
   #
   ClassVersion = (1,0x07, 0x00,0x00)

   def __init__(self, d=None):
      MpuExtd.__init__(self, d)
      MpuState.__init__(self)

      self.Disp = self.__disp(d, self)
      self.Prg  = self.__prg (d, self)

   # Functions from MpuAsm --------------------------------------------------------------------------------------------------------
   #
   # Label        (name, addr=None)
   # GetLabelAddr (name)
   # DumpPrg      (self)

   #-Asm Functions-----------------------------------------------------------------------------------------------------------------
   #
   def End        (self):              return self.asm (self.END)                      # End of a programm
   def Nop        (self):              return self.asm (self.NOP)                      # No operation
   def Exit       (self):              return self.asm (self.EXIT)                     # Terminate a programm
   def MpufSet    (self, fnr, arg1):   return self.asm (self.MPUF_SET, fnr,  arg1)     # MPU-Function    func(arg1)
   def MpufGet    (self, fnr, arg0):   return self.asm (self.MPUF_GET, arg0, fnr)      # MPU-Function    arg0 = func()

   def Mov        (self, arg0,arg1) :  return self.asm (self.MOV      , arg0, arg1)    # arg0 = arg1

   def And        (self, arg0,arg1) :  return self.asm (self.AND      , arg0, arg1)    # Accu = arg0 & arg1
   def Or         (self, arg0,arg1) :  return self.asm (self.OR       , arg0, arg1)    # Accu = arg0 | arg1
   def Xor        (self, arg0,arg1) :  return self.asm (self.XOR      , arg0, arg1)    # Accu = arg0 ^ arg1
   def Shl        (self, arg0,arg1) :  return self.asm (self.SHL      , arg0, arg1)    # Accu = arg0 << arg1
   def Shr        (self, arg0,arg1) :  return self.asm (self.SHR      , arg0, arg1)    # Accu = arg0 >> arg1
   def Inv        (self, arg0,arg1) :  return self.asm (self.INV      , arg0, arg1)    # arg0 = ~arg1
   def Not        (self, arg0,arg1) :  return self.asm (self.NOT      , arg0, arg1)    # arg0 = !arg1
   def Clrb       (self, arg0,arg1) :  return self.asm (self.CLRB     , arg0, arg1)    # Accu = arg0 & (~arg1)       ab Firmware 1.64.00.23

   def Add        (self, arg0,arg1) :  return self.asm (self.ADD      , arg0, arg1)    # Accu = arg0 + arg1
   def Sub        (self, arg0,arg1) :  return self.asm (self.SUB      , arg0, arg1)    # Accu = arg0 - arg1
   def Mul        (self, arg0,arg1) :  return self.asm (self.MUL      , arg0, arg1)    # Accu = arg0 * arg1
   def Div        (self, arg0,arg1) :  return self.asm (self.DIV      , arg0, arg1)    # Accu = arg0 / arg1
   def Mod        (self, arg0,arg1) :  return self.asm (self.MOD      , arg0, arg1)    # Accu = arg0 % arg1

   def Scale      (self, arg0,arg1) :  return self.asm (self.SCALE    , arg0, arg1)    # Accu = (float) Accu * ((float) arg0 / (float) arg1)
   def ScaleDbl   (self, arg0,arg1) :  return self.asm (self.SCALE_D  , arg0, arg1)    # Accu = (double)Accu * ((double)arg0 / (double)arg1)

   def Neg        (self, arg0,arg1) :  return self.asm (self.NEG      , arg0, arg1)    # arg0 = -arg1                ab Firmware 1.64.00.23

   def Jmp        (self, addr)      :  return self.asmj(self.JMP      , addr, 0   )    # PC = addr
   def Jeq        (self, addr,arg1) :  return self.asmj(self.JEQ      , addr, arg1)    # if (Accu == arg1)  PC = addr
   def Jneq       (self, addr,arg1) :  return self.asmj(self.JNEQ     , addr, arg1)    # if (Accu != arg1)  PC = addr
   def Jg         (self, addr,arg1) :  return self.asmj(self.JG       , addr, arg1)    # if (Accu >  arg1)  PC = addr
   def Jge        (self, addr,arg1) :  return self.asmj(self.JGE      , addr, arg1)    # if (Accu >= arg1)  PC = addr
   def Jl         (self, addr,arg1) :  return self.asmj(self.JL       , addr, arg1)    # if (Accu <  arg1)  PC = addr
   def Jle        (self, addr,arg1) :  return self.asmj(self.JLE      , addr, arg1)    # if (Accu <= arg1)  PC = addr

   def Delay      (self, time_ms)   :  return self.asm (self.DELAY    , time_ms)       # wait for time_ms
   def Clock      (self, arg0)      :  return self.asm (self.CLOCK    , arg0, 0)       # arg0 = SystemClock()                 [ms]
   def DiffClock  (self, arg0, arg1):  return self.asm (self.DIFFCLOCK, arg0, arg1)    # arg0 = Diff(SystemClock() - arg1)    [ms]
   def Abs        (self, arg0, arg1):  return self.asm (self.ABS      , arg0, arg1)    # arg0 = Abs(arg1)            ab Firmware 1.64.00.23

   #-MPU Control Functions---------------------------------------------------------------------------------------------------------
   #
   def BoostReload      (self, val):   return self.MpufSet(self.MPUF_BOOST_RELOAD,      val)
   def BoostReloadWait  (self, val):   return self.MpufSet(self.MPUF_BOOST_RELOAD_WAIT, val)
   def Boost            (self, val):   return self.MpufSet(self.MPUF_BOOST_COUNTER,     val)

   #-derived Exec Functions--------------------------------------------------------------------------------------------------------
   #
   def Setb (self, arg0, bit_mask):    return self.Or (arg0,bit_mask)                  # Accu  = arg0 | bit_mask

   def VarX (self, node_id, index, subindex):
      return MpuVarX(None, node_id, index, subindex)

   #-Display-----------------------------------------------------------------------------------------------------------------------
   #
   class __disp(Display):

      def __init__(self, d, m):
         Display.__init__(self,d)
         self.m = m

      def ClearAll (self):
         self.m.Mov([0x860,0], (0x0002<<16))

      def ClearLine (self, line):
         self.m.Mov([0x860,0], (0x0002<<16) | (line & 0xFF))

      def SetCursorPos (self, column, line):
         self.m.Mov([0x860,0], (0x0003<<16) | ((column & 0xFF)<<8) | (line & 0xFF))

      def PrintText (self, column, line, txt):
         column &= 0xFF
         line   &= 0xFF
         txt_nr  = self.GetTextNr(txt=txt, append=True)
         self.m.Mov([0x0860,4], (column<<24) | (line<<16) | txt_nr)

   #-Prg Functions-----------------------------------------------------------------------------------------------------------------
   #
   class __prg:

      def __init__(self, d, m):
         self.Dev = d
         self.m   = m

      def Load (self):
         prglen     = self.m.MakePrg()
         prglen_max = self.Dev.Gp(0x5028)

         if prglen <= prglen_max:
            self.m.LoadPrg()
         else:
            raise MpuError("Insufficient memory for program. MaxPrgLen=%d PrgLen=%d" % (prglen_max, prglen))

         if self.Dev.VersionSw() > 0x01710100:
            self.m.Disp.StoreTexts()

      def Dump             (self):           self.m.DumpPrg()

      def ClearError       (self):           self.Dev.Sp(0x5000, 0, 1)

      def Start            (self):           self.Dev.Sp(0x5000, 0, 2)
      def Break            (self):           self.Dev.Sp(0x5000, 0, 3)
      def Continue         (self):           self.Dev.Sp(0x5000, 0, 4)

      def DbgStart         (self):           self.Dev.Sp(0x5000, 0,  0x11)
      def DbgStep          (self):           self.Dev.Sp(0x5000, 0,  0x12)
      def DbgContinue      (self):           self.Dev.Sp(0x5000, 0,  0x13)

      def AutoStart        (self,val=None):  return self.Dev.Par(0x5000,1,val)
      def EnableWrAccess   (self,val=None):  return self.Dev.Sp (0x5000,2,0x6E657277)
      def DisableWrAccess  (self,val=None):  return self.Dev.Sp (0x5000,2,0x73647277)

      def Store            (self):           self.Dev.Sp(0x5000,0, 0x80, timeout=2000)
      def Restore          (self):           self.Dev.Sp(0x5000,0, 0x81, timeout=500)
      def Default          (self):           self.Dev.Sp(0x5000,0, 0x82, timeout=500)
      def Clear            (self):           self.Dev.Sp(0x5000,0, 0x83, timeout=500)

      def GetError         (self,kind=0):    return self.Dev.Gp(0x5001,kind)
      def GetStatus        (self):           return self.Dev.Gp(0x5002,0)

      def GetPrgCount      (self):           return self.Dev.Gp(0x5040,0)

      def Exec (self, store=True, start=True):
         err = 0

         if store or start:
            if self.Dev.OutType == 0:
               Msg.Print(_("Execute MPU-program on device %s\n") % str(self.Dev.NodeId))
               Msg.Print(_("   Firmware version: %s\n") % self.Dev.VersionSwString())
            else:
               Msg.Print(_("MPU-program for device %s\n") % str(self.Dev.NodeId))

            self.Break()                        # MPU-Program break

            if self.Dev.OutType == 0:
               Msg.Print(_("   Loading..."))
            else:
               Msg.Print(_("   Writing to file \"%s\"...") % self.Dev.OutFilename)

            try:
               self.Load()                      # Load the MPU-Program in the device
               Msg.Print(_("OK\n"))
            except Exception as e:
               err = -1
               Msg.Print(_("Failed\n"))
               Msg.Print(_("\nERROR: %s\n") % str(e))

         if store and err==0:
            if self.Dev.OutType == 0:
               Msg.Print(_("   Storing..."))

            try:
               try:
                  self.Dev.Disable()            # StoreMpu works only in Disable state
               except:                          # (its only for DSA-Devices)
                  pass

               self.AutoStart(1)                # Set the AutoStart
               self.Store()                     # Store MPU-Program and MPU-Settings in EEPROM

               if self.Dev.OutType == 0:
                  Msg.Print(_("OK\n"))
            except Exception as e:
               err = -2
               if self.Dev.OutType == 0:
                  Msg.Print(_("Failed\n"))
                  Msg.Print(_("\nERROR: %s\n") % str(e))

         if start and err==0:
            if self.Dev.OutType == 0:
               Msg.Print(_("   Starting..."))

            self.Start()                        # Start loaded MPU-Program

            if self.Dev.OutType == 0:
               Msg.Print(_("OK\n"))

   #- obsolete functions (only for compatibility reason) --------------------------------------------------------------------------
   #
   def ClearError       (self):           self.Prg.ClearError     ()
   def Load             (self):           self.Prg.Load           ()
   def Start            (self):           self.Prg.Start          ()
   def Break            (self):           self.Prg.Break          ()
   def Continue         (self):           self.Prg.Continue       ()
   def DbgStart         (self):           self.Prg.DbgStart       ()
   def DbgStep          (self):           self.Prg.DbgStep        ()
   def DbgContinue      (self):           self.Prg.DbgContinue    ()
   def AutoStart        (self,val=None):  return self.Prg.AutoStart      (val)
   def EnableWrAccess   (self,val=None):  return self.Prg.EnableWrAccess (val)
   def DisableWrAccess  (self,val=None):  return self.Prg.DisableWrAccess(val)
   def StoreMpu         (self):           self.Prg.Store          ()
   def RestoreMpu       (self):           self.Prg.Restore        ()
   def DefaultMpu       (self):           self.Prg.Default        ()
   def ClearMpu         (self):           self.Prg.Clear          ()
   def GetError         (self,kind=0):    return self.Prg.GetError   (kind)
   def GetStatus        (self):           return self.Prg.GetStatus  ()
   def GetPrgCount      (self):           return self.Prg.GetPrgCount()

# for compatibility reason
mpu = Mpu

# TEST ----------------------------------------------------------------------------------------------------------------------------
#
if __name__ == '__main__':
   try:
      from .dsa import *
   except ImportError:
      from mc.dsa import *

def test():
   from .dsa import Dsa

   d = Dsa(1, 1)
   m = Mpu(d)

   d.ClearError()

   m.Prg.Break()              # Break the running MPU-Programm

   #- MPU Programm START --------------------------

   m.Mov  ([    4],     0)    # Disable
   m.Mov  ([    0],     1)    # ClearError
   m.Mov  ([0x900],     1)    # Motor BLDC
   m.Mov  ([0x350], 0x96A)    # Encoder
   m.Mov  ([    3],     3)    # Velocity controller
   m.Mov  ([0x300],  1000)    # 1000 rpm
   m.Mov  ([    4],     1)    # Enable

   m.Label("main_loop")

   m.Mov  ([0x150], 1)
   m.Delay(50)

   m.Mov  ([0x150], 0)
   m.Delay(2000)

   m.Mul  ([0x300], -1)       # Accu = VelDesiredValue * (-1)
   m.Mov  ([0x300], Accu)     # SollDrehzahl = Accu

   m.Jmp("main_loop")

   #- MPU Programm END ----------------------------

   m.Prg.Dump()

   #m.Prg.Load()              # Load the MPU program in device
   #m.Prg.Start()             # Start loaded MPU program

   #m.Prg.AutoStart(1)        # Set the AutoStart

   #d.Disable()               # StoreMpu works only in Disable state
   #m.Prg.Store()             # Store MPU-Programm and Settings in EEPROM

#=================================================================================================================================#
if __name__ == '__main__':
   test()
