import os
import pandas as pd
import numpy as np
import plotly.graph_objects as go

def find_lite_brake_excels(root_folder):
    excel_files = []
    for dirpath, dirnames, filenames in os.walk(root_folder):
        product_folder = os.path.basename(dirpath)
        if (product_folder.startswith('DD-R') or product_folder.startswith('DD-S')) and 'SB' not in product_folder:
            eol_folder = os.path.join(dirpath, '04_EOL_Results')
            if os.path.isdir(eol_folder):
                for f in os.listdir(eol_folder):
                    if f.endswith('.xlsx') and '_test' in f:
                        excel_files.append(os.path.join(eol_folder, f))
    return excel_files

def compute_stepwise_spread(df, interval=8, time_col='time(S)', val_col='current A'):
    t = df[time_col].values
    v = df[val_col].values
    bins = np.arange(t[0], t[-1] + interval, interval)
    df['bin'] = np.digitize(t, bins) - 1
    step_spreads = []
    for b in np.unique(df['bin']):
        mask = df['bin'] == b
        if mask.sum() < 2:
            continue
        step_spreads.append(np.max(v[mask]) - np.min(v[mask]))
    return np.mean(step_spreads), np.max(step_spreads)

def extract_spread_features(files, sheet_name='traction_test', column='current A', interval=8):
    feature_rows = []
    for file in files:
        try:
            df = pd.read_excel(file, sheet_name=sheet_name)
            avg_spread, max_spread = compute_stepwise_spread(df, interval=interval, time_col='time(S)', val_col=column)
            feature_rows.append([
                file,
                avg_spread,
                max_spread
            ])
        except Exception as e:
            print(f"Skip {file}: {e}")
    feature_names = ['file', 'avg_spread', 'max_spread']
    feature_df = pd.DataFrame(feature_rows, columns=feature_names).set_index('file')
    return feature_df

def quantile_spread_good_files(feature_df, quantile=0.4):
    spread_thresh = feature_df['avg_spread'].quantile(quantile)
    feature_df['status'] = np.where(
        feature_df['avg_spread'] <= spread_thresh,
        'good', 'bad'
    )
    good_files = feature_df[feature_df['status'] == 'good'].index.tolist()
    bad_files = feature_df[feature_df['status'] == 'bad'].index.tolist()
    return good_files, bad_files, feature_df

def plot_thresholds_plotly_and_export(good_files, sheet_name='traction_test', column='current A', export_path='stepwise_spread.xlsx'):
    dfs = []
    for file in good_files:
        try:
            df = pd.read_excel(file, sheet_name=sheet_name)
            dfs.append(df)
        except Exception as e:
            print(f"Skip {file}: {e}")
    if not dfs:
        print("No good files for plotting!")
        return
    min_len = min(len(df) for df in dfs)
    t_common = dfs[0]['time(S)'].values[:min_len]
    curves = np.array([df[column].values[:min_len] for df in dfs])
    min_curve = np.nanmin(curves, axis=0)
    max_curve = np.nanmax(curves, axis=0)
    spread_curve = max_curve - min_curve
    # Save to Excel
    df_out = pd.DataFrame({
        'time': t_common,
        'min_currentA': min_curve,
        'max_currentA': max_curve,
        'spread_currentA': spread_curve
    })
    df_out.to_excel(export_path, index=False)
    print(f"Saved stepwise min/max/spread to {export_path}")
    # Plot
    fig = go.Figure()
    for i, df in enumerate(dfs):
        fig.add_trace(go.Scatter(
            x=t_common, y=curves[i],
            mode='lines', line=dict(color='gray', width=1),
            name=f"File {i+1}", opacity=0.15, showlegend=False
        ))
    fig.add_trace(go.Scatter(
        x=np.concatenate([t_common, t_common[::-1]]),
        y=np.concatenate([max_curve, min_curve[::-1]]),
        fill='toself', fillcolor='rgba(255,150,0,0.12)',
        line=dict(color='orange'),
        name='Envelope',
        showlegend=True
    ))
    fig.add_trace(go.Scatter(x=t_common, y=min_curve, mode='lines', line=dict(color='green', width=2), name='Min threshold'))
    fig.add_trace(go.Scatter(x=t_common, y=max_curve, mode='lines', line=dict(color='red', width=2), name='Max threshold'))
    fig.add_trace(go.Scatter(x=t_common, y=spread_curve, mode='lines', line=dict(color='blue', width=2), name='Spread (max-min)'))
    fig.update_layout(
        title='Current A Envelope and Spread (Stepwise Spread filtered)',
        xaxis_title='Time (s)',
        yaxis_title='Current A',
        template='plotly_white',
        height=600,
        width=1500,
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1)
    )
    fig.show()

if __name__ == "__main__":
    root_folder = r"C:\Users\DaniilYegarmin\Mobotic GmbH\Mobotic - Manufacturing\01_Products"  # CHANGE if needed
    excel_files = find_lite_brake_excels(root_folder)
    print(f"Found {len(excel_files)} lite brake Excel files.")
    if len(excel_files) < 3:
        print("Not enough files, aborting...")
        exit()
    feature_df = extract_spread_features(excel_files, sheet_name='traction_test', column='current A', interval=8)
    good_files, bad_files, feature_df = quantile_spread_good_files(feature_df, quantile=0.4)
    print(f"Good (calibrated) files: {len(good_files)}  |  Bad (outlier) files: {len(bad_files)}")
    plot_thresholds_plotly_and_export(good_files, sheet_name='traction_test', column='current A', export_path='stepwise_spread.xlsx')
