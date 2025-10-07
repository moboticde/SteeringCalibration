# -*- coding: utf-8 -*-
#=================================================================================================================================#
#                                                                      Copyright (c) 1997-2020 by miControl. All rights reserved. #
# File     : base.py                                                                                                              #
#                                                                                                                                 #
# Project  :                                                                                                                      #
# System   : Python                                                                                                               #
# Version  : 1.00.00.00                                                                                                           #
# Customer :                                                                                                                      #
# Company  : miControl                                                                                                            #
#                                                                                                                                 #
# Author   : miControl Development Team                                                                                           #
# Team     : dariusz Parma (dP)  mailto:dp@miControl.de                                                                           #
# Date     : 15.03.2003                                                                                                           #
#=================================================================================================================================#
# Brief:    miControl mcPyLib base module
#
#----------------------------------------------------------------------------------------------------------------------------------
# History:                                                  (Symbol legend: + Added, - Removed, ~ Changed, ! Correction, # Comment)
#  15.03.2003 dP: Created
#  12.02.2006 dP: +Usb
#  31.10.2008 dP: +Sys
#
#==================================================================================================================================
if __package__:
   from . import __version__
   from . import _tim as Tim

   from .common import Msg
else:
   import __version__
   import _tim as Tim

   from common import Msg

#----------------------------------------------------------------------------------------------------------------------------------
Version        = __version__.Version
VersionString  = __version__.VersionString

__version__    = Version
__versionstr__ = VersionString

# miControl build-in modules ------------------------------------------------------------------------------------------------------
#
try:
   import mc_sys  as Sys      # ab mPLC V2.65.00.00
   import mc_can  as Can
   import mc_com  as Com
   import mc_usb  as Usb

except (ValueError, ImportError) as exc:
   if __package__:
      from . import _sys   as Sys
      from . import _can   as Can
      from . import _com   as Com
      from . import _usb   as Usb
   else:
      import _sys as Sys
      import _can as Can
      import _com as Com
      import _usb as Usb

try:
   import mc_ibs  as Ibs
except (ValueError, ImportError) as exc:
   if __package__:
      from . import _ibs   as Ibs
   else:
      import _ibs as Ibs

# for compatiblity ----------------------------------------------------------------------------------------------------------------
#
def Delay (tim_ms):
   Tim.Delay(tim_ms)

def Clock ():
   return Tim.Clock()

# printf - entspricht 'C'-Funktion 'printf'
#
def printf (format, *args):
   txt = format % args
   if len(txt)==0 or txt[len(txt)-1]!="\n":
      txt += " "
   Msg.Print(txt)
