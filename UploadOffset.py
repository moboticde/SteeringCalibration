import ctypes
from ctypes import c_uint8, c_uint32, c_bool, c_char_p, c_void_p, POINTER, byref
from pathlib import Path
from drivers.driver_miControlF35 import MicontrolF35_CAN
from drivers.driver_can import DriverCan
from drivers.driver_mc import DSACompat
from drivers.driver_cam_st import AngleDetection
from FlashSteeringScript import import_script_via_qr,load_config_function


DLL_PATH = Path(r"C:\Users\Lab\Documents\InternalProjects\SteeringCalibration\MU\MU_3SL_interface_3.4.1\bin\windows\x86-64\MU_3SL_interface_64.dll")
CONFIG_PATH = rb"C:\Users\Lab\Documents\miControl\OCE\from utrecht vehicle 18\ic-mu_steering_encoder_front.cfg"
mu = ctypes.CDLL(str(DLL_PATH))

MU_Handle = c_void_p
MU_Error  = c_uint32
MU_MB5U   = c_uint32(4)

# MU enums / constants
MU_PRES_POS  = c_uint32(68)
MU_OFF_POS   = c_uint32(57)
MU_CMD_SOFT_PRES = c_uint32(8)
MU_VERIFY    = c_uint32(2)
MU_E2P_CFG   = c_uint32(0)
MU_MODEA     = c_uint32(16)
MU_BISS      = c_uint32(0x02)
MU_SSI       = c_uint32(0x04)

class ReadSensStruct(ctypes.Structure):
    _fields_ = [
        ("mt",        c_uint32),
        ("st",        c_uint32),
        ("err",       c_uint32),
        ("warn",      c_uint32),
        ("rawMaster", c_uint32),
        ("rawNonius", c_uint32),
    ]

# ---- prototypes ----
mu.MU_Open.argtypes  = [POINTER(MU_Handle)]
mu.MU_Open.restype   = MU_Error
mu.MU_Close.argtypes = [MU_Handle]
mu.MU_Close.restype  = MU_Error

mu.MU_SetInterface.argtypes = [MU_Handle, c_uint32, c_char_p]
mu.MU_SetInterface.restype  = MU_Error

mu.MU_SetParam.argtypes = [MU_Handle, c_uint32, c_uint32, c_uint32, c_uint32]
mu.MU_SetParam.restype  = MU_Error

mu.MU_WriteParams.argtypes = [MU_Handle, c_bool, POINTER(c_bool)]
mu.MU_WriteParams.restype  = MU_Error

mu.MU_WriteEeprom.argtypes = [MU_Handle, c_uint32]
mu.MU_WriteEeprom.restype  = MU_Error

mu.MU_LoadParams.argtypes  = [MU_Handle, c_char_p]
mu.MU_LoadParams.restype   = MU_Error

mu.MU_CalcPRES_POS.argtypes = [MU_Handle, c_uint32, c_uint32, c_uint32]
mu.MU_CalcPRES_POS.restype  = MU_Error

mu.MU_SetConfig.argtypes = [MU_Handle, c_uint32, c_uint32]
mu.MU_SetConfig.restype  = MU_Error

mu.MU_GetConfig.argtypes = [MU_Handle, c_uint32, POINTER(c_uint32)]
mu.MU_GetConfig.restype  = MU_Error

mu.MU_WriteCmdRegister.argtypes = [MU_Handle, c_uint32]
mu.MU_WriteCmdRegister.restype  = MU_Error

# revision APIs
mu.MU_ReadChipRevision.argtypes = [MU_Handle, POINTER(c_uint8)]
mu.MU_ReadChipRevision.restype  = MU_Error

mu.MU_UseRevision.argtypes = [MU_Handle, c_uint8]
mu.MU_UseRevision.restype  = MU_Error

mu.MU_ValueOfUsedRevision.argtypes = [MU_Handle, POINTER(c_uint8)]
mu.MU_ValueOfUsedRevision.restype  = MU_Error

# BiSS + IO
mu.MU_SwitchToBiss.argtypes = [MU_Handle, POINTER(c_uint32), POINTER(c_bool)]
mu.MU_SwitchToBiss.restype  = MU_Error

mu.MU_Initialize.argtypes = [MU_Handle]
mu.MU_Initialize.restype  = MU_Error

mu.MU_ReadSens.argtypes = [MU_Handle, POINTER(ReadSensStruct)]
mu.MU_ReadSens.restype  = MU_Error

def load_cfg_to_encoder(handle):
    mu.MU_LoadParams(handle, CONFIG_PATH)

    valid = (c_bool * 128)()
    mu.MU_SetParam(handle, MU_MODEA, 0, MU_BISS, MU_VERIFY); print("Set BiSS")
    mu.MU_WriteParams(handle, True, valid);                   print("Write RAM (verify)")
    mu.MU_WriteEeprom(handle, MU_E2P_CFG);                    print("Write EEPROM")

    mu.MU_SetParam(handle, MU_MODEA, 0, MU_SSI, MU_VERIFY);   print("Set SSI")
    mu.MU_WriteEeprom(handle, MU_E2P_CFG);                    print("Write EEPROM")

def init_and_load_cfg(handle):

    rev = c_uint8(0)
    mu.MU_ReadChipRevision(handle, byref(rev));               
    mu.MU_UseRevision(handle, rev.value);                      

    cnt = c_uint32(0); mu.MU_GetConfig(handle, 8,  byref(cnt)); 
    val = c_uint32(0); mu.MU_GetConfig(handle, 17, byref(val)); 

    modea = c_uint32(0); switched = c_bool(False)
    mu.MU_SwitchToBiss(handle, byref(modea), byref(switched)); print("Switch to BiSS")

    mu.MU_Initialize(handle);                                  print("Initialize")

    mu.MU_SetConfig(handle, 12, 1);                           

    load_cfg_to_encoder(handle)

    #rs = ReadSensStruct()
    #mu.MU_ReadSens(handle, byref(rs));                         print(f"ST={rs.st}")

    # Set Single Turn to zero
    #mu.MU_SetParam(handle, MU_PRES_POS, 0, 0, MU_VERIFY);      print("Preset ST=0")
    mu.MU_WriteCmdRegister(handle, MU_CMD_SOFT_PRES);          print("Soft Preset")
    mu.MU_WriteEeprom(handle, MU_E2P_CFG);                    print("Write EEPROM")

def main(serial_last4: str = ""):
    
    # === Flash config from SteeringScript.py ===
    can_bitrate = 125  # kbit/s
    node = 50          # current Node-ID 
    can = DriverCan(can_bitrate=can_bitrate)
    mic = MicontrolF35_CAN(can=can.can_network, node=node)
    if not mic.added_node:
        print("[ERROR] Could not add CAN node.") 
        return
    dsa = DSACompat(mic.added_node)
    script_path = import_script_via_qr()
    print(f"[INFO] Using script: {script_path}")

    # Read the angle in the same time 
    read_angle_cam = AngleDetection(debug=False, return_after=20, timeout_s=None)
    print(read_angle_cam)

    steer_mod, apply_fn, arity = load_config_function(script_path)
    print("[INFO] Applying configuration from steering script...")
    apply_fn(dsa)
    mic.clear_errors()
    print("[INFO] Configuration applied and errors cleared.")

    # Set Offset Position to actual steering angle
    angle_deg = float(read_angle_cam)
    offset1 = int(round((angle_deg - 180) % 360.0) * 4096.0 / 360.0)
    offset2 = int(round((angle_deg - 270) % 360.0) * 4096.0 / 360.0) 
    hex_offset1 = offset1 & 0xFFF
    hex_offset2 = offset2 & 0xFFF

    # ==== MiC+ MU Turn on 2 encoder load config, set ST on zero ====
    mic.set_digital_output(True)  # Enable 5V to encoder 

    handle = MU_Handle()

    mu.MU_Open(byref(handle));                                 print("Open")
    mu.MU_SetInterface(handle, MU_MB5U.value, serial_last4.encode('ascii'));  print("Set Interface")
    init_and_load_cfg(handle)

    set_zero2 = int(0) & 0xFFF
    mu.MU_CalcPRES_POS(handle, set_zero2, set_zero2, MU_VERIFY) 
    mu.MU_WriteCmdRegister(handle, c_uint32(8))

    mu.MU_CalcPRES_POS(handle, set_zero2, c_uint32(hex_offset2), MU_VERIFY) 
    mu.MU_WriteCmdRegister(handle, c_uint32(8))  # MU_CMD_SOFT_PRES

    mu.MU_WriteEeprom(handle, MU_E2P_CFG);                    print("Write EEPROM")

    mu.MU_Close(handle); 

    mic.clear_errors()

    # ==== MiC + MU Turn on 1 encoder load config, set ST on zero ====
    mic.set_digital_output(False)  # Enable 5V to encoder 
 
    mu.MU_Open(byref(handle));                                 print("Open")
    mu.MU_SetInterface(handle, MU_MB5U.value, serial_last4.encode('ascii'));  print("Set Interface")
    init_and_load_cfg(handle)

    set_zero1 = int(1024) & 0xFFF
    mu.MU_CalcPRES_POS(handle, set_zero1, set_zero1, MU_VERIFY) 
    mu.MU_WriteCmdRegister(handle, c_uint32(8))

    mu.MU_CalcPRES_POS(handle, set_zero1, c_uint32(hex_offset1), MU_VERIFY) 
    mu.MU_WriteCmdRegister(handle, c_uint32(8))  # MU_CMD_SOFT_PRES

    mu.MU_WriteEeprom(handle, MU_E2P_CFG);                    print("Write EEPROM")
    mu.MU_Close(handle); 

    mic.clear_errors()

    mic.enabled(True)
    mic.set_steering_RPM(1000)
    mic.set_steering_pos(0)

    

if __name__ == "__main__":
    main(serial_last4="")
