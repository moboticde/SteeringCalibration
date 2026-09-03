import time
import datetime
import struct
import pandas as pd
from threading import Timer


time_ite = 0
count = 0
df1 = pd.DataFrame()
  
          

def traction_feedback_hc(controller, set_point, time_dur, multimeter):
    """
    Measure traction feedback, velocity, RMS current, and temperature.
    :param set_point: Target set point.
    :param time_dur: Duration of the test.
    :param controller: CAN node instance.
    :param i_dmm: Digital multimeter instance.
    :return: DataFrame with test results.
    """
    class RepeatTimer(Timer):
        def run(self):
            while not self.finished.wait(self.interval):
                self.function(*self.args, **self.kwargs)

    fd_list, st_list, time_list, cur_list, rmscur_list, temp_list = [], [], [], [], [], []
    time_now = datetime.datetime.now()

    global time_ite

    controller.set_RPM(set_point)
    
    def measure():
        global time_ite, count, df1

        if count < time_dur + 0.5:
            # Measuring temperature
            temp = controller.get_temperature()
            if temp is None:
                temp_kty = None
            else:
                ainf = struct.unpack('>f', temp.to_bytes(4, byteorder='big'))[0]
                r2 = 1000/((5/ainf)-1)
                rkty = 1/((1/r2)-(1/3740))
                temp_kty = (rkty-815)/7.9
            temp_list.append(temp_kty)

            # Measuring velocity
            velocity = controller.get_velocity()
            fd_list.append((velocity / 4096) * 60 if velocity is not None else None)

            # Getting RMS current
            rms_current = controller.get_rms_current()
            if rms_current is not None:
                rmscur_list.append(rms_current / 1000)
            else:
                rmscur_list.append(None)

            # Measuring current from Rigol
            vol_multimeter = multimeter.measure_voltage() if multimeter is not None else None
            if vol_multimeter is not None:
               vol = float(vol_multimeter)* 1000
               cur = (40 / 60) * vol
               cur_list.append(cur)
            else:
                cur_list.append(None)

            # Set point
            st_list.append(set_point)

            time_list.append(time_ite)
            time_ite += 0.5
            count += 0.5

        else:
            timer.cancel()
            data = {'time(S)': time_list, 'set point': st_list, 'Traction feedback': fd_list, 'current A': cur_list, 'RMS current': rmscur_list,'temperature':temp_list }
            df1 = pd.DataFrame(data)
            time_ite -= 0.5
            count = 0

    timer = RepeatTimer(0.5, measure)
    timer.start()
    timer.join()
    return df1


def update_timeteration(x):
    global time_ite, count
    time_ite = x
    count = 0
