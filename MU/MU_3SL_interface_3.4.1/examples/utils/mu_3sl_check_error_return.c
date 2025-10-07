/*
 * Software and its documentation is provided by iC-Haus GmbH or contributors "AS IS" and is
 * subject to the ZVEI General Conditions for the Supply of Products and Services with iC-Haus
 * amendments and the ZVEI Software clause with iC-Haus amendments (http://www.ichaus.de/EULA).
 */

#include "mu_3sl_check_error_return.h"
#include "MU_3SL_defs.h"


const char* errorEnumName(MU_Error errorCode)
{
    switch (errorCode) {
    case MU_OK:
        return "MU_OK";
    case MU_INVALID_HANDLE:
        return "MU_INVALID_HANDLE";
    case MU_INTERFACEDRIVER_NOT_FOUND:
        return "MU_INTERFACEDRIVER_NOT_FOUND";
    case MU_INTERFACE_NOT_FOUND:
        return "MU_INTERFACE_NOT_FOUND";
    case MU_INVALID_INTERFACE:
        return "MU_INVALID_INTERFACE";
    case MU_NO_INTERFACE_SELECTED:
        return "MU_NO_INTERFACE_SELECTED";
    case MU_INVALID_PARAMETER:
        return "MU_INVALID_PARAMETER";
    case MU_INVALID_ADDRESS:
        return "MU_INVALID_ADDRESS";
    case MU_INVALID_VALUE:
        return "MU_INVALID_VALUE";
    case MU_USB_ERROR:
        return "MU_USB_ERROR";
    case MU_FILE_NOT_FOUND:
        return "MU_FILE_NOT_FOUND";
    case MU_INVALID_FILE:
        return "MU_INVALID_FILE";
    case MU_SPI_ERROR:
        return "MU_SPI_ERROR";
    case MU_SPI_DISMISS:
        return "MU_SPI_DISMISS";
    case MU_SPI_FAIL:
        return "MU_SPI_FAIL";
    case MU_SPI_BUSY_TIMEOUT:
        return "MU_SPI_BUSY_TIMEOUT";
    case MU_VERIFY_FAILED:
        return "MU_VERIFY_FAILED";
    case MU_MASTERCOMM_FAILED:
        return "MU_MASTERCOMM_FAILED";
    case MU_BISSCOMM_FAILED:
        return "MU_BISSCOMM_FAILED";
    case MU_INVALID_BISSMASTER:
        return "MU_INVALID_BISSMASTER";
    case MU_USB_HIGHSPEED_WARNING:
        return "MU_USB_HIGHSPEED_WARNING";
    case MU_FAST_ROTATION:
        return "MU_FAST_ROTATION";
    case MU_SLOW_ROTATION:
        return "MU_SLOW_ROTATION";
    case MU_FILE_ACCESS_DENIED:
        return "MU_FILE_ACCESS_DENIED";
    case MU_READPARAM_SSI:
        return "MU_READPARAM_SSI";
    case MU_SSIRING_ERROR:
        return "MU_SSIRING_ERROR";
    case MU_SEMI_ROTATION:
        return "MU_SEMI_ROTATION";
    case MU_BISS_REGERROR:
        return "MU_BISS_REGERROR";
    case MU_INTERNAL_CALIB_ERROR:
        return "MU_INTERNAL_CALIB_ERROR";
    case MU_INVALID_CONFIGURATION:
        return "MU_INVALID_CONFIGURATION";
    case MU_CALIBRATION_FAILED:
        return "MU_CALIBRATION_FAILED";
    case MU_ACQUISITION_FAILED:
        return "MU_ACQUISITION_FAILED";
    case MU_GAIN_LIMIT:
        return "MU_GAIN_LIMIT";
    case MU_OFFSET_LIMIT:
        return "MU_OFFSET_LIMIT";
    case MU_PHASE_LIMIT:
        return "MU_PHASE_LIMIT";
    case MU_BAD_CAL_DATA:
        return "MU_BAD_CAL_DATA";
    case MU_I2C_COMM_FAILED:
        return "MU_I2C_COMM_FAILED";
    case MU_USB_DATA_LOSS:
        return "MU_USB_DATA_LOSS";
    case MU_MT_SYNC_FAILED:
        return "MU_MT_SYNC_FAILED";
    case MU_UNKNOWN_ERROR:
        return "MU_UNKNOWN_ERROR";
    case MU_UNKNOWN_REVISION:
        return "MU_UNKNOWN_REVISION";
    case MU_UNSUPPORTED_REVISION:
        return "MU_UNSUPPORTED_REVISION";
    case MU_UNKNOWN_PARAMETER:
        return "MU_UNKNOWN_PARAMETER";
    case MU_PARAMETER_NOT_IN_REVISION:
        return "MU_PARAMETER_NOT_IN_REVISION";
    case MU_REVISION_NOT_SET:
        return "MU_REVISION_NOT_SET";
    case MU_UNSUPPORTED_CHIP:
        return "MU_UNSUPPORTED_CHIP";
    case MU_CONTRADICTORY_REVISIONS:
        return "MU_CONTRADICTORY_REVISIONS";
    case MU_FRAME_RATE_NOT_SUPPORTED:
        return "MU_FRAME_RATE_NOT_SUPPORTED";
    case MU_CLOCK_FREQUENCY_NOT_SUPPORTED:
        return "MU_CLOCK_FREQUENCY_NOT_SUPPORTED";
    case MU_FRAME_CYCLE_TIME_TO_SHORT:
        return "MU_FRAME_CYCLE_TIME_TO_SHORT";
    case MU_NO_BISS_PROFILE_ID:
        return "MU_NO_BISS_PROFILE_ID";
    case MU_ADAPTER_FIRMWARE_INCOMPATIBLE:
        return "MU_ADAPTER_FIRMWARE_INCOMPATIBLE";
    }

    return "UNKNOWN";
}
