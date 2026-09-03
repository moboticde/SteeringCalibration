import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import pandas as pd
from processing.plot_generator import PlotGenerator

# Load the result Excel
FILE_PATH = "C:\\Users\\DaniilYegarmin\\Mobotic GmbH\\Mobotic - Manufacturing\\01_Products\\DD-RR-500-225-54SB-48-C-12\\DD-RR-500-225-54SB-48-C-12\\04_EOL_Results\\DDRR50022554SB48C-12-45_test.xlsx"
SHEET_NAME = "brake_test_forward"
BRAKE_TORQUE_NM = 5  # Nm

# Load test data
brake_df = pd.read_excel(FILE_PATH, sheet_name=SHEET_NAME)

# Braking current (only when brake is active)
brake_current = brake_df.loc[brake_df["brake activated"] == 1, "RMS current"]

# Average it
avg_current = brake_current.mean()

# Estimate Kt
Kt_estimated = BRAKE_TORQUE_NM / avg_current


# Initialize plotter
pg = PlotGenerator()

# --- Brake Mechanical Energy Plot ---
fig_energy = pg.plot_energy_comparison(
    time_list=brake_df["time(S)"].values,
    current_list=brake_df["RMS current"].values,
    speed_rpm_list=brake_df["Traction feedback"].values,
    voltage=48,
    kt=Kt_estimated,
    title=f"{SHEET_NAME} - Energy Comparison"
)
fig_energy.show()

# --- Current + Brake Overlay Plot ---
fig_current = pg.plot_current_with_brake(
    time_list=brake_df["time(S)"].values,
    current=brake_df["RMS current"].values,
    brake_signal=brake_df["brake activated"].astype(int).values,
    title=f"{SHEET_NAME} - RMS Current + Brake"
)
fig_current.show()

# --- Speed + Brake Overlay Plot ---
fig_speed = pg.plot_speed_with_brake(
    time_list=brake_df["time(S)"].values,
    speed=brake_df["Traction feedback"].values,
    brake_signal=brake_df["brake activated"].astype(int).values,
    title=f"{SHEET_NAME} - Speed + Brake"
)
fig_speed.show()
