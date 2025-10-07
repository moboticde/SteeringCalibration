# -*- coding: utf-8 -*-
#=================================================================================================================================#
#                                                                      Copyright (c) 1997-2020 by miControl. All rights reserved. #
# File     : mPLC.py                                                                                                              #
#                                                                                                                                 #
# Project  :                                                                                                                      #
# System   : Python                                                                                                               #
# Version  : (see ClassVersion)                                                                                                   #
# Customer :                                                                                                                      #
# Company  : miControl                                                                                                            #
#                                                                                                                                 #
# Author   : miControl Development Team                                                                                           #
# Team     : dariusz Parma (dP)  mailto:dp@miControl.de                                                                           #
# Date     : 28.02.2019                                                                                                           #
#=================================================================================================================================#
# Brief:    System functions for the mPLC
#
#----------------------------------------------------------------------------------------------------------------------------------
# History:                                                  (Symbol legend: + Added, - Removed, ~ Changed, ! Correction, # Comment)
#  10.02.2020 dP: V2.00.00.00:   +UnicodeEncodeText, +UnicodeDecodeText, +Py3, +__StdIn__Redirector
#
#==================================================================================================================================
import sys

ModuleVersion = (2,0x01,0x00,0x00)

if not "CFG_mPLC_Encoding" in dir():
   CFG_mPLC_Encoding = None

if CFG_mPLC_Encoding is not None:
   _mc_encoding_ = CFG_mPLC_Encoding
else:
   _mc_encoding_ = 'iso-8859-1'           #'utf-8'

if (sys.version_info[0] >= 3):
   from importlib import reload                                                                                                     #pylint: disable=no-name-in-module

   reload(sys)

   #-------------------------------------------------------------------------------------------------------------------------------
   def UnicodeEncodeText (txt, encoding='iso-8859-1', fallback_encoding='utf-8'):
      return txt

   #-------------------------------------------------------------------------------------------------------------------------------
   def UnicodeDecodeText (txt, encoding='iso-8859-1', fallback_encoding='utf-8'):
      return txt
else:
   from imp import reload                                                                                                           #pylint: disable=no-name-in-module

   reload(sys)

   try:
      sys.setdefaultencoding(_mc_encoding_)
   except AttributeError:
      pass

   #-------------------------------------------------------------------------------------------------------------------------------
   def UnicodeEncodeText (txt, encoding='iso-8859-1', fallback_encoding='utf-8'):
      if type(txt) is unicode:                                                                                                      #pylint: disable=undefined-variable
         try:
            txt = txt.encode(encoding, 'strict')
         except UnicodeEncodeError:
            try:
               txt = txt.encode(fallback_encoding, 'strict')
            except UnicodeEncodeError:
               txt = txt.encode(fallback_encoding, 'replace')

      return txt

   #-------------------------------------------------------------------------------------------------------------------------------
   def UnicodeDecodeText (txt, encoding='iso-8859-1', fallback_encoding='utf-8'):
      if type(txt) is str:
         try:
            txt = txt.decode(encoding, 'strict')
         except UnicodeDecodeError:
            try:
               txt = txt.decode(fallback_encoding, 'strict')
            except UnicodeDecodeError:
               txt = txt.decode(fallback_encoding, 'replace')

      return txt

#==================================================================================================================================
def OnRunScript (dict_globals=None):
   import sys, os, site

   if (sys.version_info[0] >= 3):
      from importlib import reload                                                                                                  #pylint: disable=no-name-in-module
   else:
      from imp import reload                                                                                                        #pylint: disable=no-name-in-module

   global _mc_InitSysPath_
   global _mc_InitGlobals_
   global _mc_InitModules_

   #-------------------------------------------------------------------------------------------------------------------------------
   if dict_globals == None:
      dict_globals = globals()

   #-------------------------------------------------------------------------------------------------------------------------------
   import mc_sys                                                                                                                    #pylint: disable=import-error

   if hasattr(sys, 'stdin'):
      mc_sys.OrigStdIn = sys.stdin
   else:
      mc_sys.OrigStdIn = None

   if hasattr(sys, 'stderr'):
      mc_sys.OrigStdErr = sys.stderr
   else:
      mc_sys.OrigStdErr = None

   if hasattr(sys, 'stdout'):
      mc_sys.OrigStdOut = sys.stdout
   else:
      mc_sys.OrigStdOut = None

   class __StdIn__Redirector (object):
      def read (self):
         return ""

      def write (self, txt):
         pass

      def flush (self):
         pass

   class __StdErr__Redirector (object):
      def write (self, txt):
         txt = UnicodeEncodeText(txt)
         mc_sys.StdErrWrite(txt)

      def flush (self):
         pass

   class __StdOut__Redirector (object):
      def write (self, txt):
         txt = UnicodeEncodeText(txt)
         mc_sys.StdOutWrite(txt)

      def flush (self):
         pass

   mc_sys.__StdIn__Redirector  = __StdIn__Redirector
   mc_sys.__StdErr__Redirector = __StdErr__Redirector
   mc_sys.__StdOut__Redirector = __StdOut__Redirector

   mc_sys.StdIn  = mc_sys.__StdIn__Redirector()
   mc_sys.StdErr = mc_sys.__StdErr__Redirector()
   mc_sys.StdOut = mc_sys.__StdOut__Redirector()

   sys.stdin  = mc_sys.StdIn
   sys.stderr = mc_sys.StdErr
   sys.stdout = mc_sys.StdOut

   # Reinit Stdout's
   #
   from .common import Dbg, Err, Msg

   Dbg.InitStdout()
   Err.InitStdout()
   Msg.InitStdout()

   #rint "OnRunScript..."
   #rint "1:", '_mc_InitSysPath_' in globals()
   #rint "2:", "_mc_InitGlobals_" in globals()
   #rint "3:", "_mc_InitModules_" in globals()

   #-------------------------------------------------------------------------------------------------------------------------------
   if '_mc_InitSysPath_' not in globals():
      _mc_InitSysPath_ = list(sys.path[1:])

   sp       = _mc_InitSysPath_
   root_dir = os.path.normpath(os.path.dirname(sys.exec_prefix)).lower()

   new_path = [sys.path[0], "."]

   for p in sp:
      if os.path.normpath(p).lower().startswith(root_dir):
         if p not in new_path:
            new_path.append(p)

   for p in sp:
      if not os.path.normpath(p).lower().startswith(root_dir):
         if p not in new_path:
            new_path.append(p)

   sys.path = new_path[:]

   #-------------------------------------------------------------------------------------------------------------------------------
   if '_mc_InitGlobals_' in globals():
      for g in dict_globals.keys():
         if (g not in _mc_InitGlobals_) and (g not in ["_mc_InitSysPath_", "_mc_InitGlobals_", "_mc_InitModules_"]): #pylint: disable=used-before-assignment
            #rint("DELETE GLOBAL: %s" % g)
            del(dict_globals[g])
   else:
      _mc_InitGlobals_ = dict_globals.keys()

   #-------------------------------------------------------------------------------------------------------------------------------
   py_lib_dir = os.path.dirname(site.__file__)

   if '_mc_InitModules_' in globals():
      for m_name in sys.modules.keys():
         m = sys.modules[m_name]

         #if "m1" in m_name:
         #   rint m, m_name, (m and hasattr(m, '__file__') and (not m.__file__.lower().startswith(py_lib_dir.lower()))) or m_name.startswith('mc.') or (m_name is 'mc')

         if (m_name not in _mc_InitModules_) and (m_name not in sys.builtin_module_names) and ("(built-in)" not in str(m)):         #pylint: disable=used-before-assignment
            if (m and hasattr(m, '__file__') and (not m.__file__.lower().startswith(py_lib_dir.lower()))) or m_name.startswith('mc.') or (m_name is 'mc'):
               if m and hasattr(m, '__file__') and not m.__file__.lower().endswith(".pyd"):

                  do_reload = False

                  if sys.version_info[0] == 2:
                     filename_pyc = os.path.splitext(m.__file__)[0] + '.pyc'
                     filename_pyo = os.path.splitext(m.__file__)[0] + '.pyo'
                     filename_py  = os.path.splitext(m.__file__)[0] + '.py'

                     #rint filename_pyc
                     #rint filename_py
                     #rint os.path.exists(filename_pyc), os.path.isfile(filename_pyc), os.path.exists(filename_py), os.path.isfile(filename_py)
                     #rint os.path.getmtime(filename_pyc) < os.path.getmtime(filename_py)
                     #rint os.path.getmtime(filename_pyc), os.path.getmtime(filename_py)

                     pyc_exists = os.path.exists(filename_pyc) and os.path.isfile(filename_pyc)
                     pyo_exists = os.path.exists(filename_pyo) and os.path.isfile(filename_pyo)
                     py_exists  = os.path.exists(filename_py)  and os.path.isfile(filename_py)

                     if (pyc_exists or pyo_exists) and py_exists:
                        if pyc_exists:
                           if os.path.getmtime(filename_pyc) < os.path.getmtime(filename_py):
                              do_reload = True
                        elif pyo_exists:
                           if os.path.getmtime(filename_pyo) < os.path.getmtime(filename_py):
                              do_reload = True
                     elif py_exists:            # z.B.: *.pyc wurde gelöscht
                        do_reload = True
                  else:
                     filename_mod = m.__file__

                     if filename_mod.lower().endswith(".py"):
                        filename_py  = filename_mod
                        fn           = os.path.splitext(filename_py)[0]
                        pn,fn        = os.path.split(fn)
                        filename_pyc = os.path.join(pn, "__pycache__", fn + (".cpython-%d%d.pyc" % sys.version_info[:2]))
                        filename_pyo = os.path.join(pn, "__pycache__", fn + (".cpython-%d%d.pyo" % sys.version_info[:2]))

                        pyc_exists = os.path.exists(filename_pyc) and os.path.isfile(filename_pyc)
                        pyo_exists = os.path.exists(filename_pyo) and os.path.isfile(filename_pyo)
                        py_exists  = os.path.exists(filename_py)  and os.path.isfile(filename_py)

                        if (pyc_exists or pyo_exists) and py_exists:
                           if pyc_exists:
                              if os.path.getmtime(filename_pyc) < os.path.getmtime(filename_py):
                                 do_reload = True
                           elif pyo_exists:
                              if os.path.getmtime(filename_pyo) < os.path.getmtime(filename_py):
                                 do_reload = True
                        elif py_exists:            # z.B.: *.pyc wurde gelöscht
                           do_reload = True

                  if do_reload:
                     #rint("RELOAD MODULE: %s" % (m.__file__))

                     try:
                        reload(m)                                                                                                   #xylint: disable=undefined-variable
                     except ImportError:
                        del sys.modules[m_name]
                     except Exception:
                        pass
   else:
      _mc_InitModules_ = sys.modules.keys()

#==================================================================================================================================
def OnEndScript (dict_globals=None):
   #rint "OnEndScript..."

   #-------------------------------------------------------------------------------------------------------------------------------
   #if dict_globals == None:
   #   dict_globals = globals()

   #-------------------------------------------------------------------------------------------------------------------------------
   import sys
   import mc_sys                                                                                                                    #pylint: disable=import-error

   sys.stdin  = mc_sys.OrigStdIn
   sys.stderr = mc_sys.OrigStdErr
   sys.stdout = mc_sys.OrigStdOut
