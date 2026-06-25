from importlib import import_module

class MCUManager:
    """
    Manages the selection and initialization of Motor Control Units (MCUs) dynamically.
    """
    MCU_FACTORY = {
        ("MiControlF35", "CAN"): ("drivers.driver_miControlF35", "MicontrolF35_CAN"),
        ("MiControlF37", "CAN"): ("drivers.driver_miControlF37", "MicontrolF37_CAN"),
        ("Elmo", "CAN"): ("drivers.driver_elmo", "Elmo_CAN"),
        #("MiControlF35", "EtherCAT"): MicontrolF35_EtherCAT,
        # ("Elmo", "EtherCAT"): Elmo_EtherCAT
    }

    @classmethod
    def get_controller(cls, controller_type, communication_type, **kwargs):
        """
        Retrieve the correct controller instance based on type and communication protocol.
        
        :param controller_type: Controller type (e.g., "MiControlF35", "Elmo").
        :param communication_type: Communication protocol (e.g., "CAN", "EtherCAT").
        :param kwargs: Additional arguments (network, node, eds_file for CAN, network, ports for EtherCAT).
        :return: Instance of the selected controller.
        """
        key = (controller_type, communication_type)
        
        if key not in cls.MCU_FACTORY:
            raise ValueError(f"[ERROR] Unsupported controller: {controller_type} with {communication_type}")

        module_name, class_name = cls.MCU_FACTORY[key]
        try:
            controller_class = getattr(import_module(module_name), class_name)
        except ModuleNotFoundError as exc:
            raise ValueError(
                f"[ERROR] Controller driver is not installed: {module_name}"
            ) from exc

        # Initialize the controller with appropriate parameters
        if communication_type == "CAN":
            return controller_class(kwargs["network"], kwargs["node"])
        
        # Change later
        elif communication_type == "EtherCAT":
            return controller_class(kwargs["network"], kwargs["ports"])
        
        raise ValueError(f"[ERROR] Invalid communication type: {communication_type}")

    @classmethod
    def initialize_controller(cls, controller_type, communication_type, **kwargs):
        """
        Initialize both first and second controllers dynamically.
        
        :param traction_type: Traction controller type (e.g., "MiControlF35").
        :param traction_comm: Traction communication type (e.g., "CAN", "EtherCAT").
        :param steering_type: Steering controller type (e.g., "Elmo").
        :param steering_comm: Steering communication type (e.g., "CAN", "EtherCAT").
        :param kwargs: Additional arguments for CAN or EtherCAT initialization.
        :return: Tuple (first_controller, second_controller)
        """
        try:
            controller = cls.get_controller(controller_type, communication_type, **kwargs)

            return controller
        except ValueError as e:
            print(e)
            return None
