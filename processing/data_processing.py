import pandas as pd
import numpy as np
import glob
import os


class DataProcessing:
    def __init__(self):
        self.path = None

    def compare(self, results1, results2):
        # Calculate differences between two sets of results for each setpoint
        result_differences = []
        for row1, row2 in zip(results1, results2):
            setpoint1, min1, max1, avg1 = row1
            setpoint2, min2, max2, avg2 = row2
            diff_min = min1 - min2
            diff_max = max1 - max2
            diff_avg = abs(avg1 - avg2)
            result_differences.append([setpoint1, diff_min, diff_max, diff_avg])
        return result_differences

    def min_max_avg(self, df, column):
        # Ensure required columns are present
        if 'set point' not in df.columns or column not in df.columns:
            raise ValueError(f"Required columns 'set point' or '{column}' are missing.")

        set_points = df['set point'].values
        values = df[column].values

        current_set_point = set_points[0]
        current_set_point_values = []
        setpoint_results = {}

        # Iterate over all rows to group values by setpoint
        for i in range(len(set_points)):
            if set_points[i] == current_set_point:
                current_set_point_values.append(values[i])
            else:
                # Compute trimmed min, max, avg for the previous setpoint
                n = len(current_set_point_values)
                if n > 0:
                    start = n // 4
                    end = n - start
                    middle_values = current_set_point_values[start:end]

                    if len(middle_values) > 0:
                        min_value = min(middle_values)
                        max_value = max(middle_values)
                        avg = sum(middle_values) / len(middle_values)
                        setpoint_results[current_set_point] = (min_value, max_value, avg)

                current_set_point = set_points[i]
                current_set_point_values = [values[i]]

        # Final computation for the last setpoint
        n = len(current_set_point_values)
        if n > 0:
            start = n // 4
            end = n - start
            middle_values = current_set_point_values[start:end]

            if len(middle_values) > 0:
                min_value = min(middle_values)
                max_value = max(middle_values)
                avg = sum(middle_values) / len(middle_values)
                setpoint_results[current_set_point] = (min_value, max_value, avg)

        # Fill results per row
        results = []
        for i in range(len(set_points)):
            sp = set_points[i]
            min_value, max_value, avg_value = setpoint_results.get(sp, (None, None, None))
            results.append([sp, min_value, max_value, avg_value])

        return np.array(results, dtype=float)
    
    
    def all_files(self, path, csv_pattern, sheet_name, exclude_filename=None):
        if sheet_name == "steering_app":
            required_columns = [
                'time(S)',
                'position input',
                'position feedback',
                'RMS current'
            ]
        elif sheet_name == "steering_test":
            required_columns = [
                'time(S)',
                'set point',
                'Traction feedback',
                'current A',
                'RMS current'  
            ]
        else:
            required_columns = [
                'time(S)',
                'set point',
                'Traction feedback',
                'current A',
                'RMS current',
                'temperature'
            ]


        all_csv = glob.glob(os.path.join(path, csv_pattern))
        all_xlsx = glob.glob(os.path.join(path, "*.xlsx"))

        dataframes = []

        def process(df, filename):
            # Apply steering-specific renaming if needed
            if sheet_name == "steering_test":
                rename_map = {
                    'speed_p': 'set point',
                    'feedback_speed': 'Traction feedback'
                }
                df = df.rename(columns=rename_map)

            # Fill in any missing columns
            missing = [col for col in required_columns if col not in df.columns]
            if missing:
                print(f"[WARNING] Missing columns in {filename}: {missing}")
                for col in missing:
                    df[col] = np.nan

            # Standardize structure
            df = df[required_columns].copy()
            df['source_file'] = os.path.basename(filename)
            return df

        for fname in all_csv:
            if exclude_filename and os.path.basename(fname) == exclude_filename:
                continue
            df = pd.read_csv(fname)

            # Normalize time
            if 'time(S)' in df.columns:
                df = df.copy()
                df['time(S)'] -= df['time(S)'].iloc[0]

            dataframes.append(process(df, fname))

        for fname in all_xlsx:
            if exclude_filename and os.path.basename(fname) == exclude_filename:
                continue
            try:
                df = pd.read_excel(fname, sheet_name=sheet_name)
                dataframes.append(process(df, fname))
            except Exception as exc:
                print(f"[WARNING] Skipping comparison workbook {fname}: {exc}")
                continue

        if not dataframes:
            raise ValueError("No actual data!")

        # Trim to shortest length across all runs
        min_rows = min(len(df) for df in dataframes)
        dataframes = [df.iloc[:min_rows] for df in dataframes]

        combined_df = pd.concat(dataframes, ignore_index=True)

        # Clean column names
        col_mapping = {col: col.split('.')[0] for col in combined_df.columns}
        combined_df = combined_df.rename(columns=col_mapping)

        # Average per timestamp
        avg_df = (
            combined_df
            .drop(columns=['source_file'])
            .set_index('time(S)')
            .groupby(level=0)
            .mean(numeric_only=True)
            .reset_index()
        )
        return combined_df, avg_df
