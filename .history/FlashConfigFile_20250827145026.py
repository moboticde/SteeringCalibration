import os
from drivers.driver_QRreader import read
from drivers.driver_can import DriverCan
from drivers.driver_miControlF35 import MicontrolF35_CAN 
from io_helpers.find_product_folder import find_config
# Turn on camera and scan QR code
qrcode = read()
path = find_config(qrcode)
config_path = os.path.join(path, "01_SwConfiguration")
product_config = os.path.join(config_path, "SteeringScript_2.py")