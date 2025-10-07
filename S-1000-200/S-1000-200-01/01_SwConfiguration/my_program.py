from mc._pymc_builtins_ import *

#############################
 # This script version!
MPUVER=6
#############################



def CheckDout():
   dout = Gp(0x3150, 0x00)                   # aktuellen Dout Zustand lesen
   if Gp(0x3001, 0x00) == 0:                 # Wenn kein Fehler...
      Sp(0x3150, 0x00, dout | 0x01)          # ... dann Dout0 high setzen


DefUserVar(name="Kty_temperature",  value=0, descr="KTY temperature",    min_value=0,   max_value=0xFF) # Global user variable
DefUserVar(name="MPU_Ver",  value = MPUVER, descr="Mpu_ver",    min_value=0,   max_value=0xFF) # Global user variable

Hardware_Version = Gp(0x302E, 0x01)
#brake part
BrakeCount = Gp(0x302F, 0x01)
LifetimeCount = Gp(0x302F, 0x02)
Writtenbc = 0
Writtenlc = 0
BrakeEngaged = 1
Voltage1 = 0 # 3100.00h Analog input 0
Voltage2 = 0  # 3100.00h Analog input 0
Rpm=0 #3A04.01h Measured velocity in [rpm]
Sto=0#3120.00h Digital inputs - Port0
rpmflag = 0 #variable to indicate RPM >100 or <-100
counter = 0 #helper variable for lifetime count in seconds
BrakeError = 0 #helper variable for brake error
TemperatureError = 0 #helper variable to detect temperature error
Sp(0x3000, 0x00, 0x01) #clear error
Delay(1000)
Sp(0x3000, 0x00, 0x01) #clear error
Delay(1000)

start=Clock()

while 1:
    CheckDout()
   ##############################
    # converting temp to Celzius
   ##############################
    pt = Gp(0x3114, 0x03)  # read motor temp
    if pt != Kty_temperature:
        Kty_temperature = (3.8 * (pt / 10) + 185) / 9.5
    if Kty_temperature >= 170:   #to detect over temperature of motor
      TemperatureError = 1


   ##############################
    #Breke engage/disengage detection and DOut logic based on the hardware version
   ##############################
    if Hardware_Version>=1:  #units with current feedback hardware
      #breke logic - set output DO if brake is disengaged (current flowing)
      # use analog input object 0x3100 (per your comment)
      Voltage1 = Gp(0x3100, 0x00)   # AI channel 1
      Voltage2 = Gp(0x3100, 0x00)   # AI channel 2
      Vdiff=Voltage1-Voltage2
      if Vdiff>200: #brake disengaged
        Sp(0x3150,0x00,Gp(0x3150,0x0)  | 0b10) #set DO
        BrakeEngaged = 0
      elif Vdiff<50: #we are concidering deadband between 50&200
        Sp(0x3150,0x00,Gp(0x3150,0x0) & 0b11111101)# reset D0
        BrakeEngaged = 1

    else: #HW Version 0 with old PCB
      DBrakeReg=Gp(0x39A0,0x01) #read Brake management - status
      bit3 = (DBrakeReg >> 3) & 0b1 #brake enabled/disable status
      if bit3 == 0: #if brake engaged
         Sp(0x3150,0x00,Gp(0x3150,0x0)  | 0b10) #set DOut Bit1 as high
         BrakeEngaged = 0
      else:
         Sp(0x3150,0x00,Gp(0x3150,0x0) & 0b11111101)# Bit 1 is 0 
         BrakeEngaged = 1
    ################################
    # End DOut logic
    ################################

    ################################
    # brake count part
    ################################
    Rpm= Gp(0x3A04, 0x01) #3A04.01h Measured velocity in [rpm]
    if Rpm>=100 or Rpm<=-100:
      rpmflag = 1
    else:
      rpmflag = 0

    if rpmflag==1 and BrakeEngaged==1 and Writtenbc==0: #100mm/s =67RPM
        Writtenbc = 1
        BrakeCount+=1
        Sp(0x302F, 0x00, 0x00000000)  # DEV_UserData_Cmd - reset - enter old password
        Sp(0x302F, 0x00, 0x00010000)         # DEV_UserData_Cmd - enter password - word0
        Sp(0x302F, 0x00, 0x00010000)         # DEV_UserData_Cmd - enter password - word1
        Sp(0x302F, 0x00, 0x00010000)         # DEV_UserData_Cmd - enter password - word2
        Sp(0x302F, 0x00, 0x00010000)         # DEV_UserData_Cmd - enter password - word3

        Sp(0x302F, 0x01, BrakeCount)         # DEV_UserData_D0 - enter data D0
        # Save password and data
        Sp(0x302F, 0x00, 0x00800000)  # DEV_UserData_Cmd - save data and password
        #Sp(0x3000, 0x00, 0x80)



    if rpmflag==1 and BrakeEngaged==0: #if brake count is written
            Writtenbc=0
    ################################
    # End brake count part
    ################################

    ################################
    # Lifetime Count Part in seconds
    ################################
    if ((Gp(0x3002, 0x00) & 0b1)==1):
        Writtenlc=1
        if DiffClock(start)>1000:
            counter+=1
            start=Clock()
    if ((Gp(0x3002, 0x00) & 0b1)==0) and (Writtenlc==1):
        LifetimeCount+= counter # to save time seconds
        Sp(0x302F, 0x00, 0x00000000)     # DEV_UserData_Cmd - reset - enter old password
        Sp(0x302F, 0x00, 0x00010000)         # DEV_UserData_Cmd - enter password - word0
        Sp(0x302F, 0x00, 0x00010000)         # DEV_UserData_Cmd - enter password - word1
        Sp(0x302F, 0x00, 0x00010000)         # DEV_UserData_Cmd - enter password - word2
        Sp(0x302F, 0x00, 0x00010000)         # DEV_UserData_Cmd - enter password - word3

        Sp(0x302F, 0x02, LifetimeCount)         # DEV_UserData_D0 - enter data D0
        # Save password and data
        Sp(0x302F, 0x00, 0x00800000)  # DEV_UserData_Cmd - save data and password
        #Sp(0x3000, 0x00, 0x80)
        Writtenlc=0
        counter =0
    ################################
    # End Lifetime Count Part
    ################################