/*
 * Software and its documentation is provided by iC-Haus GmbH or contributors "AS IS" and is
 * subject to the ZVEI General Conditions for the Supply of Products and Services with iC-Haus
 * amendments and the ZVEI Software clause with iC-Haus amendments (http://www.ichaus.de/EULA).
 */

#ifndef IC_CSV_FILE_H
#define IC_CSV_FILE_H

#include "MU_3SL_defs.h"
#include "MU_3SL_interface.h"

#ifdef __cplusplus
    #include <cstdbool>
    #include <cstddef>
    #include <cstdint>
#else
    #include <stddef.h>
    #include <stdint.h>
#endif


#ifdef __cplusplus
extern "C" {
#endif


int readCalibrationDataCSVFile(
        uint16_t** masterDataArray,
        uint16_t** noniusDataArray,
        size_t* numberOfSamples,
        const char* filepath,
        unsigned long skipLines,
        uint8_t* hardRev,
        uint8_t* mpc,
        MU_Calibration_AnalogTrackAdjustments* masterAdjustments,
        MU_Calibration_AnalogTrackAdjustments* noniusAdjustments);

int readMtSyncCSVFile(
        MU_MtSyncData** syncData,
        size_t* numberOfSamples,
        const char* filepath,
        unsigned long skipLines);

size_t writeCalibrationDataCSVFile(
        const uint16_t* masterData,
        const uint16_t* noniusData,
        size_t numberOfSamples,
        const char* filepath,
        const uint8_t* hardRev,
        const uint8_t* mpc,
        const MU_Calibration_AnalogTrackAdjustments* masterAdjustments,
        const MU_Calibration_AnalogTrackAdjustments* noniusAdjustments);


#ifdef __cplusplus
}
#endif

#endif // IC_CSV_FILE_H
