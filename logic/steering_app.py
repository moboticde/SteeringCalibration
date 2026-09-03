
import pandas as pd 
from threading import Timer
time_ite = 0
count = 0

df1 = pd.DataFrame()
def steering_feedback(controller_steering, speed, position, time_dur):

    class RepeatTimer(Timer):
                    def run(self):
                        while not self.finished.wait(self.interval):
                            self.function(*self.args, **self.kwargs)
    fd_list = []
    speed_list = []
    position_list = []
    time_list = []
    cur_list = []
    position_input = []
    rmscur_list = []
    
    controller_steering.set_steering_RPM(speed)
    controller_steering.set_steering_pos(position)

    def measure():
            global time_ite
            global count
            global df1
            
            
            
            if count <0.12:
                
                position_int = controller_steering.get_steering_pos()
                position_list.append(position_int)
                
                
                
                #use 3113
                #getting RMS current 
                rmscur = controller_steering.get_rms_current_steering()
                rmscur_list.append(rmscur / 1000 if rmscur is not None else None)
                
                
                position_input.append(position)
                
                time_list.append(time_ite)
                time_ite = time_ite+0.02
                count = count + 0.02
                
            else:
                timer.cancel()
                
                data = {'time(S)': time_list,'position input': position_input,'position feedback': position_list,'RMS current': rmscur_list}
                df1 = pd.DataFrame(data)
                #print(df1)
                time_ite = time_ite-0.02
                count = 0
                
                
                
                
                
    
    timer = RepeatTimer(0.012,measure)
    
    timer.start()
    timer.join()

    return df1
    
    
    
    
def update_sttimeite(x):
    global time_ite, count
    time_ite = x
    count = 0
