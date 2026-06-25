import time
import datetime
import pandas as pd
from threading import Timer
from utils.utils import Spinner

def measure_braking(set_point, total_duration_seconds, brake_activation_time, sample_interval, arduino, controller, multimeter):
    fd_list, st_list, time_list, rmscur_list, brake_status_list = [], [], [], [], []

    time_ite = 0
    count = 0

    brake_activated = False
    spinner = Spinner(text=f"Running {set_point} RPM")
    spinner.start()
    class RepeatTimer(Timer):
        def run(self):
            while not self.finished.wait(self.interval):
                self.function(*self.args, **self.kwargs)

    def measure():
        nonlocal time_ite, count, brake_activated

        if count < total_duration_seconds + sample_interval:
            if not brake_activated and count >= brake_activation_time:

                # Activate brake
                arduino.set_relay_state('q3=0')
                brake_activated = True

            velocity = controller.get_velocity()
            fd_list.append(velocity)

            rms_current = controller.get_rms_current()
            rmscur_list.append(rms_current / 1000 if rms_current is not None else None)

            st_list.append(set_point)
            time_list.append(time_ite)
            brake_status_list.append(brake_activated)
 
            time_ite += sample_interval
            count += sample_interval
        else:
            timer.cancel()

    timer = RepeatTimer(sample_interval, measure)
    timer.start()
    timer.join()
    spinner.stop()
    data = {
        'time(S)': time_list,
        'set point': st_list,
        'Traction feedback': fd_list,
        'RMS current': rmscur_list,
        'brake activated': brake_status_list
    }

    return pd.DataFrame(data)

