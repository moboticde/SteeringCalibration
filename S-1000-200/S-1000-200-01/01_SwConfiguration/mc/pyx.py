# -*- coding: utf-8 -*-
#=================================================================================================================================#
#                                                                      Copyright (c) 1997-2020 by miControl. All rights reserved. #
# File     : pyx.py                                                                                                               #
#                                                                                                                                 #
# Project  : mPLC                                                                                                                 #
# System   : Python >=2.7                                                                                                         #
# Version  : (see Version)                                                                                                        #
# Customer :                                                                                                                      #
# Company  : miControl                                                                                                            #
#                                                                                                                                 #
# Author   : miControl Development Team                                                                                           #
# Team     : dariusz Parma (dP)  mailto:dp@miControl.de                                                                           #
# Date     : 15.02.2019                                                                                                           #
#---------------------------------------------------------------------------------------------------------------------------------#
# Customer : miControl                                                                                                            #
# OrderNr. : none                                                                                                                 #
# Date     : 15.02.2019                                                                                                           #
#=================================================================================================================================#
# Brief:    Functions for Python2 and Python3
#
#----------------------------------------------------------------------------------------------------------------------------------
# History:                                                  (Symbol legend: + Added, - Removed, ~ Changed, ! Correction, # Comment)
#  15.02.2019 dP: Created
#  05.11.2020 dP: V1.01.00.00 ~Modul wurde von dx_pyx.py in in pyx.py umbennant, +Clock, +Sleep
#
#==================================================================================================================================
from __future__ import print_function

import sys, time

Version = (1,0x01,0x00,0x00)

#= Constants ======================================================================================================================
#= Global vars ====================================================================================================================
#= Functions ======================================================================================================================

def IsPython3 ():
   return (sys.version_info[0] == 3)

def IsPython2 ():
   return (sys.version_info[0] == 2)

#==================================================================================================================================

#----------------------------------------------------------------------------------------------------------------------------------
if IsPython2():
   IntTypes       = [int, long]              #type: ignore (Pylance/Pyright)                                         #pylint: disable=used-before-assignment
   StrTypes       = [str, unicode]           #type: ignore (Pylance/Pyright)  #pylint: disable=undefined-variable    #pylint: disable=used-before-assignment
   NumTypes       = [int, long, float]       #type: ignore (Pylance/Pyright)

   TimeClockFunc  = time.clock               #type: ignore (Pylance/Pyright)  #pylint: disable=no-member
   TimeSleepFunc  = time.sleep               #type: ignore (Pylance/Pyright)
else:
   long       = int
   unicode    = str
   basestring = str

   IntTypes   = [int]
   StrTypes   = [str]
   NumTypes   = [int, float]

   xrange     = range

   if sys.version_info > (3,7):
      TimeClockFunc = time.perf_counter      #type: ignore (Pylance/Pyright)  #pylint: disable=no-member
      TimeSleepFunc = time.sleep             #type: ignore (Pylance/Pyright)
   else:
      TimeClockFunc = time.clock             #type: ignore (Pylance/Pyright)  #pylint: disable=no-member
      TimeSleepFunc = time.sleep             #type: ignore (Pylance/Pyright)

#----------------------------------------------------------------------------------------------------------------------------------
def IsFileObject (o):
   ret = False

   if IsPython2():
      import types

      if type(o) is types.FileType:                                           #pylint: disable=no-member
         ret = True
   else:
      from io import IOBase

      if isinstance(o, IOBase):
         ret = True

   return ret

#-------------------------------------------------------------------------------------------------------------------------------
def Print (*args, **kwargs):
   stdout = kwargs.pop("file",  sys.stdout)

   if stdout == None:
      return

   sep   = kwargs.pop("sep",   ' ')
   end   = kwargs.pop("end",   '\n')
   flush = kwargs.pop("flush", False)

   if kwargs:
      raise TypeError("invalid keyword arguments for Print()")

   if IsPython2():
      base_str = basestring   #pylint: disable=undefined-variable
   else:
      base_str = str

   def write (data):
      if not isinstance(data, base_str):
         data = str(data)

      if IsPython2():
         if (isinstance(data, unicode) and hasattr(stdout, 'encoding') and (stdout.encoding is not None)):
            errors = getattr(stdout, "errors", None)

            if errors is None:
               errors = "strict"

            stdout.write(data.encode(stdout.encoding, errors))
         else:
            stdout.write(data)
      else:
         stdout.write(data)

   for i, arg in enumerate(args):
      if i:
         write(sep)
      write(arg)
   write(end)

   if flush:
      stdout.flush()

#-------------------------------------------------------------------------------------------------------------------------------
def clock ():                                                              # Kleingeschrieben für Kompatibilität zu time.clock
   return TimeClockFunc()

#-------------------------------------------------------------------------------------------------------------------------------
def sleep (secs):                                                          # Kleingeschrieben für Kompatibilität zu time.sleep
   return TimeSleepFunc(secs)

#==================================================================================================================================
if __name__ == "__main__":
   Print("jajko")

   Print("a", "b", "c", "d")
   Print(u"a", u"b", u"c", u"d")
   Print(u"a",  "b",  "c", u"d")
   Print(u"x",  "x",  "x", u"x", file=None)
   Print("a", "b", "c", "d", sep='-')
   Print("a", "b", "c", "d", sep='')

   Print("a1", "b1", "c1", "d1", sep='', end='')
   Print("a2", "b2", "c2", "d2", sep='')
