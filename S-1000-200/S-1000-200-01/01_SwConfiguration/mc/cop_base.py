# -*- coding: utf-8 -*-
#=================================================================================================================================#
#                                                                      Copyright (c) 1997-2020 by miControl. All rights reserved. #
# File     : cop_base.py                                                                                                          #
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
# Brief: CopBase class for miControl CANopen Devices
#*       (CANopen - Basis communication functions)
#
#----------------------------------------------------------------------------------------------------------------------------------
# History:                                                  (Symbol legend: + Added, - Removed, ~ Changed, ! Correction, # Comment)
#  09.05.2004 dP: +Methoden forms with mux=[index,subindex]
#  29.11.2009 dP: ~SimPrintXxxx Methoden
#                 ~SimPrintXxxx Methoden
#                 ClassVersion=1.21.00.00
#  12.10.2010 dP: !_SimPrintGp,_SimPrintSdoRd
#  12.02.2011 dP: +Export
#
#==================================================================================================================================
import os

if __package__:
   from .base        import Can, Com
   from .dx_export   import DxExport
else:
   from base         import Can, Com
   from dx_export    import DxExport

__all__ = ["CopBase", "INTERFACE_miCan", "INTERFACE_COM", "INTERFACE_COM1",
           "INTERFACE_COM2", "INTERFACE_COM3", "INTERFACE_FILE", "INTERFACE_SIM"]

INTERFACE_miCan   = 1
INTERFACE_COM     = 100
INTERFACE_COM1    = 101
INTERFACE_COM2    = 102
INTERFACE_COM3    = 103
INTERFACE_COM10   = 110
INTERFACE_FILE    = 0xFFFE
INTERFACE_SIM     = 0xFFFF

#==================================================================================================================================
class ParError(Exception):
   pass

#==================================================================================================================================
class FileError(Exception):
    pass

#==================================================================================================================================
class CopBase:

   ClassVersion = (1,0x22, 0x00,0x00)

   # Constructor/Destructor -------------------------------------------------------------------------------------------------------
   #
   def __init__(self, node_id=1, interface=1):
      self.NodeId          = node_id
      self.Interface       = interface

      self.SdoTxCobId      = 0xFFFFFFFF
      self.SdoRxCobId      = 0xFFFFFFFF

      self.Export          = DxExport()

      self.SimPrintGp      = self.Export.SimPrintGp
      self.SimPrintSp      = self.Export.SimPrintSp
      self.SimPrintSdoRd   = self.Export.SimPrintSdoRd
      self.SimPrintSdoWr   = self.Export.SimPrintSdoWr

      self.Saved_sdo_rd    = None
      self.Saved_sdo_wr    = None

      self.OutFilename     = None
      self.OutType         = 0
      self.OutTxtFormat    = "0x%04X, 0x%02X, %d, %d\n"     # Index, Subindex, Value, Timeout
      self.OutFormat       = None                           # (format_string, format_arguments)

      self.sdo_rd          = self.__sdo_rd
      self.sdo_wr          = self.__sdo_wr

   def __del__(self):
      pass

   # NMT Services -----------------------------------------------------------------------------------------------------------------
   #
   def _GetNmtNodeId(self, node_id=None):
      if node_id is None:
         return self.NodeId
      else:
         return node_id

   def StartNode           (self, node_id=None):   Can.PdoWr(0, [  1, self._GetNmtNodeId(node_id)])
   def StopNode            (self, node_id=None):   Can.PdoWr(0, [  2, self._GetNmtNodeId(node_id)])
   def DisconnectNode      (self, node_id=None):   Can.PdoWr(0, [  3, self._GetNmtNodeId(node_id)])
   def EnterPreOperational (self, node_id=None):   Can.PdoWr(0, [128, self._GetNmtNodeId(node_id)])
   def ResetNode           (self, node_id=None):   Can.PdoWr(0, [129, self._GetNmtNodeId(node_id)])
   def ResetCommunication  (self, node_id=None):   Can.PdoWr(0, [130, self._GetNmtNodeId(node_id)])

   def StartAllNodes       (self):                 Can.PdoWr(0, [  1, 0])
   def StopAllNodes        (self):                 Can.PdoWr(0, [  2, 0])
   def ResetAllNodes       (self):                 Can.PdoWr(0, [129, 0])

   # Common Functions -------------------------------------------------------------------------------------------------------------

   def __sdo_rd (self, index, subindex, timeout):
      return Can.SdoRd(self.NodeId, index, subindex, timeout, self.SdoTxCobId, self.SdoRxCobId)

   def __sdo_wr (self, index, subindex, val, timeout):
      return Can.SdoWr(self.NodeId, index, subindex, val, timeout, self.SdoTxCobId, self.SdoRxCobId)

   def Sdo_BaseCobId (self, tx_cob_id=None, rx_cob_id=None, ext=False):
      if tx_cob_id is not None:
         if tx_cob_id != 0xFFFFFFFF:
            if ext:  tx_cob_id |= 0x20000000
            tx_cob_id &= ~0xC0000000
         self.SdoTxCobId = tx_cob_id

      if rx_cob_id is not None:
         if rx_cob_id != 0xFFFFFFFF:
            if ext:  rx_cob_id |= 0x20000000
            rx_cob_id &= ~0xC0000000
         self.SdoRxCobId = rx_cob_id

      if (tx_cob_id is None) and (rx_cob_id is None):
         return self.SdoTxCobId, self.SdoRxCobId

   # mux = [index,subindex]

   def GetMux (self, p1,p2=0):
      if (type(p1) is list):                                         # Form1: p1=[index,subindex]
         l1 = len(p1)
         if l1 == 1:
            return [p1[0],0]
         elif l1 >= 2:
            return [p1[0],p1[1]]
         else:
            raise ParError("Bad MUX-list length (MUX should be in form: [index] or [index,subindex])")
      else:                                                          # Form2: p1=index; p1=subindex
         return [p1,p2]

   def Gp (self, p1, p2=0, timeout=0xFFFF):                          # Form:  Gp(mux)
      mux      = self.GetMux(p1,p2)                                  #        Gp(index,subindex)
      index    = mux[0]
      subindex = mux[1]

      if (self.Interface == INTERFACE_miCan):                        # CAN Interface 1
         if index < 0x1000: index = 0x3000+index                     # bei CANopen sind DSA-Parameter im Bereich 0x3000-0x3FFF
         return self.sdo_rd(index, subindex, timeout)
      elif (self.Interface >= INTERFACE_COM) and (self.Interface <= INTERFACE_COM10):  # COM1-COM10 RS232 Interface
         return Com.Gp(self.Interface-INTERFACE_COM, index, subindex, timeout)
      elif (self.Interface == INTERFACE_SIM):                                          # for Tests und Simulation
         self.SimPrintGp(self.NodeId, index, subindex, timeout)
         return 0

   def Sp (self, p1, p2, p3=None, timeout=0xFFFF):
      if type(p1) is list:                                           # Form1: Sp(mux, val)
         mux      = self.GetMux(p1)
         index    = mux[0]
         subindex = mux[1]
         val      = p2
      elif p3 is None:                                               # Form2: Sp(index, val)          subindex==0
         index    = p1
         subindex = 0
         val      = p2
      else:                                                          # Form3: Sp(index, subindex, val)
         index    = p1
         subindex = p2
         val      = p3

      if (self.Interface == INTERFACE_miCan):                        # CAN Interface 1
         if index < 0x1000: index = 0x3000+index                     # Parameter in Bereich 3000h verschieben
         self.sdo_wr(index, subindex, val, timeout)
      elif (self.Interface >= INTERFACE_COM) and (self.Interface <= INTERFACE_COM10):  # COM1-COM10 RS232 Interface
         return Com.Sp(self.Interface-INTERFACE_COM, index, subindex, val, timeout)
      elif (self.Interface == INTERFACE_SIM):                        # for Tests und Simulation
         self.SimPrintSp(self.NodeId, index, subindex, val, timeout)

   def Par (self, p1, p2=None, p3=None, timeout=0xFFFF):
      if p3 is None:
         if p2 is None:
            return self.Gp(p1, p2, timeout=timeout)
         elif type(p1) is list:
            self.Sp(p1, p2, timeout=timeout)
         else:
            return self.Gp(p1, p2, timeout=timeout)
      else:
         self.Sp(p1, p2, p3, timeout=timeout)

   def Par2 (self, mux0, mux1, val=None, timeout=0xFFFF):            # mux=[index,subindex] val=[val0,val1]
      if val==None:
         return [self.Gp(mux0,timeout=timeout),self.Gp(mux1,timeout=timeout)]  # return as [val0,val1]
      else:
         self.Sp(mux0, val[0], timeout=timeout)
         self.Sp(mux1, val[1], timeout=timeout)

   def ParFraction (self, index, val=None, timeout=0xFFFF):          # val as [val0,val1]
      if val==None:
         return [self.Gp(index,0,timeout=timeout),self.Gp(index,1,timeout=timeout)] # return as [val0,val1]
      else:
         self.Sp(index,0, val[0], timeout=timeout)
         self.Sp(index,1, val[1], timeout=timeout)

   def Sdo (self, p1, p2=None, p3=None, timeout=0xFFFF):
      if type(p1) is list:                                           # Form1: val = Sdo(mux)             Read
         mux      = self.GetMux(p1)                                  #        Sdo(mux, val)              Write
         index    = mux[0]
         subindex = mux[1]
         val      = p2
      else:                                                          # Form2: val = Sdo(index,subindex)  Read, subindex==0
         index    = p1                                               #        Sdo(index,subindex, val)   Write
         subindex = p2
         val      = p3

      if val is None:
         if self.Interface == INTERFACE_miCan:                       # CAN Interface 1
            return self.sdo_rd(index, subindex, timeout)
         elif (self.Interface == INTERFACE_SIM):                     # for Tests und Simulation
            self.SimPrintSdoRd(self.NodeId, index, subindex, timeout)
            return 0
      else:
         if self.Interface == INTERFACE_miCan:                       # CAN Interface 1
            self.sdo_wr(index, subindex, val, timeout)
         elif (self.Interface == INTERFACE_SIM):                     # for Tests und Simulation
            self.SimPrintSdoWr(self.NodeId, index, subindex, val, timeout)

   def SdoRd (self, p1, p2=0, timeout=0xFFFF):
      mux      = self.GetMux(p1,p2)
      index    = mux[0]
      subindex = mux[1]

      if (self.Interface == INTERFACE_miCan):                        # CAN Interface 1
         return self.sdo_rd(index, subindex, timeout)
      elif (self.Interface == INTERFACE_SIM):                        # for Tests und Simulation
         self.SimPrintSdoRd(self.NodeId, index, subindex, timeout)
         return 0

   def SdoWr (self, p1, p2, p3=None, timeout=0xFFFF):
      if type(p1) is list:
         mux      = self.GetMux(p1,p2)
         index    = mux[0]
         subindex = mux[1]
         val      = p2
      else:
         index    = p1
         subindex = p2
         val      = p3

      if (self.Interface == INTERFACE_miCan):                        # CAN Interface 1
         return self.sdo_wr(index, subindex, val, timeout)
      elif (self.Interface == INTERFACE_SIM):                        # for Tests und Simulation
         self.SimPrintSdoWr(self.NodeId, index, subindex, val, timeout)

   def SdoFraction (self, index, subindex, val=None, timeout=0xFFFF):                                       # val as [val0,val1]
      if val==None:
         return [self.SdoRd(index,subindex,timeout=timeout),self.SdoRd(index,subindex+1,timeout=timeout)]   # return as [val0,val1]
      else:
         self.SdoWr(index,subindex,   val[0], timeout=timeout)
         self.SdoWr(index,subindex+1, val[1], timeout=timeout)

   # File Functions ---------------------------------------------------------------------------------------------------------------

   def sdo_rd_file (self, index, subindex, timeout):
      return 0

   def sdo_wr_file (self, index, subindex, val, timeout):
      err = 0

      if self.OutFilename:
         try:
            txt = self.OutTxtFormat % (index, subindex, val, timeout)
         except Exception as e:
            err = -1
            raise FileError("Bad output format string \"%s\". [%s]" % (repr(str(self.OutTxtFormat)), str(e)))

         if type(self.OutFormat) is tuple:
            try:
               node_id = self.NodeId
               value   = val

               exec("txt = (self.OutFormat[0]) %" + "(" + self.OutFormat[1] + ")")
            except Exception as e:
               err = -2
               raise FileError("Bad out format: \"%s\". [%s]" % (repr(str(self.OutFormat)), str(e)))

         if not err:
            try:
               of = open(self.OutFilename, "a+")
            except Exception as e:
               err = -3
               raise FileError("Can't open the file \"%s\". [%s]" % (str(self.OutFilename), str(e)))

            try:
               of.write(txt)
            except Exception as e:
               raise FileError("Can't write to the file \"%s\". [%s]" % (str(self.OutFilename), str(e)))

            if not err:
               of.close()

   def SetOutput (self, out_filename, out_txtformat=None, out_format=None):
      if self.Saved_sdo_rd is None:
         self.Saved_sdo_rd = self.sdo_rd
         self.sdo_rd       = self.sdo_rd_file

      if self.Saved_sdo_wr is None:
         self.Saved_sdo_wr = self.sdo_wr
         self.sdo_wr       = self.sdo_wr_file

      self.OutFilename = out_filename
      self.OutType     = 1

      if out_txtformat is not None:
         self.OutTxtFormat = out_txtformat

      self.OutFormat = out_format

      if os.path.exists(out_filename):
         try:
            os.remove(out_filename)
         except:
            raise FileError("Can't remove the file %s" % (out_filename))

   def RestoreOutput (self):
      if self.Saved_sdo_rd is not None: self.sdo_rd = self.Saved_sdo_rd
      if self.Saved_sdo_wr is not None: self.sdo_wr = self.Saved_sdo_wr
      self.OutType = 0

   #- obsolete -
   def StartDevice      (self):  self.StartNode()
   def StopDevice       (self):  self.StopNode()

   def StartAllDevices  (self):  self.StartAllNodes()
   def StopAllDevices   (self):  self.StopAllNodes()
