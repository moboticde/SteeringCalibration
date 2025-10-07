/*
 * Software and its documentation is provided by iC-Haus GmbH or contributors "AS IS" and is
 * subject to the ZVEI General Conditions for the Supply of Products and Services with iC-Haus
 * amendments and the ZVEI Software clause with iC-Haus amendments (http://www.ichaus.de/EULA).
 */

#include "mu_3sl_analog_nonius_calibration.h"
#include "mu_3sl_check_error_return.h"

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>


MU_CalibrationAnalyzeResult* acquireAndAnalyzeRawData(
        MU_Handle muHandle,
        MU_Calibration* calibration,
        uint32_t slaveId,
        unsigned long numberOfSamples,
        double acquireFrameCycleTime_s,
        double acquireClockFrequency_hz,
        bool setOptimizedNoniusTrackOffsetTable)
{
    MU_Error e = MU_activateCalibrationConfig(muHandle);
    if (e != MU_OK) {
        MU_Error code;
        MU_ErrorType type;
        char message[1024];
        MU_GetLastError(muHandle, &code, &type, message);
        fprintf(stderr,
                "Error: \"%s\" returned error code %s (%d) in function "
                "acquireAndAnalyzeRawData(...)\n%s",
                "MU_activateCalibrationConfig(muHandle)",
                errorEnumName(e),
                e,
                message);
        return NULL;
    }

    uint16_t* masterRawData = malloc(numberOfSamples * sizeof(uint16_t));
    uint16_t* noniusRawData = malloc(numberOfSamples * sizeof(uint16_t));
    if (MU_acquireRawData(
                muHandle,
                masterRawData,
                noniusRawData,
                numberOfSamples,
                slaveId,
                acquireFrameCycleTime_s,
                acquireClockFrequency_hz)) {
        MU_Error lastError;
        MU_ErrorType errorType;
        char errorText[1024];
        MU_GetLastError(muHandle, &lastError, &errorType, errorText);
        fprintf(stderr, "MU_acquireRawData error: %s\n", errorText);

        MU_deactivateCalibrationConfig(muHandle);
        free(masterRawData);
        free(noniusRawData);
        return NULL;
    }

    e = MU_deactivateCalibrationConfig(muHandle);
    if (e != MU_OK) {
        MU_Error code;
        MU_ErrorType type;
        char message[1024];
        MU_GetLastError(muHandle, &code, &type, message);
        fprintf(stderr,
                "Error: \"%s\" returned error code %s (%d) in function "
                "acquireAndAnalyzeRawData(...)\n%s",
                "MU_deactivateCalibrationConfig(muHandle)",
                errorEnumName(e),
                e,
                message);
        free(masterRawData);
        free(noniusRawData);
        return NULL;
    }

    MU_CalibrationAnalyzeResult* analyzeResult = MU_Calibration_analyzeRawData(
            calibration, masterRawData, noniusRawData, numberOfSamples);

    if (setOptimizedNoniusTrackOffsetTable) {
        MU_Calibration_NoniusTrackOffsetTable optimizedNoniusTrackOffsetTable;
        MU_Calibration_getOptimizedNoniusTrackOffsetTable(
                analyzeResult, &optimizedNoniusTrackOffsetTable);
        MU_Calibration_setCurrentNoniusTrackOffsetTable(
                calibration, &optimizedNoniusTrackOffsetTable);

        MU_CalibrationAnalyzeResult_delete(analyzeResult);
        // Generate a new analysis with the optimized nonius track offset table
        analyzeResult = MU_Calibration_analyzeRawData(
                calibration, masterRawData, noniusRawData, numberOfSamples);
    }

    free(masterRawData);
    free(noniusRawData);
    return analyzeResult;
}
