# -*- coding: utf-8 -*-
#=================================================================================================================================#
#                                                                      Copyright (c) 1997-2020 by miControl. All rights reserved. #
# File     : ds402.py                                                                                                             #
#                                                                                                                                 #
# Project  :                                                                                                                      #
# System   : Python                                                                                                               #
# Version  : (see self.ClassVersion)                                                                                              #
# Customer :                                                                                                                      #
# Company  : miControl                                                                                                            #
#                                                                                                                                 #
# Author   : miControl Development Team                                                                                           #
# Team     : dariusz Parma (dP)  mailto:dp@miControl.de                                                                           #
# Date     : 11.12.2004                                                                                                           #
#=================================================================================================================================#
# Brief:    Ds402 class for CANopen miControl DSA-Devices
#
#----------------------------------------------------------------------------------------------------------------------------------
# History:                                                  (Symbol legend: + Added, - Removed, ~ Changed, ! Correction, # Comment)
#
#==================================================================================================================================
if __package__:
   from .ds301 import Ds301
else:
   from  ds301 import Ds301

__all__ = ["Ds402","ds402"]

#==================================================================================================================================
class Ds402 (Ds301):

   ClassVersion = (1,0x01, 0x00,0x00)

   # DS402 Objects ----------------------------------------------------------------------------------------------------------------

   # COMMON ENTRIES
   def AbortConnectionOptCode (self, val=None):    return self.Sdo(0x6007,0, val)            # *O  (ab 1.71.00.05)
   # ErrorCode                                     0x603F
   def MotorType              (self, val=None):    return self.Sdo(0x6402,0, val)            # *O
   # MotorCatalogNumber                            0x6403
   # MotorManufacturer                             0x6404
   # HttpMotorCatalogAddress                       0x6405
   # MotorCalibrationDate                          0x6406
   # MotorServicePeriod                            0x6407
   # MotorData                                     0x6410
   def SupportedDriveModes    (self):              return self.SdoRd(0x6502,0)               # *O
   # DriveCatalogNumber                            0x6503
   # DriveManufacturer                             0x6504
   # HttpDriveCatalogAddress                       0x6505
   # DriveData                                     0x6510
   def DigitalInputs          (self):              return self.SdoRd(0x60FD,0)               # Bits32..16 wurden benutzt
   def DigitalOutputs         (self, val=None):    return self.Sdo  (0x60FE,0, val)          # Bits32..16 wurden benutzt

   # DEVICE CONTROL
   def ControlWord            (self, val=None):    return self.Sdo  (0x6040,0, val)
   def StatusWord             (self):              return self.SdoRd(0x6041,0)
   # ShutdownOptionCode                            0x605B
   # DisableOperationOptionCode                    0x605C
   # QuickStopOptionCode                           0x605A
   # HaltOptionCode                                0x605D
   # FaultReactionOptionCode                       0x605E
   def ModesOfOperation       (self, val=None):    return self.Sdo  (0x6060,0, val)          # *M
   def ModesOfOperationDisplay(self):              return self.SdoRd(0x6061,0)               # *M

   # FACTOR GROUP
   def FctPosNotationIndex    (self, val=None):    return self.Sdo(0x6089,0, val)            # *C
   def FctPosDimIndex         (self, val=None):    return self.Sdo(0x608A,0, val)            # *C
   def FctVelNotationIndex    (self, val=None):    return self.Sdo(0x608B,0, val)            # *C
   def FctVelDimIndex         (self, val=None):    return self.Sdo(0x608C,0, val)            # *C
   def FctAccNotationIndex    (self, val=None):    return self.Sdo(0x608D,0, val)            # *C
   def FctAccDimIndex         (self, val=None):    return self.Sdo(0x608E,0, val)            # *C
   def FctPosEncoderResolution(self, val=None):    return self.SdoFraction(0x608F,1, val)    # *O  val = [encoder_increments, motor_revolutions]
   def FctVelEncoderResolution(self, val=None):    return self.SdoFraction(0x6090,1, val)    # *O  val = [encoder_increments, motor_revolutions]
   def FctGearRatio           (self, val=None):    return self.SdoFraction(0x6091,1, val)    # *O  val = [motor_revolutions,  shaft_revolutions]
   def FctFeedConstant        (self, val=None):    return self.SdoFraction(0x6092,1, val)    # *O  val = [feed,               shaft_revolutions]
   # FctPosFactor                                  0x6093   //-O
   # FctVelEncoderFactor                           0x6094   //-O
   # FctVelFactor1                                 0x6095   //-O
   # FctVelFactor2                                 0x6096   //-O
   # FctAccFactor                                  0x6097   //-O
   def FctPolarity            (self, val=None):    return self.Sdo(0x607E,0, val)            # *O

   # PROFILE POSITION MODE
   def TargetPos              (self, val=None):    return self.Sdo(0x607A,0, val)            # *M
   # PositionRangeLimit                            0x607B
   def PosLimitMin            (self, val=None):    return self.Sdo(0x607D,1, val)            # *O  (ab V1.68)
   def PosLimitMax            (self, val=None):    return self.Sdo(0x607D,2, val)            # *O  (ab V1.68)
   def MaxProfileVel          (self, val=None):    return self.Sdo(0x607F,0, val)            # *O
   # MaxMotorSpeed                                 0x6080
   def ProfileVel             (self, val=None):    return self.Sdo(0x6081,0, val)            # *M
   # EndVelocity                                   0x6082
   def ProfileAcc             (self, val=None):    return self.Sdo(0x6083,0, val)            # *M
   def ProfileDec             (self, val=None):    return self.Sdo(0x6084,0, val)            # *O
   def QuickStopDec           (self, val=None):    return self.Sdo(0x6085,0, val)            # *O
   def MotionProfileType      (self, val=None):    return self.Sdo(0x6086,0, val)            # *M  (ab V1.69)
   # MaxAcc                                        0x60C5
   # MaxDec                                        0x60C6

   # HOMING MODE
   def HomeOffset             (self, val=None):    return self.Sdo(0x607C,0, val)            # *O  (ab V1.69)
   def HomeMethod             (self, val=None):    return self.Sdo(0x6098,0, val)            # *M  (ab V1.69)
   def HomeVelSwitch          (self, val=None):    return self.Sdo(0x6099,1, val)            # *M  (ab V1.69)
   def HomeVelZero            (self, val=None):    return self.Sdo(0x6099,2, val)            # *M  (ab V1.69)
   def HomeAcc                (self, val=None):    return self.Sdo(0x609A,0, val)            # *O  (ab V1.69)

   # POSITION CONTROL FUNCTION
   def PosDemandValue         (self, val=None):    return self.Sdo  (0x6062,0, val)          # *O
   def PosActualValue_cnt     (self):              return self.SdoRd(0x6063,0)               # *O in [counts]
   def PosActualValue         (self):              return self.SdoRd(0x6064,0)               # *M
   def FollowingErrorWindow   (self, val=None):    return self.Sdo  (0x6065,0, val)          # *O
   #FollowingErrorTimeout                          0x6066
   def PosWindow              (self, val=None):    return self.Sdo  (0x6067,0, val)          # *O
   def PosWindowTime          (self, val=None):    return self.Sdo  (0x6068,0, val)          # *O
   def FollowingErrorActualVal(self):              return self.SdoRd(0x60F4,0)               # *O  (ab V1.68)
   #ControlEffort                                  0x60FA
   #PositionControlParameterSet                    0x60FB
   def PositionDemandValue_cnt(self):              return self.SdoRd(0x60FC,0)               # *O  (ab V1.68)
   #
   # DSA - Compatible functions
   def CmdPos                 (self, val=None):    return self.Sdo  (0x6062,0, val)          # *O              == PosDemandValue
   def ActPos_cnt             (self):              return self.SdoRd(0x6063,0)               # *O in [counts]  == PosActualValue_cnt
   def ActPos                 (self):              return self.SdoRd(0x6064,0)               # *M              == PosActualValue
   def ActPosFollowingError   (self):              return self.SdoRd(0x60F4,0)               # *O  (ab V1.68)  == FollowingErrorActualVal

   # INTERPOLATED POSITION MODE
   # InterpolationSubModeSelect                    0x60C0
   # InterpolationDataRecord                       0x60C1
   # InterpolationTimePeriod                       0x60C2
   # InterpolationSyncDefinition                   0x60C3
   # InterpolationDataConfiguration                0x60C4

   # PROFILE VELOCITY MODE
   # VelSensorActualValue                          0x6069   //-M
   # SensorSelectionCode                           0x606A   //!O  *** ersetzt durch DSA-Parameter ***
   # VelDemandValue                                0x606B   //-M
   # VelActualValue                                0x606C   //-M
   # VelWindow                                     0x606D
   # VelWindowTime                                 0x606E
   # VelThreshold                                  0x606F
   # VelThresholdTime                              0x6070
   # TargetVel                                     0x60FF   //-M
   # MaxSlippage                                   0x60F8
   # VelControlParameterSet                        0x60F9

   # PROFILE TORQUE MODE
   def TargetTorque           (self, val=None):    return self.Sdo  (0x6071,0, val)          # *M
   def MaxTorque              (self, val=None):    return self.Sdo  (0x6072,0, val)          # *O
   # MaxCurrent                                    0x6073   //!O  *** ersetzt durch DSA-Parameter ***
   # TorqueDemandValue                             0x6074
   def MotorRatedCurrent      (self, val=None):    return self.Sdo  (0x6075,0, val)          # *O
   # MotorRatedTorque                              0x6076
   def TorqueActualValue      (self):              return self.SdoRd(0x6077,0)               # *O
   def CurrentActualValue     (self):              return self.SdoRd(0x6078,0)               # *O
   def DC_LinkCircuitVoltage  (self):              return self.SdoRd(0x6079,0)               # *O
   def TorqueSlope            (self, val=None):    return self.Sdo  (0x6087,0, val)          # *M  mcDefaultwert=0xFFFFFFFF, nach DS402 soll es 0 sein
   def TorqueProfileType      (self, val=None):    return self.Sdo  (0x6088,0, val)          # *M
   # PowerStageParameters                          0x60F7
   # TorqueControlParameters                       0x60F6

   # VELOCITY MODE
   def Vl_TargetVel           (self, val=None):    return self.Sdo(0x6042,0, val)            # *M
   # Vl_VelDemand                                  0x6043   // M !!!z.Z. nicht implementiert
   # Vl_ControlEffort                              0x6044   // M !!!z.Z. nicht implementiert
   # Vl_ManipulatedVel                             0x6045
   def Vl_VelAmountMin        (self, val=None):    return self.Sdo(0x6046,1, val)            # *M
   def Vl_VelAmountMax        (self, val=None):    return self.Sdo(0x6046,2, val)            # *M
   # Vl_VelMinMax                                  0x6047
   def Vl_VelAcc              (self, val=None):    return self.SdoFraction(0x6048,1, val)    # *M  val=[delta_speed_rpm, delta_time_sec]
   def Vl_VelDec              (self, val=None):    return self.SdoFraction(0x6049,1, val)    # *M  val=[delta_speed_rpm, delta_time_sec]
   def Vl_VelQuickStop        (self, val=None):    return self.SdoFraction(0x604A,1, val)    # *O  val=[delta_speed_rpm, delta_time_sec]
   # Vl_SetPointFactor                             0x604B
   def Vl_VelDimFactor        (self, val=None):    return self.SdoFraction(0x604C,1, val)    # *O
   # Vl_PoleNumber                                 0x604D   //!O  *** ersetzt durch DSA-Parameter ***
   # Vl_VelReference                               0x604E
   # Vl_RampFunctionTime                           0x604F
   # Vl_SlowDownTime                               0x6050
   # Vl_QuickStopTime                              0x6051
   # Vl_NominalPercentage                          0x6052
   # Vl_PercentageDemand                           0x6053
   # Vl_ActualPercentage                           0x6054
   # Vl_ManipulatedPercentage                      0x6055
   # Vl_VelMotorMinMaxAmount                       0x6056
   # Vl_VelMotorMinMax                             0x6057
   # Vl_FrequencyMotorMinMaxAmount                 0x6058
   # Vl_FrequencyMotorMinMax                       0x6059

   # StatusWord - States
   #
   def _get_status_word (self, sw_val=None):
      if sw_val is None:
         return self.StatusWord()
      else:
         return sw_val

   def _check_status_word (self, sw_val, mask, val):
      sw = self._get_status_word(sw_val)
      if (sw & mask) == val:
         return True
      else:
         return False                                                                                          # 1111 11
                                                                                                               # 5432 1098 7654 3210
   def IsNotReadyToSwitchOn   (self, sw_val=None):    return self._check_status_word(sw_val, 0x004F, 0x0000)   # xxxx xxxx x0xx 0000 Not ready to switch on
   def IsSwitchOnDisabled     (self, sw_val=None):    return self._check_status_word(sw_val, 0x004F, 0x0040)   # xxxx xxxx x1xx 0000 Switch on disabled
   def IsReadyToSwitchOn      (self, sw_val=None):    return self._check_status_word(sw_val, 0x006F, 0x0021)   # xxxx xxxx x01x 0001 Ready to switch on
   def IsSwitchedOn           (self, sw_val=None):    return self._check_status_word(sw_val, 0x006F, 0x0023)   # xxxx xxxx x01x 0011 Switched on
   def IsOperationEnabled     (self, sw_val=None):    return self._check_status_word(sw_val, 0x006F, 0x0027)   # xxxx xxxx x01x 0111 Operation enabled
   def IsQuickStopActive      (self, sw_val=None):    return self._check_status_word(sw_val, 0x006F, 0x0007)   # xxxx xxxx x00x 0111 Quick stop active
   def IsFaultReactionActive  (self, sw_val=None):    return self._check_status_word(sw_val, 0x004F, 0x000F)   # xxxx xxxx x0xx 1111 Fault reaction active
   def IsFault                (self, sw_val=None):    return self._check_status_word(sw_val, 0x004F, 0x0008)   # xxxx xxxx x0xx 1000 Fault

   def GetStateText (self, sw_val=None):
      sw = self._get_status_word(sw_val)

      if   self.IsNotReadyToSwitchOn(sw)  :  s = "not ready to switch on"
      elif self.IsSwitchOnDisabled(sw)    :  s = "switch on disabled"
      elif self.IsReadyToSwitchOn(sw)     :  s = "ready to switch on"
      elif self.IsSwitchedOn(sw)          :  s = "switched on"
      elif self.IsOperationEnabled(sw)    :  s = "operation enabled"
      elif self.IsQuickStopActive(sw)     :  s = "quick stop active"
      elif self.IsFaultReactionActive(sw) :  s = "fault reaction active"
      elif self.IsFault(sw)               :  s = "fault"
      else                                :  s = "unknown state (%04Xh)" % (sw)

      return s

   # Unit-Dimensions for FACTOR GROUP
   #
   UNIT_DIM_None      = 0x00
   UNIT_DIM_Vel_rps   = 0xA3                 # [rev / sec]        (revolutions pro seconds)
   UNIT_DIM_Vel_rpm   = 0xA4                 # [rev / min]
   UNIT_DIM_Acc_rps2  = 0xAF                 # [rev / s^2]
   UNIT_DIM_Acc_rpm2  = 0xB0                 # [rev / min^2]
   UNIT_DIM_Acc_cps2  = 0xB2                 # [steps / s^2]   = [counts/s^2]
   UNIT_DIM_Acc_cpm2  = 0xB3                 # [steps / min^2] = [counts/min^2]
   UNIT_DIM_cpr       = 0xAD                 # [steps / rev]   = [counts/rev]
   UNIT_DIM_Pos_steps = 0xAC                 # [steps]
   UNIT_DIM_Pos_cnt   = UNIT_DIM_Pos_steps   # [counts]
   UNIT_DIM_Pos_rev   = 0xB4                 # [rev]

# for compatibility reason
ds402 = Ds402
