import os, re
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from processing.data_processing import DataProcessing

# --- CONFIG ---
PATH = r"C:\Users\DaniilYegarmin\Mobotic GmbH\Mobotic - Manufacturing\01_Products\DD-RL-500-225-54SB-48-C-6\DD-RL-500-225-54SB-48-C-6\04_EOL_Results"
CSV_PATTERN = "*_traction_motor_test*"
SHEET_NAME = "traction_test"
COLUMN = "current A"
TZ = "Europe/Berlin"

# --- Build NUM_RE dynamically from PATH (e.g., -> ^DDRL50022554SB48C-6-(?P<num>\d+)_) ---
def build_num_re_from_path(path: str):
    prod = os.path.basename(os.path.dirname(path.rstrip(r"\/")))
    parts = prod.split('-')
    if len(parts) < 2:
        raise ValueError(f"Unexpected product folder: {prod}")
    head = ''.join(parts[:-2])          # remove hyphens
    tail1, tail2 = parts[-2], parts[-1]
    prefix = f"{head}{tail1}-{tail2}"   # e.g. "DDRL50022554SB48C-6"
    return re.compile(rf"^{re.escape(prefix)}-(?P<num>\d+)_", re.IGNORECASE), prefix

NUM_RE, PREFIX = build_num_re_from_path(PATH)

# --- Parser (accepts _traction_motor_test or _test; -copy / -copy(n) / (copy n)) ---
TEST_RE     = re.compile(r'_(?:traction_motor_)?test', re.IGNORECASE)
COPY_DASH   = re.compile(r'-(copy)(?:\((\d+)\))?', re.IGNORECASE)   # -copy or -copy(3)
COPY_PAREN  = re.compile(r'\(copy\s*(\d+)\)', re.IGNORECASE)        # (copy 3)

def parse_filename_from_path(path: str):
    b = os.path.basename(path.strip())
    if not TEST_RE.search(b): return None
    mnum = NUM_RE.search(b)
    if not mnum: return None
    num = str(int(mnum.group('num')))  # drop leading zeros

    copy = None
    m = COPY_DASH.search(b)
    if m:
        copy = 'copy' if not m.group(2) else f'copy({m.group(2)})'
    else:
        m = COPY_PAREN.search(b)
        if m: copy = f'copy({m.group(1)})'

    ext = os.path.splitext(b)[1].lstrip('.').lower()
    if ext not in ('csv', 'xlsx'): return None
    return f"{num}/{(copy + '/') if copy else ''}{ext}"

def main():
    dp = DataProcessing()
    all_df, _ = dp.all_files(PATH, CSV_PATTERN, SHEET_NAME)

    rows = []
    for fname in all_df['source_file'].unique():
        df = all_df[all_df['source_file'] == fname]
        arr = dp.min_max_avg(df, COLUMN)  # -> [setpoint, min, max, avg]
        s = pd.DataFrame(arr, columns=['setpoint', 'min', 'max', 'avg']).dropna()
        if s.empty: continue
        max_osc = float((s['max'] - s['min']).max())

        fpath = fname if (os.path.isabs(fname) and os.path.exists(fname)) else os.path.join(PATH, fname)
        if not os.path.exists(fpath): continue

        # --- use MODIFICATION time ---
        mtime = os.path.getmtime(fpath)  # seconds since epoch
        dt = pd.to_datetime(mtime, unit='s', utc=True).tz_convert(TZ)  # tz-aware
        date_only = dt.date()

        label = parse_filename_from_path(fpath) or os.path.basename(fpath)
        rows.append([label, fpath, max_osc, date_only])

    df = pd.DataFrame(rows, columns=['name', 'file', 'max_osc', 'date'])
    if df.empty:
        print("[ERROR] No valid files/statistics found."); return

    # sort by DATE first, then NAME
# sort by DATE first, then NAME
    df = df.sort_values(['max_osc', 'date', 'name'],
                    ascending=[False, True, True]).reset_index(drop=True)

    fig = go.Figure(go.Bar(
        x=df['name'],  # categories; we relabel ticks as dates
        y=df['max_osc'],
        text=[f"{v:.2f} A" for v in df['max_osc']],
        textposition='auto',
        customdata=np.stack([df['file'], df['date']], axis=-1),
        hovertemplate="File: %{customdata[0]}<br>Date (mod): %{customdata[1]}<br>Max oscillation: %{y:.2f} A<extra></extra>"
    ))

    # x-axis still shows DATE labels, but order is date→name
    fig.update_xaxes(
        categoryorder='array',
        categoryarray=df['name'],
        tickmode='array',
        tickvals=df['name'],
        ticktext=df['name'].astype(str),
        tickfont=dict(size=9)       # ← smaller x-axis ticks
    )
    fig.update_yaxes(tickfont=dict(size=9))  # ← smaller y-axis ticks

    fig.update_traces(textfont=dict(size=9), textposition='auto')  # ← smaller bar labels

    fig.update_layout(
        title=f"Max oscillation per file — {PREFIX} (sorted by DATE, then NAME)",
        xaxis_title="Name",
        yaxis_title="Max oscillation (A)",
        template="plotly_white",
        margin=dict(l=40, r=40, t=70, b=60),
        font=dict(size=11)          # ← smaller default UI/legend font
    )

    # hide overlapping text if needed + slightly smaller title
    fig.update_layout(uniformtext_minsize=8, uniformtext_mode='hide')
    fig.update_layout(title={'text': fig.layout.title.text, 'font': {'size': 14}})

    fig.show()

    # --- save as standalone HTML ---
    ts = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
    OUTPUT_DIR = r"C:\Users\DaniilYegarmin\OneDrive - Mobotic GmbH\Desktop"
    out_html = os.path.join(OUTPUT_DIR, f"max_oscillation_{PREFIX}_{ts}.html")

    # include_plotlyjs=True -> fully self-contained (works offline). For smaller file, use 'cdn'.
    fig.write_html(out_html, include_plotlyjs=True, full_html=True, auto_open=False)
    print("Saved plot to:", out_html)

if __name__ == "__main__":
    main()
