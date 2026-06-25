import time
import os
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from test_manager import TestRunner
from driver_arduino import DriverArduino
from driver_can import DriverCan
from driver_multimeter import DriverMultimeter
from MCU_manager import MCUManager
from data_processing import DataProcessing
from plot_generator import PlotGenerator
from utils import safe_execute
from brake_test import BrakeTest

# --- Initialization ---
arduino = safe_execute(DriverArduino)
multimeter = safe_execute(DriverMultimeter)
perform = TestRunner(arduino)
dp = DataProcessing()
pg = PlotGenerator()

time.sleep(2)
safe_execute(lambda: perform.activate_relays_for_operation(48) if perform else None)

can = DriverCan()
network = can.can_network

controller = MCUManager.initialize_controller("MiControlF35", "CAN", network=network, node=5)
bt = BrakeTest(controller, arduino, multimeter)

# --- Running Test ---
actual_df = perform.run_brake_test(bt, controller, 1700, 10, 8)

arduino.close_arduino()

# --- Save all raw measurements into one Excel sheet ---
desktop_excel_path = os.path.join(os.path.expanduser("~"), "Desktop", "brake_test_data.xlsx")
actual_df.to_excel(desktop_excel_path, index=False)
print(f"Data saved successfully at: {desktop_excel_path}")

# --- Prepare data for plots ---
raw_current = actual_df[['time(S)', 'current A']].values.tolist()
raw_temp = actual_df[['time(S)', 'temperature']].values.tolist()
raw_rms_current = actual_df[['time(S)', 'RMS current']].values.tolist()
raw_speed = actual_df[['time(S)', 'Traction feedback']].values.tolist()

actual_current = dp.min_max_avg(actual_df, 'current A')
actual_temp = dp.min_max_avg(actual_df, 'temperature')
actual_rms_current = dp.min_max_avg(actual_df, 'RMS current')
actual_speed = dp.min_max_avg(actual_df, 'Traction feedback')

# No wrong unpacking now
data_dict = {
    "DC Motor Current": (raw_current, actual_current),
    "RMS Current": (raw_rms_current, actual_rms_current),
    "Temperature": (raw_temp, actual_temp),
    "Speed RPM": (raw_speed, actual_speed)
}

# --- Save plots into HTML ---
all_figs = []
for param_name, (raw_data, actual_data) in data_dict.items():
    df_raw = pd.DataFrame(raw_data, columns=['time(S)', 'raw'])
    df_actual = pd.DataFrame(actual_data, columns=['setpoint', 'min', 'max', 'avg'])
    
    t_act = df_raw['time(S)']
    fig = make_subplots(specs=[[{"secondary_y": False}]])
    
    fig.add_trace(
        go.Scatter(x=t_act, y=df_raw['raw'], mode='lines', name="Raw Data",
                   line=dict(color='black'))
    )
    fig.add_trace(
        go.Scatter(x=t_act, y=df_actual['avg'], mode='lines+markers', name="Average",
                   line=dict(color='orange', dash='dot'), opacity=1)
    )
    fig.update_layout(title=param_name, xaxis_title="Time (S)", yaxis_title=param_name)
    all_figs.append(fig)

# Save HTML to Desktop
desktop_html_path = os.path.join(os.path.expanduser("~"), "Desktop", "brake_test_plots.html")

from plotly.offline import plot
with open(desktop_html_path, 'w') as f:
    for fig in all_figs:
        inner_html = plot(fig, include_plotlyjs='cdn', output_type='div')
        f.write(inner_html)

print(f"Plots saved successfully at: {desktop_html_path}")
