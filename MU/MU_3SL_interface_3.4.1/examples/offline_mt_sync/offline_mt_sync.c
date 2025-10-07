/*
 * Software and its documentation is provided by iC-Haus GmbH or contributors "AS IS" and is
 * subject to the ZVEI General Conditions for the Supply of Products and Services with iC-Haus
 * amendments and the ZVEI Software clause with iC-Haus amendments (http://www.ichaus.de/EULA).
 */

#include "MU_3SL_defs.h"
#include "MU_3SL_interface.h"

#include "csv_file.h"
#include "mu_3sl_mt_curve.h"

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>


int main(int argc, char** argv)
{
    const char* filepath            = argc <= 1 ? "resources/mu_pvl_mt_sync_data.csv" : argv[1];
    const uint32_t masterPeriodCode = argc <= 2 ? 4 : strtol(argv[2], NULL, 0);
    const uint32_t numberOfMultiTurnBits = argc <= 3 ? 3 : strtol(argv[3], NULL, 0);
    const uint8_t revisionCode           = argc <= 4 ? MU_REV_MU128_X1 : strtol(argv[4], NULL, 0);

    const char* mtSyncCurveCsvFilePath = argc <= 5 ? "mt_sync_curve.csv" : argv[5];

    const unsigned int numberOfMasterPeriods   = 1u << masterPeriodCode;
    const uint64_t systemResolution = 1ull << (numberOfMultiTurnBits + masterPeriodCode + 14);

    const size_t numberOfMultiTurnSynchronizationBits = 4;
    const bool multiTurnMovementIsReverse             = true;

    printf("Library version: %s%s\n\n", MU_GetVersionString(), MU_GetVersionSuffixString());

    size_t numberOfSamples  = 0;
    MU_MtSyncData* syncData = NULL;
    printf("Read multi turn synchronization data from file: \"%s\"\n\n", filepath);
    if (readMtSyncCSVFile(&syncData, &numberOfSamples, filepath, 1) < 0) {
        fprintf(stderr, "Error: Unable to read data file!\n");
        return EXIT_FAILURE;
    }


    printf("\n"
           "---------------------------------------------------------------\n"
           "----------------- Multi Turn Synchronization ------------------\n"
           "---------------------------------------------------------------\n");

    MU_Calibration* calibration = MU_createCalibration(revisionCode);
    MU_Calibration_preconfigureNumberOfMasterPeriods(calibration, numberOfMasterPeriods);
    MU_MtSync* mtSynchronization = MU_createMtSync(
            calibration, numberOfMultiTurnSynchronizationBits, multiTurnMovementIsReverse);

    MU_MtAnalyzeResult* mtAnalyzeResult =
            MU_MtSync_analyzeData(mtSynchronization, syncData, numberOfSamples);

    uint8_t optimalSpoMt = MU_MtAnalyzeResult_optimalSpoMt(mtAnalyzeResult);
    printf("optimal SPO_MT = %i\n", (int)optimalSpoMt);


    optionalMtOffsetErrorData(
            syncData,
            numberOfSamples,
            mtSynchronization,
            mtAnalyzeResult,
            optimalSpoMt,
            systemResolution,
            mtSyncCurveCsvFilePath);

    free(syncData);
    MU_MtAnalyzeResult_delete(mtAnalyzeResult);

    return EXIT_SUCCESS;
}
