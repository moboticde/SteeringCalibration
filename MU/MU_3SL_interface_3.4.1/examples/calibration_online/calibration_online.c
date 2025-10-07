/*
 * Software and its documentation is provided by iC-Haus GmbH or contributors "AS IS" and is
 * subject to the ZVEI General Conditions for the Supply of Products and Services with iC-Haus
 * amendments and the ZVEI Software clause with iC-Haus amendments (http://www.ichaus.de/EULA).
 */

#include "csv_file.h"
#include "mu_3sl_calibration_adjustments.h"
#include "mu_3sl_check_error_return.h"
#include "MU_3SL_defs.h"
#include "MU_3SL_interface.h"
#include "mu_3sl_nonius_curve.h"

#include <inttypes.h>
#include <math.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>


#if defined(_WIN32) || defined(__WIN32__)
    #include <windows.h>
#elif defined(linux) || defined(__linux) || defined(__APPLE__)
    #include <unistd.h>
#endif


inline void sleepMs(unsigned int ms)
{
#if defined(_WIN32) || defined(__WIN32__)
    Sleep(ms);
#elif defined(linux) || defined(__linux) || defined(__APPLE__)
    usleep(ms * 1000);
#endif
}


int main(int argc, char** argv)
{
    const double acquireFrameCycleTime_s  = 187.5E-6;
    const double acquireClockFrequency_hz = 2E6;
    // Calculation of the number of samples based on acquisition time in seconds
    const double acquisitionTime_s      = 5.0;
    const unsigned long numberOfSamples = lround(acquisitionTime_s / acquireFrameCycleTime_s);
    // const unsigned long numberOfSamples = 10000; // min. 16 (recommended 128) values per period

    const size_t maximumNumberOfAnalogCalibrationRuns             = 3;
    const double permissibleResidualErrorsDuringAnalogCalibration = 1.0;

    const char* noniusCurveCsvFilePath = argc <= 1 ? "nonius_curve.csv" : argv[1];

    const char* calibrationDataExportPath = "";

    uint16_t* masterRawData = malloc(numberOfSamples * sizeof(uint16_t));
    uint16_t* noniusRawData = malloc(numberOfSamples * sizeof(uint16_t));

    // Get the version of the library
    printf("Library version: %s%s\n\n", MU_GetVersionString(), MU_GetVersionSuffixString());

    // Construct a new instance of a virtual chip object and obtain a handle for it.
    MU_Handle muHandle;
    CHECK(MU_Open(&muHandle));

    // Connect the interface (USB-BiSS adapter) MB5U
    CHECK(MU_SetInterface(muHandle, MU_MB5U, ""));

    uint8_t revisionCode = MU_REV_MU128_X1;
    CHECK(MU_ReadChipRevision(muHandle, &revisionCode));
    CHECK(MU_UseRevision(muHandle, revisionCode));

    // Read all configuration parameters from the connected iC-MU* in the virtual chip object
    CHECK(MU_ReadParams(muHandle));

    MU_Calibration* calibration = MU_getCalibration(muHandle);

    uint32_t muMPC;
    CHECK(MU_GetParam(muHandle, MU_MPC, NULL, &muMPC));
    uint8_t masterPeriodCode = (uint8_t)muMPC;


    printf("---------------------------------------------------------------\n"
           "- Reset current analog track adjustments (loaded from EEPROM) -\n"
           "---------------------------------------------------------------\n");

    MU_Calibration_AnalogTrackAdjustments initialMasterAdjustments = {0, 0, 0, 0, 0};
    MU_Calibration_AnalogTrackAdjustments initialNoniusAdjustments = {0, 0, 0, 0, 0};
    MU_Calibration_setCurrentAnalogTrackAdjustments(
            calibration, &initialMasterAdjustments, &initialNoniusAdjustments);
    CHECK(MU_setCalibration(muHandle, calibration));
    CHECK(MU_WriteParams(muHandle, false, NULL));


    printf("Initial iC-MU analog parameters:\n");
    printAnalogAdjustments(calibration);
    printf("\n\n");

    printf("---------------------------------------------------------------\n"
           "------------- Activate calibration configuration --------------\n"
           "---------------------------------------------------------------\n"
           "\n");
    CHECK(MU_activateCalibrationConfig(muHandle));

    MU_CalibrationAnalyzeResult* analyzeResult = NULL;

    for (size_t i = 0; i < maximumNumberOfAnalogCalibrationRuns; ++i) {
        printf("---------------------------------------------------------------\n"
               "---------------------- Acquire raw data -----------------------\n"
               "---------------------------------------------------------------\n"
               "\n");
        if (MU_acquireRawData(
                    muHandle,
                    masterRawData,
                    noniusRawData,
                    numberOfSamples,
                    0,
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
            MU_Calibration_delete(calibration);
            MU_Close(muHandle);
            exit(EXIT_FAILURE);
        }

        char calibrationDataFilePath[256];
        snprintf(
                calibrationDataFilePath,
                sizeof(calibrationDataFilePath) / sizeof(char),
                "%scalibration_data_%" PRIuPTR ".csv",
                calibrationDataExportPath,
                i);
        MU_Calibration_AnalogTrackAdjustments masterTrackAdjustments;
        MU_Calibration_getAnalogMasterTrackAdjustments(calibration, &masterTrackAdjustments);
        MU_Calibration_AnalogTrackAdjustments noniusTrackAdjustments;
        MU_Calibration_getAnalogNoniusTrackAdjustments(calibration, &noniusTrackAdjustments);
        writeCalibrationDataCSVFile(
                masterRawData,
                noniusRawData,
                numberOfSamples,
                calibrationDataFilePath,
                &revisionCode,
                &masterPeriodCode,
                &masterTrackAdjustments,
                &noniusTrackAdjustments);

        printf("---------------------------------------------------------------\n"
               "---------------------- Analyze raw data  ----------------------\n"
               "---------------------------------------------------------------\n");
        if (analyzeResult != NULL) {
            MU_CalibrationAnalyzeResult_delete(analyzeResult);
        }
        analyzeResult = MU_Calibration_analyzeRawData(
                calibration, masterRawData, noniusRawData, numberOfSamples);
        if (analyzeResult == NULL) {
            fprintf(stderr, "Raw data are not analyzable\n");
            MU_deactivateCalibrationConfig(muHandle);
            free(masterRawData);
            free(noniusRawData);
            MU_Calibration_delete(calibration);
            MU_Close(muHandle);
            exit(EXIT_FAILURE);
        }

        printAnalyzeResultLog(analyzeResult);

        printf("Residual errors (relative changes in \"LSB\")\n");
        printRelativeAdjustments(analyzeResult);

        printAnalogAnalyzeResultAdjustableLog(calibration, analyzeResult);

        MU_Calibration_RelativeAnalogTrackAdjustments relativeMasterTrackAdjustments;
        MU_Calibration_getRelativeMasterTrackAdjustments(
                analyzeResult, &relativeMasterTrackAdjustments);
        MU_Calibration_RelativeAnalogTrackAdjustments relativeNoniusTrackAdjustments;
        MU_Calibration_getRelativeNoniusTrackAdjustments(
                analyzeResult, &relativeNoniusTrackAdjustments);

        if (fabs(relativeMasterTrackAdjustments.cosineGain_lsb)
                    <= permissibleResidualErrorsDuringAnalogCalibration
            && fabs(relativeNoniusTrackAdjustments.cosineGain_lsb)
                       <= permissibleResidualErrorsDuringAnalogCalibration
            && fabs(relativeMasterTrackAdjustments.sineOffset_lsb)
                       <= permissibleResidualErrorsDuringAnalogCalibration
            && fabs(relativeNoniusTrackAdjustments.sineOffset_lsb)
                       <= permissibleResidualErrorsDuringAnalogCalibration
            && fabs(relativeMasterTrackAdjustments.cosineOffset_lsb)
                       <= permissibleResidualErrorsDuringAnalogCalibration
            && fabs(relativeNoniusTrackAdjustments.cosineOffset_lsb)
                       <= permissibleResidualErrorsDuringAnalogCalibration
            && fabs(relativeMasterTrackAdjustments.phase_lsb)
                       <= permissibleResidualErrorsDuringAnalogCalibration
            && fabs(relativeNoniusTrackAdjustments.phase_lsb)
                       <= permissibleResidualErrorsDuringAnalogCalibration) {
            printf("\n"
                   "All residual errors (absolute relative changes in \"LSB\") are smaller than "
                   "%.3f.\n"
                   "From this point, no further analog calibration step would be required.\n"
                   "\n",
                   permissibleResidualErrorsDuringAnalogCalibration);
            break;
        }

        printf("---------------------------------------------------------------\n"
               "------------ Adjust the analyzed analog parameters ------------\n"
               "---------------------------------------------------------------\n");

        MU_Calibration_adjustAnalogByAnalyzeResult(calibration, analyzeResult);

        printf("iC-MU analog parameters after adjustment:\n");
        printAnalogAdjustments(calibration);
        printf("\n\n");

        MU_setCalibration(muHandle, calibration);
        CHECK(MU_WriteParams(muHandle, false, NULL));
    }

    printf("\n"
           "---------------------------------------------------------------\n"
           "------------ Adjust the analyzed nonius parameters ------------\n"
           "---------------------------------------------------------------\n"
           "\n");

    MU_Calibration_NoniusTrackOffsetTable optimizedNoniusTrackOffsetTable;
    MU_Calibration_getOptimizedNoniusTrackOffsetTable(
            analyzeResult, &optimizedNoniusTrackOffsetTable);
    MU_Calibration_setCurrentNoniusTrackOffsetTable(calibration, &optimizedNoniusTrackOffsetTable);

    MU_CalibrationAnalyzeResult_delete(analyzeResult);
    // Generate a new analysis with the optimized nonius track offset table
    analyzeResult = MU_Calibration_analyzeRawData(
            calibration, masterRawData, noniusRawData, numberOfSamples);

    optionalPrintOptimizedNoniusTrackOffsetTable(analyzeResult, noniusCurveCsvFilePath);
    printf("\n");
    optionalPrintOptimizedNoniusTrackOffsetParameters(analyzeResult);

    MU_setCalibration(muHandle, calibration);
    CHECK(MU_WriteParams(muHandle, false, NULL));

    MU_CalibrationAnalyzeResult_delete(analyzeResult);
    MU_Calibration_delete(calibration);

    printf("\n"
           "---------------------------------------------------------------\n"
           "------------ Deactivate calibration configuration -------------\n"
           "---------------------------------------------------------------\n");
    CHECK(MU_deactivateCalibrationConfig(muHandle));

    printf("\n"
           "---------------------------------------------------------------\n"
           "------------- iC-MU CRC calculation and reset ABS -------------\n"
           "---------------------------------------------------------------\n");

    CHECK(MU_WriteCmdRegister(muHandle, MU_CMD_CRC_CALC));
    CHECK(MU_WriteCmdRegister(muHandle, MU_CMD_ABS_RESET));

    printf("\n"
           "---------------------------------------------------------------\n"
           "---------- Save the configuration in the chip EEPROM ----------\n"
           "---------------------------------------------------------------\n");

    CHECK(MU_WriteCmdRegister(muHandle, MU_CMD_WRITE_ALL));

    free(masterRawData);
    free(noniusRawData);
    MU_Close(muHandle);

    return EXIT_SUCCESS;
}
