
import matplotlib.pyplot as plt
import numpy as np
from processing.data_processing import DataProcessing
from plot_generator import PlotGenerator
import matplotlib.pyplot as plt

path = r"C:\Users\DaniilYegarmin\Mobotic GmbH\Mobotic - Manufacturing\01_Products\DD-RL-500-225-54-48-C-12\DD-RL-500-225-54-48-C-12\04_EOL_Results"

dp = DataProcessing()
pg = PlotGenerator()

all_df, avg_df = dp.all_files(path,"*_traction_motor_test*" , "traction_test")

grp = all_df.groupby('source_file')

raw_data_by_file = { fname: df.copy() for fname, df in grp }

metrics = grp.agg({
    'Traction feedback': ['min', 'mean', 'std'],
    'current A':    ['min', 'mean', 'max'],
    'RMS current':  ['min', 'mean', 'max'],
    'temperature':  ['min', 'mean', 'max'],
})

# flatten column names
metrics.columns = ['_'.join(col).strip() for col in metrics.columns.values]

bad_cols = [
    'Traction feedback_std',
    'current A_mean',
    'RMS current_max',
    'temperature_min',
    'temperature_max'
]

# compute the 95th percentile of each
pct95 = metrics[bad_cols].quantile(0.95)

# build status columns
for col in bad_cols:
    thr = pct95[col]
    # <= threshold → good ;  > threshold → bad
    metrics[f'{col}_status'] = np.where(
        metrics[col] <= thr,
        'good',
        'bad'
    )

# if one metric is bad → file is bad
status_cols = [c + '_status' for c in bad_cols]
metrics['file_status'] = np.where(
    metrics[status_cols].eq('bad').any(axis=1),
    'bad',
    'good'
)

# 2) Print counts of good vs bad files
print("\nFile status counts:\n", metrics['file_status'].value_counts())

# create a 2×2 grid of histograms
fig, axes = plt.subplots(2, 2, figsize=(12, 8))
axes = axes.flatten()

for ax, col in zip(axes, bad_cols):
    ax.hist(metrics[col], bins=20)
    ax.axvline(pct95[col], linestyle='--', label=f'95th pct = {pct95[col]:.2f}')
    ax.set_title(col)
    ax.set_xlabel('Value')
    ax.set_ylabel('Count')
    ax.legend()

plt.tight_layout()
plt.show()