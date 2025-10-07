# -*- coding: utf-8 -*-
#=================================================================================================================================#
#                                                                      Copyright (c) 1997-2020 by miControl. All rights reserved. #
# File     : common.py                                                                                                            #
#                                                                                                                                 #
# Project  :                                                                                                                      #
# System   : Python                                                                                                               #
# Version  : (see VERSION)                                                                                                        #
# Customer :                                                                                                                      #
# Company  : miControl                                                                                                            #
#                                                                                                                                 #
# Author   : miControl Development Team                                                                                           #
# Team     : dariusz Parma (dP)  mailto:dp@miControl.de                                                                           #
# Date     : 02.02.2012                                                                                                           #
#=================================================================================================================================#
# Brief:    Common functions for mcPyLib
#
#----------------------------------------------------------------------------------------------------------------------------------
# History:                                                  (Symbol legend: + Added, - Removed, ~ Changed, ! Correction, # Comment)
#
#==================================================================================================================================
if __package__:
   from .dx_dbg   import DxDbg
   from .dx_error import DxError
   from .dx_msg   import DxMsg
else:
   from dx_dbg    import DxDbg
   from dx_error  import DxError
   from dx_msg    import DxMsg

__all__ = ['Dbg', 'Err', 'Msg']

VERSION = (1,0x00,0x00,0x00)

MC_DEBUG_Level    = None
MC_DEBUG_LogLevel = None

#----------------------------------------------------------------------------------------------------------------------------------
Dbg = DxDbg(level=MC_DEBUG_Level, log_level=MC_DEBUG_LogLevel)
Err = DxError()
Msg = DxMsg()


# TEST ----------------------------------------------------------------------------------------------------------------------------
def Test ():
   pass

#==================================================================================================================================
if __name__ == '__main__':
   Test()
