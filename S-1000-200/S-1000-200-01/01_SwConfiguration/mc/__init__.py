# -*- coding: utf-8 -*-
#=================================================================================================================================#
#                                                                      Copyright (c) 1997-2020 by miControl. All rights reserved. #
# File     : __init__.py                                                                                                          #
#                                                                                                                                 #
# Project  :                                                                                                                      #
# System   : Python                                                                                                               #
# Version  : 1.01.00.00                                                                                                           #
# Customer :                                                                                                                      #
# Company  : miControl                                                                                                            #
#                                                                                                                                 #
# Author   : miControl Development Team                                                                                           #
# Team     : dariusz Parma (dP)  mailto:dp@miControl.de                                                                           #
# Date     : 15.03.2003                                                                                                           #
#=================================================================================================================================#
# Brief:    mcPyLib
#
#----------------------------------------------------------------------------------------------------------------------------------
# History:                                                  (Symbol legend: + Added, - Removed, ~ Changed, ! Correction, # Comment)
#
#==================================================================================================================================

import sys

if sys.version_info < (2,7):
   raise ImportError('miControl mcPyLib (mc - Module) requires Python 2.7 or greater.')

from .base import *
