# Thresholds of one Product

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from processing.data_processing import DataProcessing
from processing.plot_generator import PlotGenerator
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 1. LOAD DATA
path = r"C:\Users\DaniilYegarmin\Mobotic GmbH\Mobotic - Manufacturing\01_Products\DD-RR-500-225-54-48-C-12\DD-RR-500-225-54-48-C-12\04_EOL_Results"
desktop_path = r"C:\Users\DaniilYegarmin\OneDrive - Mobotic GmbH\Desktop"
dp = DataProcessing()
pg = PlotGenerator()
all_df, avg_df = dp.all_files(path, "*_traction_motor_test*", "traction_test")
files = all_df['source_file'].unique()
any_file = all_df['source_file'].unique()[0]
setpoint_series = all_df[all_df['source_file'] == any_file][['time(S)', 'set point']]

# 2. EXTRACT FEATURES FROM EACH FILE
feature_rows = []
for fname in files:
    vals = all_df[all_df['source_file'] == fname]['current A'].values
    vals = vals[~np.isnan(vals)]

    feature_rows.append([
        fname,
        np.mean(vals),
        np.std(vals),
        np.max(vals),
        np.min(vals),
    ])
feature_names = ['file', 'mean', 'std', 'max', 'min']
feature_df = pd.DataFrame(feature_rows, columns=feature_names).set_index('file')

# 3. QUANTILE-BASED FILTERING TO FLAG GOOD/BAD MOTORS
good_fraction = 0.1

mean_thresh = feature_df['mean'].quantile(good_fraction)
std_thresh = feature_df['std'].quantile(good_fraction)

# Mark as good only those with both mean and std in lowest quantile
feature_df['status'] = np.where(
    (feature_df['mean'] <= mean_thresh) & (feature_df['std'] <= std_thresh),
    'good', 'bad'
)
good_files = feature_df[feature_df['status'] == 'good'].index

# 4. PIVOT ALL DATA TO [TIME, FILE] MATRIX
all_df = all_df.groupby(['time(S)', 'source_file'], as_index=False).agg({'current A': 'mean'})
pivot = all_df.pivot(index="time(S)", columns="source_file", values="current A")

# 5. THRESHOLDS USING ONLY GOOD MOTORS (warn/skip if too few)
if len(good_files) < 3:
    print(f"WARNING: Only {len(good_files)} good files identified. Envelope calculation skipped or unreliable.")
    thresholds = None
else:
    good_pivot = pivot[good_files]
    thresholds = pd.DataFrame(index=good_pivot.index)
    thresholds['min'] = good_pivot.min(axis=1)
    thresholds['max'] = good_pivot.max(axis=1)
    thresholds['mean'] = good_pivot.mean(axis=1)

# 6. FLAG ALL POINTS IN ALL FILES AS GOOD/BAD (OUTLIER VS GOOD ENVELOPE)
if thresholds is not None:
    def flag_good_bad(col):
        return np.where((col >= thresholds['min']) & (col <= thresholds['max']), 'good', 'bad')
    status = pivot.apply(flag_good_bad, axis=0)
    status = pd.DataFrame(status, index=pivot.index, columns=pivot.columns)
else:
    status = None

# 7. VISUALIZE FEATURE SPACE
plt.figure(figsize=(10,6))
plt.scatter(
    feature_df[feature_df['status']=='good']['mean'],
    feature_df[feature_df['status']=='good']['std'],
    c='blue', label='Good'
)
plt.scatter(
    feature_df[feature_df['status']=='bad']['mean'],
    feature_df[feature_df['status']=='bad']['std'],
    c='red', label='Bad'
)
plt.xlabel('Mean Current A')
plt.ylabel('Std Dev Current A')
plt.title(f'Quantile Filtering: Good vs Bad Motors\n'
          f'(Good: {len(good_files)}, Bad: {len(files)-len(good_files)})')
plt.legend()
plt.tight_layout()
plt.show()

# 8. VISUALIZE CURRENT ENVELOPE AND ALL FILES
fig = make_subplots(specs=[[{"secondary_y": True}]])

fig.add_trace(go.Scatter(
    x=setpoint_series['time(S)'],
    y=setpoint_series['set point'],
    mode='lines',
    name='Setpoint',
    line=dict(dash='dash', color='black', width=2),
    showlegend=True
), secondary_y=True)

if thresholds is not None:
    # Good Min (step)
    fig.add_trace(go.Scatter(
        x=thresholds.index,
        y=thresholds['min'],
        mode='lines',
        line=dict(color='green', width=3),
        name='Good Min',
        showlegend=True,
    ), secondary_y=False)

    fig.add_trace(go.Scatter(
        x=thresholds.index,
        y=thresholds['max'],
        mode='lines',
        line=dict(color='red', width=3),
        name='Max',
        showlegend=True,
    ), secondary_y=False)

    # Fill envelope area
    fig.add_trace(go.Scatter(
        x=list(thresholds.index) + list(thresholds.index)[::-1],
        y=list(thresholds['max']) + list(thresholds['min'])[::-1],
        fill='toself',
        fillcolor='rgba(128,128,128,0.15)',
        line=dict(color='rgba(255,255,255,0)'),
        name='Good Envelope',
        showlegend=True
    ), secondary_y=False)

    # Step function for Max
    time = thresholds.index.values
    max_vals = thresholds['max'].values
    interval = 8  # seconds
    start_time = time[0]
    end_time = time[-1]
    bins = np.arange(start_time, end_time + interval, interval)

    df = pd.DataFrame({'time': time, 'max': max_vals})
    df['bin'] = np.digitize(df['time'], bins) - 1  # 0-based bin

    step_times = []
    step_vals = []
    for b in range(df['bin'].min(), df['bin'].max() + 1):
        mask = df['bin'] == b
        if not mask.any():
            continue
        interval_times = df.loc[mask, 'time']
        interval_max = df.loc[mask, 'max'].max()
        # For step, repeat value at left and right edge
        step_times += [interval_times.iloc[0], interval_times.iloc[-1]]
        step_vals += [interval_max, interval_max]

    fig.add_trace(go.Scatter(
        x=step_times,
        y=step_vals,
        mode='lines',
        name='Threshold Max',
        line=dict(color='orange', width=4, dash='solid')
    ))

else:
    fig.add_annotation(
        text="No reliable envelope calculated. Too few good files.",
        xref="paper", yref="paper", x=0.5, y=0.5,
        showarrow=False, font=dict(color="red", size=18)
    )

fig.update_layout(
    title='DC Current',
    xaxis_title='Time (s)',
    yaxis_title='Current A',
    template='plotly_white',
    legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1)
)
fig.update_yaxes(title_text="Setpoint", secondary_y=True)
fig.update_yaxes(title_text="Current (A)", secondary_y=False)
fig.show()
