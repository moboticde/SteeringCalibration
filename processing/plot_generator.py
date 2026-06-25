import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


class PlotGenerator:
    def __init__(self):
        self.fig = None

    def _compute_diff(self, t_act, t_gen, df_actual, df_general):
        df_act = pd.DataFrame({
            'time': t_act,
            'avg_act': df_actual['avg'],
            'min_act': df_actual['min'],
            'max_act': df_actual['max']
        }).sort_values('time')
        df_gen = pd.DataFrame({
            'time': t_gen,
            'setpoint': df_general['setpoint'],
            'avg_gen':  df_general['avg'],
            'min_gen':  df_general['min'],
            'max_gen':  df_general['max']
        }).sort_values('time')
        df_merged = pd.merge_asof(df_gen, df_act, on='time', direction='backward')
        return pd.DataFrame({
            'setpoint': df_merged['setpoint'],
            'avg':       abs(df_merged['avg_gen'] - df_merged['avg_act']),
            'min':       df_merged['min_gen'] - df_merged['min_act'],
            'max':       df_merged['max_gen'] - df_merged['max_act'],
        })

    def _filter_difference_plot(self, x, y, value_threshold=0.05, duration_threshold=1.0):
        x_new = [x[0]]
        y_new = [y[0]]
        last_change_idx = 0

        for i in range(1, len(x)):
            value_change = abs(y[i] - y[last_change_idx])
            time_duration = x[i] - x[last_change_idx]

            if value_change > value_threshold and time_duration >= duration_threshold:
                x_new.append(x[i])
                y_new.append(y[i])
                last_change_idx = i
            elif value_change > value_threshold:
                x_new[-1] = x[i]
                y_new[-1] = y[i]
                last_change_idx = i

        return x_new, y_new

    def plot_motor_feedback(self, param_name, data):
        raw_data, actual_data, gen_raw, general_data = data

        df_raw     = pd.DataFrame(raw_data,    columns=['time(S)', 'raw'])
        df_actual  = pd.DataFrame(actual_data, columns=['setpoint','min','max','avg'])

        t_act = df_raw['time(S)']

        fig = make_subplots(specs=[[{"secondary_y": True}]])

        fig.add_trace(go.Scatter(x=t_act, y=df_raw['raw'], mode='lines', name="Actual",
                                 line=dict(color='orange', dash='dot'), opacity=0.6), secondary_y=False)
        fig.add_trace(go.Scatter(x=t_act, y=df_actual['avg'], mode='lines', name="Avg Actual",
                                 line=dict(color='red'),visible='legendonly'), secondary_y=False)
        fig.add_trace(go.Scatter(x=pd.concat([t_act, t_act[::-1]]),
                                 y=pd.concat([df_actual['max'], df_actual['min'][::-1]]),
                                 fill='toself', fillcolor='rgba(255,0,0,0.2)', line=dict(color='rgba(255,0,0,0)'),
                                 name="Min–Max Actual",visible='legendonly'), secondary_y=False)

        fig.add_trace(go.Scatter(x=t_act, y=df_actual['setpoint'], mode='lines', name="Set-Point",
                                 line=dict(color='peru', dash='dash')), secondary_y=True)

        fig.update_xaxes(title_text="Time (s)")
        fig.update_yaxes(title_text=param_name, secondary_y=False)
        fig.update_yaxes(title_text="Set-Point", secondary_y=True)
        fig.update_layout(title=param_name, template="plotly_white",
                          height=600, width=1500,
                          legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))

        return fig

    def plot_motor_app_feedback(self, param_name, raw_actual, raw_general, raw_input=None):

        df_raw = pd.DataFrame(raw_actual, columns=['time(S)', 'raw'])
        df_gen = pd.DataFrame(raw_general, columns=['time(S)', 'raw'])
        df_input = pd.DataFrame(raw_input, columns=['time(S)', 'setpoint'])

        fig = make_subplots(specs=[[{"secondary_y": True}]])

        # Main signal (primary axis)
        fig.add_trace(go.Scatter(
            x=df_raw['time(S)'],
            y=df_raw['raw'],
            mode='lines',
            name=f"{param_name} (Actual)",
            line=dict(color='orange', dash='dot'),
            opacity=0.6
        ), secondary_y=False)

        fig.add_trace(go.Scatter(
            x=df_gen['time(S)'],
            y=df_gen['raw'],
            mode='lines',
            name=f"{param_name} (General)",
            line=dict(color='black', dash='dot'),
            opacity=0.6
        ), secondary_y=False)

        # Position input as setpoint (secondary axis)
        if not df_input.empty:
            fig.add_trace(go.Scatter(
                x=df_input['time(S)'],
                y=df_input['setpoint'],
                mode='lines',
                name="Position Input",
                line=dict(color='blue', dash='dash')
            ), secondary_y=True)

        # Layout
        fig.update_layout(
            title=param_name,
            xaxis_title="Time (s)",
            yaxis_title=param_name,
            yaxis2_title="Position Input",
            height=600,
            width=1500,
            template="plotly_white",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )

        return fig





    def plot_speed_with_brake(self, time_list, speed, brake_signal, title):
        brake_scaled = np.array(brake_signal) * (np.max(speed) if np.max(speed) > 0 else -np.min(speed))

        fig = go.Figure()

        fig.add_trace(go.Scatter(
            x=time_list,
            y=speed,
            name="RPM",
            mode="lines",
            line=dict(color="blue", width=2)
        ))

        fig.add_trace(go.Scatter(
            x=time_list,
            y=brake_scaled,
            mode='lines',
            name="Brake Activated",
            line=dict(color="red", width=2)
        ))

        fig.update_layout(
            title=title,
            xaxis_title="Time (s)",
            yaxis_title="Speed RPM",
            height=600, 
            width=1500
        )

        return fig
    
    def plot_current_with_brake(self, time_list, current, brake_signal, title):

        brake_scaled = np.array(brake_signal) * (np.max(current) if np.max(current) > 0 else -np.min(current))

        fig = go.Figure()

        fig.add_trace(go.Scatter(
            x=time_list,
            y=current,
            name="RMS Current",
            mode="lines",
            line=dict(color="green", width=2)
        ))

        fig.add_trace(go.Scatter(
            x=time_list,
            y=brake_scaled,
            mode='lines',
            name="Brake Activated",
            line=dict(color="red", width=2)
        ))

        fig.update_layout(
            title=title,
            xaxis_title="Time (s)",
            yaxis_title="Current (A)",
            height=600, 
            width=1500
        )

        return fig
    
    def plot_energy_comparison(self, time_list, current_list, speed_rpm_list, voltage=48, kt=0.1, title="Electrical vs Mechanical Energy"):

        t = np.array(time_list)
        i = np.array(current_list)
        rpm = np.array(speed_rpm_list)

        delta_t = np.diff(t)
        delta_t = np.append(delta_t, delta_t[-1])  # last delta same as previous

        # Brake energy: E = Kt * I * omega * dt for scaling torque
        omega = 2 * np.pi * rpm / 60
        power_brake = kt * i * omega
        energy_brake = power_brake * delta_t
        total_energy = np.cumsum(energy_brake)

        # Plot both
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=t, y=abs(energy_brake * 100), name="Energy in every point(J)", line=dict(color="blue")))
        fig.add_trace(go.Scatter(x=t, y=abs(total_energy), name="Total Energy (J)", line=dict(color="green")))
        
        

        fig.update_layout(
            title=title,
            xaxis_title="Time (s)",
            yaxis_title="Energy (J)",
            height=600,
            width=1500,
            legend=dict(x=0.01, y=0.99)
        )

        return fig





