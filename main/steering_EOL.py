# Mobotic End of the Line Test
import sys

from drivers.driver_can import DriverCan
from drivers.driver_arduino import DriverArduino, MeasureFromINA
from drivers.driver_QRreader import run_qr_reader

from io_helpers.requirements_doc import ConfigReader
from managers.test_manager import TestRunner
from managers.MCU_manager import MCUManager
from utils.utils import safe_execute


def as_int(x):
    try:
        return int(float(x))
    except Exception:
        return None


def scan_qr_code(label):
    print(f"[INFO] Scanning {label} QR code.")
    return run_qr_reader(show=True, once=True, return_first=True)


def main(tester_name=None):
    # -------------------- DRIVERS --------------------
    arduino = None
    multimeter = None
    can = None
    controllers_info = []
    eol_ok = False

    try:
        arduino = safe_execute(DriverArduino)
        multimeter = safe_execute(MeasureFromINA)

        print(r"""
╔═══════════════════════════════════════════════════════════════════════════╗
║ _____ ______   ________  ________  ________  _________  ___  ________     ║
║|\   _ \  _   \|\   __  \|\   __  \|\   __  \|\___   ___\\  \|\   ____\    ║
║\ \  \\\__\ \  \ \  \|\  \ \  \|\ /\ \  \|\  \|___ \  \_\ \  \ \  \___|    ║
║ \ \  \\|__| \  \ \  \\\  \ \   __  \ \  \\\  \   \ \  \ \ \  \ \  \       ║
║  \ \  \    \ \  \ \  \\\  \ \  \|\  \ \  \\\  \   \ \  \ \ \  \ \  \____  ║
║   \ \__\    \ \__\ \_______\ \_______\ \_______\   \ \__\ \ \__\ \_______\║
║    \|__|     \|__|\|_______|\|_______|\|_______|    \|__|  \|__|\|_______|║
╚═══════════════════════════════════════════════════════════════════════════╝
""")
        print("Welcome to End Of The Line Test!\n")

        if tester_name is None:
            tester_name = input("Who perform this test: ").strip()
        else:
            tester_name = str(tester_name).strip()

        # -------------------- QR CODES --------------------
        unit_serial_number = safe_execute(
            lambda: scan_qr_code("product"),
            spinner_text="Scanning product QR code",
        )
        print("Product QR:", unit_serial_number)

        motor_number = safe_execute(
            lambda: scan_qr_code("motor"),
            spinner_text="Scanning motor QR code",
        )
        print("Motor QR:", motor_number)

        # -------------------- CONFIG --------------------
        config = safe_execute(ConfigReader, unit_serial_number)
        gp = (config.get_product_parameter if config else (lambda *a, **k: None))

        product_parameters = {
            "CAN Baudrate": gp("CAN Baudrate"),
            "Motor supply voltage": gp("Motor supply voltage"),
            "SW Configuration": gp("SW Configuration"),
            "HW Version": gp("HW Version"),
            "MPU Version Number": gp("MPU Version Number"),
            "Steering Extended SSI": gp("Steering Extended SSI"),
            "Communication": gp("Communication"),
            "Traction Controller Type": gp("Traction Controller Type"),
            "Steering Controller Type": gp("Steering Controller Type"),
            "Traction Node ID": gp("Traction Node ID"),
            "Steering Node ID": gp("Steering Node ID"),
            "Zero angle": gp("Zero angle"),
        }

        # -------------------- RECIPES --------------------
        traction_test_data = {"setpoint": [], "time": []}
        steering_test_data = {"setpoint": [], "time": [], "position": []}

        if config:
            traction_recipe = config.recepies.get("Traction")
            steering_motor_recipe = config.recepies.get("Steering")
            steering_app_recipe = config.recepies.get("SteeringApp")

            if traction_recipe is not None and not traction_recipe.empty:
                traction_test_data["setpoint"] = safe_execute(
                    lambda: list(traction_recipe.get("setpoint", []))
                )
                traction_test_data["time"] = safe_execute(
                    lambda: list(traction_recipe.get("time", []))
                )

            if steering_motor_recipe is not None and not steering_motor_recipe.empty:
                steering_test_data["setpoint"] = safe_execute(
                    lambda: list(steering_motor_recipe.get("setpoint", []))
                )
                steering_test_data["time"] = safe_execute(
                    lambda: list(steering_motor_recipe.get("time", []))
                )

            if steering_app_recipe is not None and not steering_app_recipe.empty:
                steering_test_data["position"] = safe_execute(
                    lambda: list(steering_app_recipe.get("position", []))
                )

        # -------------------- TEST RUNNER --------------------
        perform = safe_execute(lambda: TestRunner(
            arduino=arduino,
            controller=None,
            config=config,
            motor_number=motor_number,
            multimeter=multimeter,
            unit_serial_number=unit_serial_number,
            tester_name=tester_name,
        ))

        # -------------------- BUS --------------------
        network = None
        if product_parameters.get("Communication") == "CAN" and product_parameters.get("CAN Baudrate"):
            can = safe_execute(DriverCan, can_bitrate=product_parameters["CAN Baudrate"])
            network = can.can_network if can else None

        # -------------------- CONTROLLERS --------------------
        controllers_info = []

        # Traction
        t_type = product_parameters.get("Traction Controller Type")
        t_node = as_int(product_parameters.get("Traction Node ID"))
        comm = product_parameters.get("Communication")

        if t_type and t_node is not None and comm:
            controller_traction = safe_execute(
                MCUManager.initialize_controller, t_type, comm, network=network, node=t_node
            )
            if controller_traction:
                controllers_info.append({
                    "controller": controller_traction,
                    "controller_firmware": t_type,
                    "is_steering": False,
                    "node": t_node,
                    "can": can,
                    "can_bitrate": product_parameters.get("CAN Baudrate"),
                    "setpoint": traction_test_data["setpoint"],
                    "time": traction_test_data["time"],
                    "position": [],
                })

        # Steering
        s_type = product_parameters.get("Steering Controller Type")
        s_node = as_int(product_parameters.get("Steering Node ID"))

        if s_type and s_node is not None and comm:
            controller_steering = safe_execute(
                MCUManager.initialize_controller, s_type, comm, network=network, node=s_node
            )
            if controller_steering:
                controllers_info.append({
                    "controller": controller_steering,
                    "controller_firmware": s_type,
                    "is_steering": True,
                    "node": s_node,
                    "can": can,
                    "can_bitrate": product_parameters.get("CAN Baudrate"),
                    "setpoint": steering_test_data["setpoint"],
                    "time": steering_test_data["time"],
                    "position": steering_test_data["position"],
                })

        if perform and controllers_info:
            eol_ok = bool(safe_execute(lambda: perform.run_EOL_test(
                controllers_info=controllers_info,
                product_parameters=product_parameters,
            )))
        else:
            print("[ERROR] EOL did not start because test runner or controllers were not available.")
    finally:
        # -------------------- TEARDOWN --------------------
        closed_can_ids = set()
        for can_handle in [can] + [info.get("can") for info in controllers_info if isinstance(info, dict)]:
            if can_handle and id(can_handle) not in closed_can_ids:
                closed_can_ids.add(id(can_handle))
                safe_execute(lambda handle=can_handle: handle.close_can())
        safe_execute(lambda: multimeter.close_multimeter() if multimeter else None)
        safe_execute(lambda: arduino.close_arduino() if arduino else None)
    return eol_ok


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
