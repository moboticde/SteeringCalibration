# Script for rocker left unit
# Version - 2.17
HardwareVersion = 201         #change this value only when there is hardware revision from Mobotic
SoftwareVersion = 217               #change this value(version*100), when creating a new version

CurrentLeftID = 5           #Current Node ID for left unit

LeftNodeID = 5              #New Node ID for left unit

baudrate = 3                #New Baudrate for left and right unit
                            #0 - 1 Mbit/s
                            #1 - 800 kbit/s
                            #2 - 500 kbit/s
                            #3 - 250 kbit/s
                            #4 - 125 kbit/s
                            #5 - 100 kbit/s
                            #6 - 50 kbit/s
                            #7 - 20 kbit/s
                            #8 - 10 kbit/s


def Baudrate (d):
    d.SdoWr(0x2000, 0x01, 0x6E657277)               # write enable
    d.SdoWr(0x2000, 0x03, baudrate, timeout=500)    # set baud rate


def TractionLeftPar (d):

   d.SdoWr(0x2000, 0x01, 0x6E657277)               # write enable
   d.SdoWr(0x2000, 0x02, LeftNodeID, timeout=500) # set new NodeId

   d.SdoWr(0x3004, 0x00, 0)           # DEV_Enable - Disable
   d.SdoWr(0x3000, 0x00, 0x1)         # DEV_Cmd - Clear error
   d.SdoWr(0x3000, 0x00, 0x82)        # DEV_Cmd - Default parameter

   d.SdoWr(0x3060, 0x00, -0x160)      # DEV_DoutError

   d.SdoWr(0x3003, 0x00, 3)           # DEV_Mode
   d.SdoWr(0x3154, 0x00, 0xFB)        # IO_DOUT_Enable

   d.SdoWr(0x3200, 0x00, 0)           # CURR_DesiredValue

   d.SdoWr(0x3210, 0x00, 4)           # CURR_Kp
   d.SdoWr(0x3211, 0x00, 1)           # CURR_Ki

   d.SdoWr(0x3221, 0x00, 80000)      # CURR_LimitMaxPos
   d.SdoWr(0x3223, 0x00, 80000)      # CURR_LimitMaxNeg
   d.SdoWr(0x3224, 0x00, 1)           # CURR_DynLimitMode
   d.SdoWr(0x324C, 0x00, 0)           # CURR_RampType
   d.SdoWr(0x3224, 0x01, 80000)       # CURR_DynLimitPeak (Dynamische Strombegrenzung ist aktiviert)
   d.SdoWr(0x3224, 0x02, 40000)       # CURR_DynLimitCont (Dynamische Strombegrenzung ist aktiviert)
   d.SdoWr(0x3224, 0x03, 2000)        # CURR_DynLimitTime

   d.SdoWr(0x3300, 0x00, 0)           # VEL_DesiredValue
   d.SdoWr(0x3302, 0x00, 1)           # VEL_ScaleNum
   d.SdoWr(0x3303, 0x00, 1)           # VEL_ScaleDen
   d.SdoWr(0x330A, 0x00, -745)        # VEL_DimensionNum
   d.SdoWr(0x330B, 0x00, 1000)        # VEL_DimensionDen

   d.SdoWr(0x3310, 0x00, 0)           # VEL_Kp
   d.SdoWr(0x3311, 0x00, 0)           # VEL_Ki
   d.SdoWr(0x3312, 0x00, 0)           # VEL_Kd
   d.SdoWr(0x3313, 0x00, 10000)       # VEL_ILimit
   d.SdoWr(0x3314, 0x00, 1000)        # VEL_Kvff
   d.SdoWr(0x3315, 0x00, 300)         # VEL_Kaff
   d.SdoWr(0x3317, 0x00, 0)           # VEL_KIxR

   d.SdoWr(0x3321, 0x00, 2200)       # VEL_LimitMaxPos
   d.SdoWr(0x3323, 0x00, 2200)       # VEL_LimitMaxNeg

   d.SdoWr(0x3350, 0x00, 0x97A)       # VEL_Feedback
   d.SdoWr(0x3521, 0x00, 2200)        # SVEL_LimitMaxPos
   d.SdoWr(0x3523, 0x00, 2200)        # SVEL_LimitMaxNeg
   d.SdoWr(0x3500, 0x00, 0)           # SVEL_DesiredValue


   d.SdoWr(0x3502, 0x00, -745)        # SVEL_ScaleNum
   d.SdoWr(0x3503, 0x00, 1000)        # SVEL_ScaleDen

   d.SdoWr(0x3510, 0x00, 2800)        # SVEL_Kp
   d.SdoWr(0x3511, 0x00, 1600)        # SVEL_Ki

   d.SdoWr(0x3550, 0x00, 0x97A)       # SVEL_Feedback

   d.SdoWr(0x3732, 0x00, 4294967295)  # POS_FollowingErrorWindow
   d.SdoWr(0x373C, 0x00, 0x8)         # POS_ReachedConfigFlags

   d.SdoWr(0x39A0, 0x00, 3)           # MOTOR_BrakeManagement_Config
   d.SdoWr(0x39A0, 0x08, -0x162)      # MOTOR_BrakeManagement_Dout
   d.SdoWr(0x39A0, 0x11, 100)         # MOTOR_BrakeManagement_OffDelay2
   d.SdoWr(0x39A0, 0x13, 100)         # MOTOR_BrakeManagement_OnDelay2
   d.SdoWr(0x39A0, 0x18, 5)           # MOTOR_BrakeManagement_OffOrConditionFlags
   d.SdoWr(0x39A0, 0x1A, 12)          # MOTOR_BrakeManagement_OnOrConditionFlags
   d.SdoWr(0x39A0, 0x40, 60)          # MOTOR_BrakeManagement_CurrentControl_PWM
   d.SdoWr(0x39A0, 0x42, 3000)        # MOTOR_BrakeMana..._CurrentControl_Time_ms

   #______ekr parameters______
   d.SdoWr(0x3059, 0x00, 305)         # PAR_3059.00h
   d.SdoWr(0x3A02, 0x00, 20)          # Measurement_VelTime_ms (default: 100)
   d.SdoWr(0x3080, 0x00, 4)           # DEV_ContinueMode (4 = automatic after quick stop)

   #MOBOTIC parameters
   d.SdoWr(0x3900, 0x00, 1)           # MOTOR_Type
   d.SdoWr(0x3901, 0x00, 1550)        # MOTOR_Nn
   d.SdoWr(0x3902, 0x00, 48000)       # MOTOR_Un

   d.SdoWr(0x3910, 0x00, 20)          # MOTOR_PolN
   d.SdoWr(0x3911, 0x00, 0)           # MOTOR_Polarity

   d.SdoWr(0x3962, 0x00, 4096)        # MOTOR_ENC_Resolution

   d.SdoWr(0x3970, 0x00, 1)           # MOTOR_ENC_SSI_Enable
   d.SdoWr(0x3971, 0x01, 12)          # MOTOR_ENC_SSI_SignificantBits
   d.SdoWr(0x3971, 0x02, 15)          # MOTOR_ENC_SSI_Bits
   d.SdoWr(0x3972, 0x00, 4096)        # MOTOR_ENC_SSI_Resolution
   #d.SdoWr(0x397F, 0x08, 238)         # MOT_ENC_SSI_ReferencePos

   d.SdoWr(0x3913, 0x07, 0)           # MOTOR_Commutation_Polarity
   d.SdoWr(0x3913, 0x84, 2426)        # PAR_3913.84h

   d.SdoWr(0x3971, 0x00, 1)           # MOTOR_ENC_SSI_Code
   d.SdoWr(0x3971, 0x03, 0)           # PAR_3971.03h

   d.SdoWr(0x3913, 0x11, 0)           # MOTOR_Commutation_ReferencingMode
   d.SdoWr(0x3059, 0x05, 3)           # PAR_3059.05h (is needed for the hardware quickstop to work properly)

   #password to access 302E parameters
   d.SdoWr(0x302E, 0, 0x00000000)  # DEV_OemData_Cmd - reset - enter old password
   d.SdoWr(0x302E, 0, 0x00010000)  # DEV_OemData_Cmd - enter password - word0
   d.SdoWr(0x302E, 0, 0x00010000)  # DEV_OemData_Cmd - enter password - word1
   d.SdoWr(0x302E, 0, 0x00010000)  # DEV_OemData_Cmd - enter password - word2
   d.SdoWr(0x302E, 0, 0x00010000)  # DEV_OemData_Cmd - enter password - word3
   #saving HW and SW version numbers
   d.SdoWr(0x302E, 1, HardwareVersion)  # DEV_OemData_D0 - enter data D0
   d.SdoWr(0x302E, 2, SoftwareVersion)  # DEV_OemData_D1 - enter data D1
   d.SdoWr(0x302E, 0, 0x00800000)  # DEV_OemData_Cmd - save data and password
   d.SdoWr(0x3000, 0x00, 0x80)        # DEV_Cmd - Store parameters

def TractionLeftCommPar (d):
   d.SdoWr(0x2011, 0x02, 1684107116)  # ...tion - Default parameter communication
   d.SdoWr(0x2011, 0x05, 1684107116)  # DS2000_RestoreD...000 - Default parameter

   d.SdoWr(0x1005, 0x00, 0x80)        # COP_CobId_Sync
   d.SdoWr(0x1006, 0x00, 20000)       # COP_CommunicationCyclePeriod
   d.SdoWr(0x100C, 0x00, 0)           # COP_GuardTime
   d.SdoWr(0x100D, 0x00, 0)           # COP_LifeTimeFactor
   d.SdoWr(0x100E, 0x00, 0x705)       # COP_CobId_Guarding

   d.SdoWr(0x1012, 0x00, 0x100)       # COP_CobId_TimeStampMessage
   #d.SdoWr(0x1014, 0x00, 0x85)        # COP_CobId_EmergencyMessage
   d.SdoWr(0x1016, 0x01, 8323372)     # COP_ConsumerHea..._ConsumerHeartbeatTime1
   d.SdoWr(0x1016, 0x02, 0)           # COP_ConsumerHea..._ConsumerHeartbeatTime2
   d.SdoWr(0x1016, 0x03, 0)           # COP_ConsumerHea..._ConsumerHeartbeatTime3
   d.SdoWr(0x1016, 0x04, 0)           # COP_ConsumerHea..._ConsumerHeartbeatTime4
   d.SdoWr(0x1017, 0x00, 200)         # COP_ProducerHeartbeatTime

   d.SdoWr(0x1029, 0x01, 0x0)         # COP_ErrorBehavior_CommunicationError

   d.SdoWr(0x1400, 0x01, 0x40000205)  # COP_RxPDO1_CommunicationParameter_CobId
   d.SdoWr(0x1400, 0x02, 0x1)         # COP_RxPDO1_Comm...ameter_TransmissionType
   d.SdoWr(0x1400, 0x03, 0)           # COP_RxPDO1_Comm...onParameter_InhibitTime
   d.SdoWr(0x1401, 0x01, 0x40000305)  # COP_RxPDO2_CommunicationParameter_CobId
   d.SdoWr(0x1401, 0x02, 0x1)         # COP_RxPDO2_Comm...ameter_TransmissionType
   d.SdoWr(0x1401, 0x03, 0)           # COP_RxPDO2_Comm...onParameter_InhibitTime
   d.SdoWr(0x1402, 0x01, 0x40000405)  # COP_RxPDO3_CommunicationParameter_CobId
   d.SdoWr(0x1402, 0x02, 0xFF)        # COP_RxPDO3_Comm...ameter_TransmissionType
   d.SdoWr(0x1402, 0x03, 0)           # COP_RxPDO3_Comm...onParameter_InhibitTime
   d.SdoWr(0x1403, 0x01, 0x40000505)  # COP_RxPDO4_CommunicationParameter_CobId
   d.SdoWr(0x1403, 0x02, 0xFF)        # COP_RxPDO4_Comm...ameter_TransmissionType
   d.SdoWr(0x1403, 0x03, 0)           # COP_RxPDO4_Comm...onParameter_InhibitTime
   d.SdoWr(0x1404, 0x01, 0xC0000000)  # COP_RxPDO5_CommunicationParameter_CobId
   d.SdoWr(0x1404, 0x02, 0xFF)        # COP_RxPDO5_Comm...ameter_TransmissionType
   d.SdoWr(0x1404, 0x03, 0)           # COP_RxPDO5_Comm...onParameter_InhibitTime
   d.SdoWr(0x1405, 0x01, 0xC0000000)  # COP_RxPDO6_CommunicationParameter_CobId
   d.SdoWr(0x1405, 0x02, 0xFF)        # COP_RxPDO6_Comm...ameter_TransmissionType
   d.SdoWr(0x1405, 0x03, 0)           # COP_RxPDO6_Comm...onParameter_InhibitTime
   d.SdoWr(0x1406, 0x01, 0xC0000000)  # COP_RxPDO7_CommunicationParameter_CobId
   d.SdoWr(0x1406, 0x02, 0xFF)        # COP_RxPDO7_Comm...ameter_TransmissionType
   d.SdoWr(0x1406, 0x03, 0)           # COP_RxPDO7_Comm...onParameter_InhibitTime

   d.SdoWr(0x1414, 0x01, 0xC0000000)  # COP_RxPDO21_CommunicationParameter_CobId
   d.SdoWr(0x1414, 0x02, 0xFF)        # COP_RxPDO21_Com...ameter_TransmissionType
   d.SdoWr(0x1414, 0x03, 0)           # COP_RxPDO21_Com...onParameter_InhibitTime

   d.SdoWr(0x1600, 0x00, 0x0)         # COP_RxPDO1_Mapp...appedApplicationObjects
   d.SdoWr(0x1600, 0x01, 0x60400010)  # COP_RxPDO1_Mapping_1ApplicationObject
   d.SdoWr(0x1600, 0x02, 0x60420010)  # COP_RxPDO1_Mapping_2ApplicationObject
   d.SdoWr(0x1600, 0x03, 0x60600008)  # COP_RxPDO1_Mapping_3ApplicationObject
   d.SdoWr(0x1600, 0x00, 0x3)         # COP_RxPDO1_Mapp...appedApplicationObjects
   d.SdoWr(0x1601, 0x00, 0x0)         # COP_RxPDO2_Mapp...appedApplicationObjects
   d.SdoWr(0x1601, 0x01, 0x35100010)  # COP_RxPDO2_Mapping_1ApplicationObject
   d.SdoWr(0x1601, 0x02, 0x35110010)  # COP_RxPDO2_Mapping_2ApplicationObject
   d.SdoWr(0x1601, 0x00, 0x2)         # COP_RxPDO2_Mapp...appedApplicationObjects
   d.SdoWr(0x1602, 0x00, 0x0)         # COP_RxPDO3_Mapp...appedApplicationObjects
   d.SdoWr(0x1603, 0x00, 0x0)         # COP_RxPDO4_Mapp...appedApplicationObjects
   d.SdoWr(0x1604, 0x00, 0x0)         # COP_RxPDO5_Mapp...appedApplicationObjects
   d.SdoWr(0x1605, 0x00, 0x0)         # COP_RxPDO6_Mapp...appedApplicationObjects
   d.SdoWr(0x1606, 0x00, 0x0)         # COP_RxPDO7_Mapp...appedApplicationObjects

   d.SdoWr(0x1614, 0x00, 0x0)         # COP_RxPDO21_Map...appedApplicationObjects

   d.SdoWr(0x1800, 0x01, 0x185)       # COP_TxPDO1_CommunicationParameter_CobId
   d.SdoWr(0x1800, 0x02, 0x1)         # COP_TxPDO1_Comm...ameter_TransmissionType
   d.SdoWr(0x1800, 0x03, 0)           # COP_TxPDO1_Comm...onParameter_InhibitTime
   d.SdoWr(0x1801, 0x01, 0x285)       # COP_TxPDO2_CommunicationParameter_CobId
   d.SdoWr(0x1801, 0x02, 0x1)         # COP_TxPDO2_Comm...ameter_TransmissionType
   d.SdoWr(0x1801, 0x03, 0)           # COP_TxPDO2_Comm...onParameter_InhibitTime
   d.SdoWr(0x1802, 0x01, 0x385)       # COP_TxPDO3_CommunicationParameter_CobId
   d.SdoWr(0x1802, 0x02, 0x1)         # COP_TxPDO3_Comm...ameter_TransmissionType
   d.SdoWr(0x1802, 0x03, 0)           # COP_TxPDO3_Comm...onParameter_InhibitTime
   d.SdoWr(0x1803, 0x01, 0x485)       # COP_TxPDO4_CommunicationParameter_CobId
   d.SdoWr(0x1803, 0x02, 0xFF)        # COP_TxPDO4_Comm...ameter_TransmissionType
   d.SdoWr(0x1803, 0x03, 0)           # COP_TxPDO4_Comm...onParameter_InhibitTime
   d.SdoWr(0x1804, 0x01, 0x80000000)  # COP_TxPDO5_CommunicationParameter_CobId
   d.SdoWr(0x1804, 0x02, 0xFF)        # COP_TxPDO5_Comm...ameter_TransmissionType
   d.SdoWr(0x1804, 0x03, 0)           # COP_TxPDO5_Comm...onParameter_InhibitTime
   d.SdoWr(0x1805, 0x01, 0x80000000)  # COP_TxPDO6_CommunicationParameter_CobId
   d.SdoWr(0x1805, 0x02, 0xFF)        # COP_TxPDO6_Comm...ameter_TransmissionType
   d.SdoWr(0x1805, 0x03, 0)           # COP_TxPDO6_Comm...onParameter_InhibitTime
   d.SdoWr(0x1806, 0x01, 0x80000000)  # COP_TxPDO7_CommunicationParameter_CobId
   d.SdoWr(0x1806, 0x02, 0xFF)        # COP_TxPDO7_Comm...ameter_TransmissionType
   d.SdoWr(0x1806, 0x03, 0)           # COP_TxPDO7_Comm...onParameter_InhibitTime

   d.SdoWr(0x1814, 0x01, 0x80000000)  # COP_TxPDO21_CommunicationParameter_CobId
   d.SdoWr(0x1814, 0x02, 0xFF)        # COP_TxPDO21_Com...ameter_TransmissionType
   d.SdoWr(0x1814, 0x03, 0)           # COP_TxPDO21_Com...onParameter_InhibitTime

   d.SdoWr(0x1A00, 0x00, 0x0)         # COP_TxPDO1_Mapp...appedApplicationObjects
   d.SdoWr(0x1A00, 0x01, 0x60410010)  # COP_TxPDO1_Mapping_1ApplicationObject
   d.SdoWr(0x1A00, 0x02, 0x3A040120)  # COP_TxPDO1_Mapping_2ApplicationObject
   d.SdoWr(0x1A00, 0x03, 0x60610008)  # COP_TxPDO1_Mapping_3ApplicationObject
   d.SdoWr(0x1A00, 0x00, 0x3)         # COP_TxPDO1_Mapp...appedApplicationObjects
   d.SdoWr(0x1A01, 0x00, 0x0)         # COP_TxPDO2_Mapp...appedApplicationObjects
   d.SdoWr(0x1A01, 0x01, 0x32620120)  # COP_TxPDO2_Mapping_1ApplicationObject
   d.SdoWr(0x1A01, 0x02, 0x31140010)  # COP_TxPDO2_Mapping_2ApplicationObject
   d.SdoWr(0x1A01, 0x00, 0x2)         # COP_TxPDO2_Mapp...appedApplicationObjects
   d.SdoWr(0x1A02, 0x00, 0x0)         # COP_TxPDO3_Mapp...appedApplicationObjects
   d.SdoWr(0x1A02, 0x01, 0x30010010)  # COP_TxPDO3_Mapping_1ApplicationObject
   d.SdoWr(0x1A02, 0x02, 0x31110020)  # COP_TxPDO3_Mapping_2ApplicationObject
   d.SdoWr(0x1A02, 0x00, 0x2)         # COP_TxPDO3_Mapp...appedApplicationObjects
   d.SdoWr(0x1A03, 0x00, 0x0)         # COP_TxPDO4_Mapp...appedApplicationObjects
   d.SdoWr(0x1A03, 0x01, 0x51010110)  # COP_TxPDO4_Mapping_1ApplicationObject
   d.SdoWr(0x1A03, 0x02, 0x31140310)  # COP_TxPDO4_Mapping_2ApplicationObject
   d.SdoWr(0x1A03, 0x00, 0x2)         # COP_TxPDO4_Mapp...appedApplicationObjects
   d.SdoWr(0x1A04, 0x00, 0x0)         # COP_TxPDO5_Mapp...appedApplicationObjects
   d.SdoWr(0x1A05, 0x00, 0x0)         # COP_TxPDO6_Mapp...appedApplicationObjects
   d.SdoWr(0x1A06, 0x00, 0x0)         # COP_TxPDO7_Mapp...appedApplicationObjects

   d.SdoWr(0x1A14, 0x00, 0x0)         # COP_TxPDO21_Map...appedApplicationObjects

   d.SdoWr(0x2000, 0x01, 0x6E657277)  # DS2000_CopConfigParam_WriteEnable
   d.SdoWr(0x2000, 0x04, 0)           # DS2000_CopConfigParam_AutoOperational
   d.SdoWr(0x2000, 0x01, 0x6E657277)  # DS2000_CopConfigParam_WriteEnable
   d.SdoWr(0x2000, 0x05, 1)           # DS2000_CopConfigParam_MessageOnBootup

   d.SdoWr(0x2021, 0x01, 0)           # DS2000_SyncProducer_Enable
   d.SdoWr(0x1010,0x02,0x65766173,timeout=21000)



#main
if __name__ == '__main__':
   from mc.dsa import *
   from mc.pymc import Run

   lu = Dsa(CurrentLeftID)         #steering node

   TractionLeftPar(lu)
   print("Traction parameters are uploaded for the left unit")
   TractionLeftCommPar(lu)
   print("traction communication settings are uploaded for the left unit")

   Baudrate(lu)
   print("Baudrate is changed for left unit")