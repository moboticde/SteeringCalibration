# -*- coding: utf-8 -*-
#=================================================================================================================================#
#                                                                      Copyright (c) 1997-2020 by miControl. All rights reserved. #
# File     : dsa_par.py                                                                                                           #
#                                                                                                                                 #
# Project  :                                                                                                                      #
# System   : Python                                                                                                               #
# Version  : (see PAR_DSA_Version)                                                                                                #
# Customer :                                                                                                                      #
# Company  : miControl                                                                                                            #
#                                                                                                                                 #
# Author   : miControl Development Team                                                                                           #
# Team     : dariusz Parma (dP)  mailto:dp@miControl.de                                                                           #
# Date     : 18.02.2003                                                                                                           #
#=================================================================================================================================#
# Brief:    Parameters of miControl DSA-Devices
#
#----------------------------------------------------------------------------------------------------------------------------------
# History:                                                  (Symbol legend: + Added, - Removed, ~ Changed, ! Correction, # Comment)
#
#==================================================================================================================================
PAR_DSA_Version                     =  0x0136

# Parameter                                       RO-Read Only, WO-Write Only, RW-Read & Write
#
PAR_DEV_Class                       =  0x00
PAR_DEV_Cmd                         =  0x0000   #*WO
PAR_DEV_ErrorReg                    =  0x0001   #*RO
PAR_DEV_StatusReg                   =  0x0002   #*RO
PAR_DEV_Mode                        =  0x0003   #*RW default: MODE_VEL
PAR_DEV_Enable                      =  0x0004   #*RW default: 1, (ENABLE = *PAR_DEV_Enable && *PAR_DEV_DinEnable)

PAR_DEV_Code                        =  0x0020   #*RO

PAR_DEV_VersionSw                   =  0x0023   #*RO
PAR_DEV_VersionHw                   =  0x0024   #*RO

PAR_DEV_MaxUp                       =  0x0031   #*RO
PAR_DEV_MaxIm                       =  0x0032   #*RO

PAR_DEV_DinEnable                   =  0x0050   #*RW default: 0 -ohne Funktion
PAR_DEV_DinErrorClear               =  0x0051   #*RW default: 0 -ohne Funktion
PAR_DEV_DinStartStop                =  0x0052   #*RW default: 0 -ohne Funktion

PAR_DEV_DinHwLimitPos               =  0x0055   #*RW default: 0 -ohne Funktion
PAR_DEV_DinHwLimitNeg               =  0x0056   #*RW default: 0 -ohne Funktion

PAR_DEV_DoutError                   =  0x0060   #*RW default: 0 -ohne Function

PAR_DEV_HwLimitMode                 =  0x0080   #*RW

PAR_IO_Class                        =  0x01
PAR_IO_BASE                         =  0x0100
PAR_IO_AIN0                         =  0x0100   #*RO AINx - externe Eingänge
PAR_IO_AIN1                         =  0x0101   #*RO
PAR_IO_AIN2                         =  0x0102   #*RO
PAR_IO_AIN3                         =  0x0103   #*RO

PAR_IO_AIN_VOLTAGE_Ue               =  0x0110   #*RO [mV] Ue=+24V für Elektronik
PAR_IO_AIN_VOLTAGE_Up               =  0x0111   #*RO [mV] Up=+XXV für Leistung
PAR_IO_AIN_VOLTAGE_Um               =  0x0112   #*RO [mV]
PAR_IO_AIN_CURRENT_Im               =  0x0113   #*RO [mA]
PAR_IO_AIN_TEMP                     =  0x0114   #*RO [0.1°C]
PAR_IO_AIN_Trim0                    =  0x0115   #*RO [-1000..+1000]
PAR_IO_AIN_Trim1                    =  0x0116   #*RO [-1000..+1000]
PAR_IO_AIN_Trim2                    =  0x0117   #*RO [-1000..+1000]
PAR_IO_AIN_Trim3                    =  0x0118   #*RO [-1000..+1000]
PAR_IO_AIN_Trim4                    =  0x0119   #*RO [-1000..+1000]
PAR_IO_AIN_Trim5                    =  0x011A   #*RO [-1000..+1000]

PAR_IO_DIN_P0                       =  0x0120   #*RO Port (8-Bit)
PAR_IO_DIN_Hall                     =  0x0128   #*RO
PAR_IO_DIN_DipSwitch                =  0x0129   #*RO

PAR_IO_DOUT_P0                      =  0x0150   #*WO Port (8-Bit)
#
#
PAR_CURR_Class                      =  0x02
PAR_CURR_DesValue                   =  0x0200   #*RW  (Desired Value)
PAR_CURR_DesValue_Source            =  0x0204   #*RW

PAR_CURR_Pi_Kp                      =  0x0210   #*RW
PAR_CURR_Pi_Ki                      =  0x0211   #*RW

PAR_CURR_LimitMaxPos                =  0x0221   #*RW maximaler Strom Positiv
PAR_CURR_LimitMaxNeg                =  0x0223   #*RW maximaler Strom Negativ

PAR_CURR_ActualCurr                 =  0x0262   #*RO
#
#
PAR_VEL_Class                       =  0x03
PAR_VEL_DesValue                    =  0x0300   #*RW
PAR_VEL_DesValue_ScaleNum           =  0x0302   #*RW   Wirkt nur auf Soll- und Istwerte (alle Ausgangswerte)
PAR_VEL_DesValue_ScaleDen           =  0x0303   #*RW
PAR_VEL_DesValue_Source             =  0x0304   #*RW
PAR_VEL_DesValue_Reference          =  0x0305   #*RW   Bezugswert für Analogeneingang

PAR_VEL_DimensionNum                =  0x030A   #*RW - Numerator       Wirkt auf alle Werte
PAR_VEL_DimensionDen                =  0x030B   #*RW - Denominator

PAR_VEL_Pid_Kp                      =  0x0310   #*RW
PAR_VEL_Pid_Ki                      =  0x0311   #*RW
PAR_VEL_Pid_Kd                      =  0x0312   #*RW
PAR_VEL_Pid_KIxR                    =  0x0317   #*RW [0..1000]

PAR_VEL_LimitMaxPos                 =  0x0321   #*RW default:  30000 rpm
PAR_VEL_LimitMaxNeg                 =  0x0323   #*RW default:  30000 rpm

PAR_VEL_Acc_dV                      =  0x0340   #*RW
PAR_VEL_Acc_dT                      =  0x0341   #*RW
PAR_VEL_Dec_dV                      =  0x0342   #*RW
PAR_VEL_Dec_dT                      =  0x0343   #*RW
PAR_VEL_Dec_QuickStop_dV            =  0x0344   #*RW
PAR_VEL_Dec_QuickStop_dT            =  0x0345   #*RW
PAR_VEL_RampType                    =  0x034C   #*RW 0-NoRamp, 1-Trapez (default), ....
PAR_VEL_RampState                   =  0x034D   #*RO

PAR_VEL_Feedback                    =  0x0350   #*RW 0-Automatic (DC: EMK, BLDC: Hall)
#
#
PAR_PWM_Class                       =  0x05
PAR_PWM_DesValue                    =  0x0500   #*RW
PAR_PWM_DesValue_ScaleNum           =  0x0502   #*RW
PAR_PWM_DesValue_ScaleDen           =  0x0503   #*RW
PAR_PWM_DesValue_Source             =  0x0504   #*RW

PAR_PWM_Pid_Kp                      =  0x0510   #*RW
PAR_PWM_Pid_Ki                      =  0x0511   #*RW
#
# Diese Funktinen/Parameter bnutzen die VEL_Parameter
#
PAR_VPOS_Class                      =  0x07

PAR_VPOS_FollowingErrorWin_Error    =  0x0732   #*RW es ist PAR_VPOS_ActualFollowingError, bei deren Überschreitung ein Error ausgegeben wird

PAR_VPOS_RampState                  =  0x074D   #*RO

PAR_VPOS_ActualComandPosition       =  0x0761   #*RO
PAR_VPOS_ActualPosition             =  0x0762   #*RW
PAR_VPOS_ActualFollowingError       =  0x0763   #*RO

PAR_VPOS_MovA                       =  0x0790   #*WO = PAR_POS_DesValue + PAR_POS_Cmd-MOVA
PAR_VPOS_MovR                       =  0x0791   #*WO = PAR_POS_DesValue + PAR_POS_Cmd-MOVR
#
#
PAR_REG_Class                       =  0x08
PAR_REG_CURR_SampleTime             =  0x0800   #*RO in [us]
PAR_REG_CURR_SamplePoint            =  0x0801   #*RW in [100ns]  bestimmt der Zeitpunkt der Stromabtastung
PAR_REG_VEL_SampleTime              =  0x0810   #*RO in [us]
PAR_REG_PwmFreq                     =  0x0830   #*RO in [Hz]
#
#
PAR_MOT_Class                       =  0x09
PAR_MOT_Type                        =  0x0900   #*RW 0=DC, 1=BLDC
PAR_MOT_Nn                          =  0x0901   #*RW Nenndrehzahn
PAR_MOT_Un                          =  0x0902   #*RW Nennspannung
#
PAR_MOT_PolN                        =  0x0910   #*RW Polanzahl (=Polpaaranzahl*2)
PAR_MOT_Polarity                    =  0x0911   #*RW Bitweise (siehe BIT_MOT_POLARITY_xxx)

PAR_MOT_HALL_Type                   =  0x0940   #*RW 0=120, 1=60
PAR_MOT_HALL_ActualPosition         =  0x094A   #*RO

PAR_MOT_ENC2_Resolution_Cnt         =  0x0962   #*RW [counts] = (PAR_MOT_ENC2_Resolution_Line*4)
PAR_MOT_ENC2_ActualPosition         =  0x096A   #*RO [counts]
#
#
PAR_DIAG_EchoRegister               =  0x0FFF   #*RW

# Commands (PAR_DEV_Cmd)
#
PAR_CMD_NOP                         =  0x00
PAR_CMD_ClearError                  =  0x01
PAR_CMD_QuickStop                   =  0x02
PAR_CMD_Halt                        =  0x03
PAR_CMD_Continue                    =  0x04     # nach Halt oder QuickStop
#
PAR_CMD_StoreParam                  =  0x80
PAR_CMD_RestoreParam                =  0x81
PAR_CMD_DefaultParam                =  0x82
PAR_CMD_ClearParam                  =  0x83     #(Default + Save)

# Bits of Device Status
#
BIT_DEV_STAT_Enable                 =  (1 <<  0) #*
BIT_DEV_STAT_Error                  =  (1 <<  1) #*
BIT_DEV_STAT_Warning                =  (1 <<  2) #*
BIT_DEV_STAT_Moving                 =  (1 <<  3) #*
BIT_DEV_STAT_Reached                =  (1 <<  4) #*
BIT_DEV_STAT_Limit                  =  (1 <<  5) #*
BIT_DEV_STAT_HomeOK                 =  (1 <<  6)
BIT_DEV_STAT_SynchOK                =  (1 <<  7)
#
BIT_DEV_STAT_RampConst              =  (1 <<  9) # Vel=constant und nicht null
BIT_DEV_STAT_LimitCurrent           =  (1 << 12)
BIT_DEV_STAT_LimitVel               =  (1 << 13)
BIT_DEV_STAT_LimitPos               =  (1 << 14)
BIT_DEV_STAT_LimitPwm               =  (1 << 15)

# Mode (PAR_DEV_Mode)
#
MODE_OFF                            =  0
MODE_CURRENT                        =  2  # 2 - wie 0x200 Gruppe
MODE_VEL                            =  3  # 3 - wie 0x300 Gruppe
MODE_POS                            =  4  # 4 - wie 0x400 Gruppe
MODE_PWM                            =  5  # 5 - wie 0x500 Gruppe (PWM -> Spannungssteller)
MODE_Reserved                       =  6
MODE_VPOS                           =  7  # 7 - wie 0x700 Gruppe - Positionierung, die die Parameter vom VEL benutzt

# Polarity bits (PAR_MOT_Polarity)
#
BIT_MOT_POLARITY_PWM                =  (1<<0)
BIT_MOT_POLARITY_HALL               =  (1<<1)
BIT_MOT_POLARITY_ENC1               =  (1<<2)
BIT_MOT_POLARITY_ENC2               =  (1<<3)

# Ramp States
#
RS_DirNeg                           =  0x80
RS_Dec                              =  0x04
RS_Const                            =  0x02
RS_Acc                              =  0x01

# Motor Type (PAR_MOT_Type)
#
MOTOR_TYPE_DC                       =  0  # Brush     DC - Motor
MOTOR_TYPE_BLDC                     =  1  # Brushless DC - Motor
