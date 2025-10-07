# -*- coding: utf-8 -*-
#=================================================================================================================================#
#                                                                      Copyright (c) 1997-2020 by miControl. All rights reserved. #
# File     : __version_.py                                                                                                        #
#                                                                                                                                 #
# Project  :                                                                                                                      #
# System   : Python                                                                                                               #
# Version  : (see Version)                                                                                                        #
# Customer :                                                                                                                      #
# Company  : miControl                                                                                                            #
#                                                                                                                                 #
# Author   : miControl Development Team                                                                                           #
# Team     : dariusz Parma (dP)  mailto:dp@miControl.de                                                                           #
# Date     : 15.03.2003                                                                                                           #
#=================================================================================================================================#
# Brief:    Version of mcPyLib
#
#----------------------------------------------------------------------------------------------------------------------------------
# History:                                                  (Symbol legend: + Added, - Removed, ~ Changed, ! Correction, # Comment)
#  03.05.2010 dP: V2.02.00.00 +plot.py
#  14.09.2010 dP: V2.02.01.00 !bootloadr.py
#  14.11.2010 dP: V2.02.02.00  ClassMpu-V2.00.01.00 - Wegen kompatibilität zu MPU1 kann der Register0 nicht als Returnwert verwendet werden.
#  01.03.2011 dP: V2.02.03.00  ClassMpu-V2.00.02.00 - mpu2_asm: !__get_arg1 im Bezug auf indirekte Addresierung
#  05.04.2011 dP: V2.02.04.00  ClassMpu-V2.00.02.00 - mpu2_asm: +init_value für Var's
#  xx.09.2011 dP: V2.02.05.00  ClassMpu-V2.00.02.00 - ~für DefUserVar, ~mpu2_dbginfo
#  04.02.2012 dP: V2.03.00.00 +i18n.py, +base.py, +mx_file.py
#  29.03.2012 dP: V2.04.00.00 +dbak.py
#  13.06.2012 dP: V2.05.00.00 bootloadr.py: +StopMpu
#  20.06.2012 dP: V2.05.00.00 ~in pymc.py: def Run (node_id, prg_filename, mpu_filename=None, store=True, start=True, dump=0, out_filename=None, out_txtformat=None, out_format=None, init_func=None):
#  21.08.2012 dP: V2.05.00.00 Korrektur von Limit_xx - Funktionen (dort waren lokale Funktionen von MpuAsm verwendet -> Exception beim assemblieren)
#  14.01.2013 dP: V2.06.00.00 Korrektur von Mclrb im MPU1+MPU2. Mclrb hat gleiches Kod wie Clrb generiert.
#  31.01.2013 dP: V2.06.01.00 Bei relativen Sprüngen kann jetzt als arg0 auch eine Konstante sein (war wegen den pymc-Compiler V1.01.00.11 nötig).
#  22.05.2013 dP: V2.06.02.00 +Unterstützung von pymc-Compiler V2.0. Die pymc.Run-Funktion akzeptiert jetzt auch *.mpu.mx Dateien.
#                             ~Alle aktive "print"-Anweisungen wurden durch Msg.Print-Funktion ersetzt.
#  16.08.2013 dP: V2.06.03.00 pymc.Run braucht jetzt kein Compiler um mpu.mx-Dateien zu laden.
#  09.09.2013 dP: V2.06.04.00 ~util.GetExecPath        arbeitet jetzt mit PyInstaller
#                             +util.GetResourcePath    arbeitet auch mit PyInstaller
#  10.09.2013 dP: V2.06.04.00 ~DT_XXXXX vom "mpu2_types.py" wurden an IPC-Interface angepasst
#  16.09.2013 dP: V2.06.05.00 !dx_dbg.py,
#                             !mpu2_asm.py # dP 13.09.2013: Falls nur Variablen definiert wurden (kein eigentliches Programm vorhanden) war __MPU_PRG_ENTRY__ nicht definiert
#  01.10.2013 dP: V2.07.00.00 ~dx_dbg.py, ~dx_error_codes.py
#  08.11.2013 dP: V2.07.00.01 ~Anpassung von display.py an 9s12xe CPU (Firmware 1.91.00.56)
#  14.11.2013 dP: V2.07.00.02 ~In pymc.Run man kann jetzt auch nur "mpu_filename" angeben.
#                             +mpu2.Addr Funktion (MPU2_VERSION=2.04.00.00)
#  21.11.2013 dP: V2.07.00.03 ~pymc.py
#                                1. Zuerst wird das Compiler in dem gleichem Verzeichnis wie das ausgeführte Script gesucht.
#                                2. Falls nicht gefunden, dann wird das Compiler von dem mPLC-Verzeichnis genommen.
#                                Die Funktion "Run" hat neues Argument: "compiler" - damit kann man den Compiler angeben.
#                                   Run (node_id, prg_filename, mpu_filename=None, store=True, start=True, dump=0, out_filename=None, out_txtformat=None, out_format=None, init_func=None, compiler=None)
#  22.11.2013 dP: V2.07.00.04 ~bootloader.py: +Release-Information wurde zu Versionausgaben hinzugefügt
#  02.12.2013 dP: V2.07.00.05 dsa.py: +ReleaseSw, +Release-Information wurde zu Versionausgaben hinzugefügt
#  10.12.2013 dP: V2.07.00.05 mpu2.py: +Überprüfung des Platzes für Variablen mpu2-V2.05.00.00
#                             bootloadr.py: 03.12.2013 MH:  2.60.00.00 +BootloaderActive (für mcFirmwareConverter)
#                                           10.12.2013 MH:  2.61.00.00 +use_extd_cobid
#  18.02.2014 dP: V2.07.00.06 pymc-BUGFIX5003 in mx_file.py
#  14.03.2014 dP: V2.07.00.07 bootloader.py 2.61.00.01 +MultiBootloader-Funktionalität
#  02.04.2014 dP: V2.07.00.08 !bootloader.py 2.61.00.02
#  17.09.2014 dP: V2.07.00.09 +in dsa.py: TrgVel,CmdVel,VelFollowingError. Dsa.ClassVersio_n = (1,0x42, 0x00,0x00)
#  15.12.2014 dP: V2.07.00.10 +in bootloader.py: miCAN-Stick2 wird unterstützt.
#  15.01.2015 dP: V2.07.00.10 ~plot.py: Anpassung an neue "wxPython 3.0" und "mathplotlib 1.4.2"
#  15.01.2015 dP: V2.07.00.10 ~pymc.py: Aenderung wegen Intergration ins mcTools
#  20.01.2015 dP: V2.07.00.10 pymc-BUGFIX5008 in mx_file.py
#  25.03.2015 dP: V2.07.00.11 ~plot.py V1.0.0.2
#  21.04.2015 dP: V2.07.00.11 ~util.py: +UnicodeEncode() +UnicodeDecode()
#  12.06.2015 dP: V2.07.00.12 ~bootloader.py: 06.05.2015 MH:  2.61.00.04 +DatCrc in Programming_LPC24XX (für mcFirmwareConverter)
#  15.06.2015 dP: V2.07.00.13 !util.py wurde korrigiert ("mport sys" fehlte)
#  15.06.2015 dP: V2.08.00.00 !bootloader.py: Stringkorrektur für gettext
#  15.06.2015 dP: V2.08.00.00: RELEASE VERSIOIN
#  01.10.2015 dP: V2.09.00.01: dbak V1.21.00.00 (unicode zeichensätze behandlung wurde geändert)
#  21.12.2015 dP: V2.09.00.02: dx_error V1.04.00.00 (__check_exc_value__(self) wurde eingefuegt)
#  14.04.2016 dP: V2.09.00.03: util.GetAppSignOn
#  31.05.2016 dP: V2.09.00.04: ~bootloader.py: 31.05.2016 dP:  2.61.00.05 ~Kosmetische Korrekturen der Print-Ausgaben
#  21.06.2016 dP: V2.10.00.00: Release
#  18.11.2016 dP: V2.10.01.00: jam.py Korrektur
#  14.12.2016 dP: V2.10.02.00: Korrektur in plot.py
#  19.12.2016 dP: V2.10.03.00: Korrektur in pymc.py
#  01.02.2017 dP: V2.10.04.00: +DecorCall in dx_dbg.py
#  06.03.2017 dP: V2.10.05.00: +DefUserVar, Addr, BoostShot in _pymc_builtins_.py - Release Version
#  10.03.2017 dP: V2.10.05.01: +IsOsWin, +IsOsLinux in util.py
#                              +"rU" bei "file" und "open" Operationen für "universal newline interpretation" (wegen Linux)
#  23.03.2017 dP: V2.10.05.02: !Event_CmdOnSpecError in dsa.py
#  28.03.2017 dP: V2.10.06.00: Release
#  04.05.2017 dP: V2.11.00.01: ~Modulename io wurde auf iom, wegen Namenkonfikt mit python io-Modul, geändert.
#  10.05.2017 dP: V2.11.00.02: +dx_autocompletion.py, +run_autocompletion_server.py
#  20.07.2017 dP: V2.11.00.03: ~Änderungen von Max-mcTools wurden übernommen
#  24.07.2017 dP: V2.11.00.04: ~mx_file.py - 24.07.2017 dP: V2.00.00.06  In LoadMpu fehlte _close_in_file
#  04.08.2017 dP: V2.11.00.05: ~Änderungen von Max-mcTools/PyMci wurden übernommen
#                              ~Die Fehlercodes (dx_error_codes.py) wurden mit err_decl.h synchroniziert
#  09.01.2018 dP: V2.11.00.06: ~Änderungen in plot.py
#  12.01.2018 dP: V2.11.00.07: +temp_sensor_KTY84.py
#  17.01.2018 dP: V2.11.00.08: ~Änderungen in plot.py
#  18.01.2018 dP: V2.11.00.09: +dx_build_exe.py
#  19.01.2019 dP: V2.11.00.0B: +load, autostart Parameters in mpu2.Exec(), pymc.Run(), pymc.RunEx
#  23.01.2019 dP: V2.11.00.0C: diagnostic.py V2.02.00.00
#                                 ~mem_type wurde in mem_region umbennant                              ACHTUNG: INKOMPATIBILITÄT !!!!
#                                 +self.ActualBlMemRegion, +Zugriff auf GlobalMem in Bootloader-Modus
#  25.01.2019 dP: V2.11.00.0D: +util.GetTimeStampStr()
#  26.02.2019 dP: V2.11.00.0E: Portierung auf Python3. mcPyLib bleibt zu Python27 kompatibel aber nicht zu Python25.
#  08.03.2019 dP: V2.11.00.0F: +cmdutil.Exec
#  10.07.2019 dP: V2.11.00.10: +dx_blu.py +dx_blu_data.py +hw_cpu_reg_9s12xep100.py
#                              ~bootloader.py (Anpassungen an Bootloader Universal (BLU))
#  24.07.2019 dP: V2.12.00.00: Release aus V2.11.00.10
#  02.10.2019 dP: V2.12.00.01: ~dbak.py auf V1.23.00.00 (Leere Verzeichnisse werden auch archiviert)
#  10.10.2019 dP: V2.12.00.02: ~dbak.py auf V1.26.00.00 (dbak.py wurde übergearbeitet - ist aber kompatibel zu verherigen Versionen)
#  12.11.2019 dP: V2.12.00.03: ~dx_blu.py      in blu.py      umbennant
#                              ~dx_blu_data.py in blu_data.py umbenannt
#                              +foc.py:  Klassen für FOC: FocDiag
#                              +henc.py: Henc - Klasse für HALL-Encoder von IC-HAUS: IC-MH, IC-MU, IC-NQC (SinCos)
#  13.11.2019 dP: V2.12.00.03: ~dx_build_exe.py auf V1.04.01.00 (Anpassungen an neue python-Libs: Alle übergegebene Dir's werden in abspath umgewandelt)
#  19.11.2019 dP: V2.12.00.03: ~bootloader.py auf V2.62.00.00
#  05.12.2019 dP: V2.13.00.00: ~ an Python3
#  17.12.2019 dP: V2.14.00.00: ~bootloader.py V2.63.00.00 +use_sdo_only Argument (wird bei dem Firmwarekonverter (mcConvertFirmware) benutzt)
#  10.02.2020 dP: V2.15.00.00: +"if __package:" in Modulen, damit kann man die Module direkt in Source-Verzeichnis testen
#  10.02.2020 dP: V2.15.00.01: +cmdutil.GetTerminalSize()
#  21.02.2020 dP: V2.16.00.00: Release (noch ohne dx_app.py)
#  05.05.2020 dP: V2.17.00.00: Release (noch ohne dx_app.py), neue foc.py 1.00.00.03 mit "FocException", "FocDiag", "FocReference"
#  18.06.2020 dP: V2.18.00.00: Release (noch ohne dx_app.py), neue foc.py 1.01.00.00, "FocReference" ist OK
#  18.06.2020 dP: V2.18.01.00: ! für i18n-Translation
#  23.06.2020 dP: V2.18.02.00: ~ dbak.py 1.29.00.00
#  23.06.2020 dP: V2.18.03.00: ~ dbak.py 1.30.00.00
#  23.06.2020 dP: V2.18.04.00: ~ dbak.py 1.31.00.00
#  01.07.2020 dP: V2.18.05.00: ~ dx_dbg.py, dx_error.py
#  25.08.2020 dP: V2.18.06.00: + dx_error.py, dx_dbg.py, dx_txtout.py
#  28.10.2020 dP: V2.18.06.00: ~ dbak.py V1.32.00.00
#  29.10.2020 dP: V2.19.00.00: ~cmdutil.py: Exec wurde in ExecCmd umbennant. ExecCmd wurde um env-Parameter erweitert.
#  30.10.2020 dP: V2.19.01.00: ~dbak.py V1.33.00.00. !util.GetExecPath !util.GetResourcePath()
#  06.11.2020 dP: V2.20.00.01: Anpassungen an Python3.8
#  24.11.2020 dP: V2.20.01.00: Anpassungen an Python3.8
#  25.11.2020 dP: V2.20.02.00: !foc.ControlWrAccess, +foc.ControlUnits
#  30.11.2020 dP: V2.20.03.00: ~dx_build_exe.py (an Py3.8 angepasst), ~dbak.py (colored output), !display.py, !mPLC.py, !bootloader.py
#  15.12.2020 dP: V2.20.04.00: !mpu_asm.py !mpu2_asm.py
#  15.02.2021 dP: V2.20.05.00: ~foc.py V1.00.00.04
#
#==================================================================================================================================

Version       = (2,0x20, 0x05,0x00)
VersionString = "%X.%02X.%02X.%02X" % Version
