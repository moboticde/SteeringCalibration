# io_helpers/requirements_doc.py
import os
from matplotlib import pyplot as plt
import numpy as np
import pandas as pd
from io_helpers.find_product_folder import find_config
from openpyxl import load_workbook
import zipfile
import warnings  
warnings.filterwarnings("ignore", message="Data Validation extension is not supported and will be removed")  


def is_valid_xlsx(path):
    try:
        with zipfile.ZipFile(path, 'r') as zipf:
            return "[Content_Types].xml" in zipf.namelist()
    except zipfile.BadZipFile:
        return False


class ConfigReader:
    """Reads and stores configuration parameters and recepies from Excel files dynamically."""

    def __init__(self, barcode):
        self.path = find_config(barcode)  # Find the correct folder dynamically
        if not self.path:
            raise FileNotFoundError(f"[ERROR] No matching folder found for barcode: {barcode}")

        # Dynamically set base path for this barcode
        self.BASE_PATH = self.path
        self.RECEPIES_FOLDER = os.path.join(self.BASE_PATH, "02_EOL_Recepies")
        self.PRODUCT_SPEC_V2 = os.path.join(self.BASE_PATH, "ProductSpecifications_V2.xlsx")
        self.PRODUCT_SPEC = os.path.join(self.BASE_PATH, "ProductSpecifications.xlsx")
        self.STEERING_APP_TEST_FILE = os.path.join(self.RECEPIES_FOLDER, "SteeringAppRecepie.xlsx")
        self.STEERING_MOTOR_TEST_FILE = os.path.join(self.RECEPIES_FOLDER, "SteeringMotorRecepie.xlsx")
        self.TRACTION_TEST_FILE = os.path.join(self.RECEPIES_FOLDER, "TractionRecepie.xlsx")
        self.SAVE_RESULTS_PATH = os.path.join(self.BASE_PATH, "04_EOL_Results")
        os.makedirs(self.SAVE_RESULTS_PATH, exist_ok=True)

        # Generate unique filename
        excel_name = f"{barcode}_test.xlsx"
        excel_path = os.path.join(self.SAVE_RESULTS_PATH, excel_name)

        attempt = 0
        final_path = excel_path
        while os.path.exists(final_path):
            attempt += 1
            suffix = f" (copy{'' if attempt == 1 else f' {attempt}'})"
            final_name = f"{barcode}_test{suffix}.xlsx"
            final_path = os.path.join(self.SAVE_RESULTS_PATH, final_name)

        self.results_excel_path = final_path

        if not os.path.exists(self.results_excel_path):
            with pd.ExcelWriter(self.results_excel_path, engine='openpyxl', mode='w') as writer:
                pd.DataFrame({'info': ['initialized']}).to_excel(writer, sheet_name='init', index=False)

        # Load config
        self.parameters = {}
        self.recepies = {}
        self.load_config()
        self.load_recepies()

    def load_config(self):
        """Loads configuration from the available Excel file dynamically."""
        if os.path.exists(self.PRODUCT_SPEC_V2):
            self._read_spec(self.PRODUCT_SPEC_V2)
        else:
            raise FileNotFoundError("No valid product specification file found.")

    def _read_spec(self, filepath):
        """Reads all parameters from the available specification file dynamically."""
        xls = pd.ExcelFile(filepath, engine="openpyxl")
        for sheet in xls.sheet_names:
            df = pd.read_excel(filepath, sheet_name=sheet, engine="openpyxl")
            for index, row in df.iterrows():
                key = row.iloc[0]
                value = row.iloc[1]
                self.parameters[key] = value

    def get_product_parameter(self, name, default=None):
        """Retrieve a parameter by name safely."""
        return self.parameters.get(name, default)

    def load_recepies(self):
        """Loads recepies from additional Excel files."""
        for file_path, key in [
            (self.STEERING_APP_TEST_FILE, "SteeringApp"),
            (self.STEERING_MOTOR_TEST_FILE, "Steering"),
            (self.TRACTION_TEST_FILE, "Traction")
        ]:
            if os.path.exists(file_path):
                self.recepies[key] = self._read_recepies(file_path)

    def _read_recepies(self, filepath):
        """Reads only 'Sheet1' from the recepie file and stores it as a DataFrame."""
        try:
            df = pd.read_excel(filepath, sheet_name="Sheet1", engine="openpyxl")
            return df
        except ValueError:
            print(f"[ERROR] Recepies not found in {filepath}")
            return None

    # Save the results
    def save_results_to_excel(self, results, sheet_name):
        # Step 1: Save the new results first
        with pd.ExcelWriter(self.results_excel_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
            results.to_excel(writer, sheet_name=sheet_name, index=False)

        # Step 2: Remove 'init' sheet if it still exists
        book = load_workbook(self.results_excel_path)
        if 'init' in book.sheetnames and sheet_name != 'init':
            del book['init']
            book.save(self.results_excel_path)


    def extract_brake_feedback(self, dp, pg, brake_torque):
        fragments = []
        for idx, sheet_name in enumerate(["brake_test_forward", "brake_test_backward"]):
            actual_df = pd.read_excel(self.results_excel_path, sheet_name=sheet_name)
            fig_parts = []

            include_js = 'cdn' if idx == 0 else False

            # Braking current (only when brake is active)
            brake_current = actual_df.loc[actual_df["brake activated"] == 1, "RMS current"]
            avg_current = brake_current.mean()
            Kt_estimated = brake_torque / avg_current if avg_current != 0 else 0.1

            # --- RMS Current + Brake Activation ---
            fig_current = pg.plot_current_with_brake(
                time_list=actual_df['time(S)'].values,
                current=actual_df['RMS current'].values,
                brake_signal=actual_df['brake activated'].astype(int).values,
                title=f"{sheet_name.replace('_', ' ').title()} - Current"
            )
            fig_parts.append(fig_current.to_html(full_html=False, include_plotlyjs=include_js))

            # --- Traction Feedback + Brake Activation ---
            fig_speed = pg.plot_speed_with_brake(
                time_list=actual_df['time(S)'].values,
                speed=actual_df['Traction feedback'].values,
                brake_signal=actual_df['brake activated'].astype(int).values,
                title=f"{sheet_name.replace('_', ' ').title()} - Speed"
            )
            fig_parts.append(fig_speed.to_html(full_html=False, include_plotlyjs=include_js))

            # --- Brake Energy ---
            fig_energy = pg.plot_energy_comparison(
                time_list=actual_df["time(S)"].values,
                current_list=actual_df["RMS current"].values,
                speed_rpm_list=actual_df["Traction feedback"].values,
                voltage=48,
                kt=Kt_estimated,
                title=f"{sheet_name.replace('_', ' ').title()} - Energy Comparison"
            )
            fig_parts.append(fig_energy.to_html(full_html=False, include_plotlyjs=include_js))

            fragments.append({
                "title": sheet_name.replace("_", " ").title(),
                "figs": fig_parts
            })
        return fragments

    def extract_motor_combined_feedback(self, dp, pg):
        result_sections = []

        motor_tests = [
            {
                "title": "Traction",
                "sheet": "traction_test",
                "csv_pattern": "*_traction_motor_test.csv",
                "rename": {},
                "type": "feedback",  # with setpoints
            },
            {
                "title": "Steering",
                "sheet": "steering_test",
                "csv_pattern": "*_steering_motor_test.csv",
                "rename": {
                    'speed_p': 'set point',
                    'feedback_speed': 'Traction feedback'
                },
                "type": "feedback",  # with setpoints
            },
            {
                "title": "Steering App",
                "sheet": "steering_app",
                "csv_pattern": "*_steering_app_test.csv",
                "rename": {},
                "type": "position",  # no setpoints
            }
        ]

        for i, test in enumerate(motor_tests):
            try:
                sheet = test["sheet"]
                csv_pattern = test["csv_pattern"]
                title = test["title"]
                rename_map = test["rename"]
                test_type = test["type"]

                actual_df = pd.read_excel(self.results_excel_path, sheet_name=sheet)
                if rename_map:
                    actual_df = actual_df.rename(columns=rename_map)

                all_df, avg_df = dp.all_files(
                    self.SAVE_RESULTS_PATH,
                    csv_pattern,
                    sheet,
                    os.path.basename(self.results_excel_path)
                )
                if rename_map:
                    avg_df = avg_df.rename(columns=rename_map)

                fig_parts = []

                if test_type == "feedback":
                    # Raw values
                    raw_current = actual_df[['time(S)', 'current A']].values.tolist()
                    raw_temp = actual_df[['time(S)', 'temperature']].values.tolist() if 'temperature' in actual_df.columns else [[t, None] for t in actual_df['time(S)']]
                    raw_rms_current = actual_df[['time(S)', 'RMS current']].values.tolist()
                    raw_speed = actual_df[['time(S)', 'Traction feedback']].values.tolist()

                    # Statistics
                    actual_current = dp.min_max_avg(actual_df, 'current A')
                    actual_temp = dp.min_max_avg(actual_df, 'temperature') if 'temperature' in actual_df.columns else actual_current * 0
                    actual_rms_current = dp.min_max_avg(actual_df, 'RMS current')
                    actual_speed = dp.min_max_avg(actual_df, 'Traction feedback')

                    # General raw
                    gen_raw_current = avg_df[['time(S)', 'current A']].values.tolist()
                    gen_raw_temp = avg_df[['time(S)', 'temperature']].values.tolist() if 'temperature' in avg_df.columns else [[t, None] for t in avg_df['time(S)']]
                    gen_raw_rms_current = avg_df[['time(S)', 'RMS current']].values.tolist()
                    gen_raw_speed = avg_df[['time(S)', 'Traction feedback']].values.tolist()

                    # General stats
                    general_current = dp.min_max_avg(avg_df, 'current A')
                    general_temp = dp.min_max_avg(avg_df, 'temperature') if 'temperature' in avg_df.columns else general_current * 0
                    general_rms_current = dp.min_max_avg(avg_df, 'RMS current')
                    general_speed = dp.min_max_avg(avg_df, 'Traction feedback')

                    data_dict = {
                        "DC Motor Current": (raw_current, actual_current, gen_raw_current, general_current),
                        "RMS Current": (raw_rms_current, actual_rms_current, gen_raw_rms_current, general_rms_current),
                        "Speed RPM": (raw_speed, actual_speed, gen_raw_speed, general_speed),
                        "Temperature": (raw_temp, actual_temp, gen_raw_temp, general_temp),
                    }

                    for j, (param_name, data) in enumerate(data_dict.items()):
                        fig = pg.plot_motor_feedback(param_name, data)
                        fig_parts.append(fig.to_html(full_html=False, include_plotlyjs='cdn' if j == 0 else False))

                elif test_type == "position":
                    raw_pos_input = actual_df[['time(S)', 'position input']].values.tolist()
                    raw_pos_feedback = actual_df[['time(S)', 'position feedback']].values.tolist()
                    raw_rms_current = actual_df[['time(S)', 'RMS current']].values.tolist()

                    gen_pos_input = avg_df[['time(S)', 'position input']].values.tolist()
                    gen_pos_feedback = avg_df[['time(S)', 'position feedback']].values.tolist()
                    gen_rms_current = avg_df[['time(S)', 'RMS current']].values.tolist()

                    # Now safe to use these variables
                    fig_parts.append(
                        pg.plot_motor_app_feedback("Position Feedback", raw_pos_feedback, gen_pos_feedback, raw_input=raw_pos_input)
                            .to_html(full_html=False, include_plotlyjs=False)
                    )

                    fig_parts.append(
                        pg.plot_motor_app_feedback("RMS Current", raw_rms_current, gen_rms_current, raw_input=raw_pos_input)
                            .to_html(full_html=False, include_plotlyjs=False)
                    )

                result_sections.append({"title": title, "figs": fig_parts})

            except Exception as e:
                print(f"")

        return result_sections
    
    def check_calibration_status(self, dp):
        actual_df = pd.read_excel(self.results_excel_path, sheet_name='traction_test')
        actual_current = dp.min_max_avg(actual_df, 'current A')
        df_actual = pd.DataFrame(actual_current, columns=['setpoint', 'min', 'max', 'avg'])
        
        df_actual = df_actual.dropna(subset=['min', 'max'])
        
        # Calibration check: if any interval exceeds the threshold
        if ((df_actual['max'] - df_actual['min']) > 0.2).any():
            return "not calibrated"
        else:
            return "ok"
        
    
    # Get metadata
    def get_metadata(self,dp):
        """
        Extracts metadata from 'general_traction' and 'general_steering' sheets separately.
        Returns a dict with keys 'traction' and 'steering'.
        """
        meta = {
            'traction': {},
            'steering': {}
        }
        for sheet, key in [('general_traction', 'traction'), ('general_steering', 'steering')]:
            try:
                df = pd.read_excel(self.results_excel_path, sheet_name=sheet, engine='openpyxl')
                for _, row in df.iterrows():
                    param = str(row.get('Parameter', '')).strip()
                    value = row.get('Value', '')
                    # flatten dict cell if needed
                    if isinstance(value, dict) and value:
                        value = list(value.values())[0]
                    meta[key][param] = value
            except (ValueError, FileNotFoundError, KeyError):
                # sheet not present or invalid, leave empty
                continue

        status = self.check_calibration_status(dp)
        meta['traction']['Threshold Status'] = status

        return meta
    
    @staticmethod
    def get_unique_filename(filepath):
        """
        If filepath exists, append _copy, _copy2, etc. before the extension.
        """
        base, ext = os.path.splitext(filepath)
        counter = 1
        new_filepath = filepath
        while os.path.exists(new_filepath):
            new_filepath = f"{base}_copy{counter}{ext}"
            counter += 1
        return new_filepath

        
    # Rendering plots in HTML tabs
    def render_tabs_html(self, unit_serial_number, sections, metadata):
        """
        Renders plot sections into an HTML report with tabs,
        showing traction metadata on the left and steering on the right (only if exists).
        """
        plot_name = f"{unit_serial_number}_plots_tabs.html"
        raw_path = os.path.join(self.SAVE_RESULTS_PATH, plot_name)
        plot_path = self.get_unique_filename(raw_path)

        def _render_meta_div(meta_dict):
            if not meta_dict:
                return ''
            html = ['<ul>']
            for k, v in meta_dict.items():
                html.append(f"<li><b>{k}:</b> {v}</li>")
            html.append('</ul>')
            return '\n'.join(html)

        traction_meta = metadata.get('traction', {})
        steering_meta = metadata.get('steering', {})

        with open(plot_path, 'w', encoding='utf-8') as f:
            f.write("<html><head><title>Test Report</title>")
            f.write("""
            <style>
                .metadata-container { display: flex; justify-content: space-between; gap: 40px; }
                .metadata-box { width: 48%; }
                .tab { display: none; }
                .tab.active { display: block; }
                .nav { margin-bottom: 10px; }
                .nav button { margin-right: 5px; padding: 6px 12px; }
            </style>
            <script>
                function showTab(id) {
                    document.querySelectorAll('.tab').forEach(el => el.classList.remove('active'));
                    document.getElementById(id)?.classList.add('active');
                }
                window.onload = function() { showTab('tab0'); };
            </script>
            """)
            f.write("</head><body>")
            f.write(f"<h1>EOL Report: {unit_serial_number}</h1>")

            # Metadata layout
            f.write("<div class='metadata-container'>")
            f.write("<div class='metadata-box'><h2>Traction Metadata</h2>")
            f.write(_render_meta_div(traction_meta))
            f.write("</div>")
            if steering_meta:
                f.write("<div class='metadata-box'><h2>Steering Metadata</h2>")
                f.write(_render_meta_div(steering_meta))
                f.write("</div>")
            f.write("</div><hr>")

            # Tab buttons
            f.write("<div class='nav'>")
            valid = []
            for idx, sec in enumerate(sections):
                if sec and sec.get('title') and sec.get('figs'):
                    valid.append(sec)
                    f.write(f"<button onclick=\"showTab('tab{idx}')\">{sec['title']}</button>")
            f.write("</div>")

            # Tab contents
            for idx, sec in enumerate(valid):
                f.write(f"<div id='tab{idx}' class='tab'>")
                for fig in sec['figs']:
                    if fig:
                        f.write(fig + '<hr>')
                f.write("</div>")

            f.write("</body></html>")

        os.startfile(plot_path)
        return plot_path







