/*
 * Software and its documentation is provided by iC-Haus GmbH or contributors "AS IS" and is
 * subject to the ZVEI General Conditions for the Supply of Products and Services with iC-Haus
 * amendments and the ZVEI Software clause with iC-Haus amendments (http://www.ichaus.de/EULA).
 */

/*
 * This sample shows how to calibrate a 3 track iC-MU system like the iC-MU1D with two iC-MUs.
 * This calibration expects 2 iC-MU within an BiSS-Chain. It will not work if one has a shorter or
 * longer BiSS Chain.
 * For this example we assume, that a 256 nonius system is used.
 * Because of the power consumption of 2 iC-MUs within a BiSS chain and the limited power supply of
 a USB port,
 * it is highly recommended to use an external power supply.
 */

#include "MU_3SL_defs.h"
#include "MU_3SL_interface.h"

#include "mu_3sl_calibration_adjustments.h"
#include "mu_3sl_check_error_return.h"
#include "mu_3sl_mt_curve.h"
#include "mu_3sl_nonius_curve.h"

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


void sleepMs(unsigned int ms)
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
    const double acquisitionTime_s = 5.0;
    const unsigned long numberOfSamples = lround(acquisitionTime_s / acquireFrameCycleTime_s);
    // const unsigned long numberOfSamples = 10000; // min. 16 (recommended 128) values per period
    const size_t numberOfSynchronizationDataSamples = 5000;

    const char* mu1NoniusCurveCsvFilePath = argc <= 1 ? "mu1_nonius_curve.csv" : argv[1];
    const char* mu2NoniusCurveCsvFilePath = argc <= 2 ? "mu2_nonius_curve.csv" : argv[2];
    const char* mtSyncCurveCsvFilePath    = argc <= 3 ? "mt_sync_curve.csv" : argv[3];

    const char* mu1ConfigFilePath = "resources/MU2M_MU_default_128_3-track_MU1_ST_200529.cfg";
    const char* mu2ConfigFilePath = "resources/MU2M_MU_default_128_3-track_MU2_MT_210622.cfg";

    uint16_t* masterRawData = (uint16_t*)malloc(numberOfSamples * sizeof(uint16_t));
    uint16_t* noniusRawData = (uint16_t*)malloc(numberOfSamples * sizeof(uint16_t));

    const size_t adjustmentMessageSize = 1024;
    char* adjustmentMessage            = (char*)malloc(adjustmentMessageSize * sizeof(char));

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


    // Check number of detected BiSS slaves
    uint32_t slaveCount;
    MU_GetConfig(muHandle, MU_SLAVE_COUNT, &slaveCount);
    if (slaveCount == 1) {
        // If only one slave is found, it is possible that GetMT is not already activated
        // Enable GetMT => active BiSS-Chain during calibration process
        uint32_t modeA;
        bool switched;
        CHECK(MU_EnableGetMT(muHandle, &modeA, &switched));
        MU_GetConfig(muHandle, MU_SLAVE_COUNT, &slaveCount);
    }
    if (slaveCount != 2) {
        fprintf(stderr, "Could not detect a 3-track system!\n");
        MU_Close(muHandle);
        return EXIT_FAILURE;
    }

    printf("\n"
           "---------------------------------------------------------------\n"
           "----------------- Setup iC-MU 1 (single turn) -----------------\n"
           "---------------------------------------------------------------\n");

    // Switch to the single turn iC-MU
    CHECK(MU_SetConfig(muHandle, MU_SLAVE_ID, 1));

    MU_Error error = MU_LoadParams(muHandle, mu1ConfigFilePath);
    if (error != MU_OK) {
        if (error == MU_CONTRADICTORY_REVISIONS) {
            fprintf(stderr,
                    "The Chip Revision of the file does not match to the connected iC-MU!\n"
                    "Please generate a new file with the correct chip revision\n");
        } else {
            fprintf(stderr, "Loading parameters failed!");
        }
        MU_Close(muHandle);
        return EXIT_FAILURE;
    }

    // Keep parameter GET_MT activated for the 3-Track calibration
    CHECK(MU_SetParam(muHandle, MU_GET_MT, 0, 1, MU_SETONLY));
    // Write configuration to iC-MU single turn without verification
    CHECK(MU_WriteParams(muHandle, false, NULL));

    CHECK(MU_WriteCmdRegister(muHandle, MU_CMD_CRC_CALC));
    CHECK(MU_WriteCmdRegister(muHandle, MU_CMD_ABS_RESET));


    printf("\n"
           "---------------------------------------------------------------\n"
           "------------------ Setup iC-MU 2 (multi turn) -----------------\n"
           "---------------------------------------------------------------\n");

    // Switch to the multi turn iC-MU
    CHECK(MU_SetConfig(muHandle, MU_SLAVE_ID, 0));

    CHECK(MU_LoadParams(muHandle, mu2ConfigFilePath));

    // Keep parameter of the iC-MU multi turn MODEA in BiSS mode
    CHECK(MU_SetParam(muHandle, MU_MODEA, 0, 2, MU_SETONLY));
    CHECK(MU_WriteParams(muHandle, false, NULL));

    CHECK(MU_WriteCmdRegister(muHandle, MU_CMD_CRC_CALC));
    CHECK(MU_WriteCmdRegister(muHandle, MU_CMD_ABS_RESET));


    printf("\n"
           "---------------------------------------------------------------\n"
           "------------------- Calibration of iC-MU 2 --------------------\n"
           "---------------------------------------------------------------\n");

    // Switch to the multi turn iC-MU
    CHECK(MU_SetConfig(muHandle, MU_SLAVE_ID, 0));
    // Synchronize with the chosen slave
    CHECK(MU_ReadParams(muHandle));

    MU_Calibration* mu2Calibration = MU_getCalibration(muHandle);

    uint32_t mu2MasterPeriodCode;
    CHECK(MU_GetParam(muHandle, MU_MPC, NULL, &mu2MasterPeriodCode));


    printf("Initial multi turn iC-MU signal conditioning parameters:\n");
    printAnalogAdjustments(mu2Calibration);
    printf("\n\n");


    printf("\n"
           "---------------------------------------------------------------\n"
           "---------------- Analog Calibration of iC-MU 2 ----------------\n"
           "---------------------------------------------------------------\n");

    CHECK(MU_activateCalibrationConfig(muHandle));
    uint32_t currentSlaveId = 0;
    MU_GetConfig(muHandle, MU_SLAVE_ID, &currentSlaveId);
    if (MU_acquireRawData(
                muHandle,
                masterRawData,
                noniusRawData,
                numberOfSamples,
                currentSlaveId,
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
        MU_Calibration_delete(mu2Calibration);
        MU_Close(muHandle);
        return EXIT_FAILURE;
    }
    CHECK(MU_deactivateCalibrationConfig(muHandle));

    MU_CalibrationAnalyzeResult* mu2AnalyzeResult = MU_Calibration_analyzeRawData(
            mu2Calibration, masterRawData, noniusRawData, numberOfSamples);

    if (mu2AnalyzeResult == NULL) {
        fprintf(stderr, "Raw data are not analyzable\n");
        free(masterRawData);
        free(noniusRawData);
        MU_Calibration_delete(mu2Calibration);
        MU_Close(muHandle);
        return EXIT_FAILURE;
    }

    size_t mu2AnalyzeResultLogSize =
            MU_Calibration_getAnalyzeResultLog(
                    mu2AnalyzeResult, NULL, 0, MU_CALIBRATION_ANALYZE_RESULT_LOG_ALL)
            + 1;
    char* mu2AnalyzeResultLogMessage = (char*)malloc(mu2AnalyzeResultLogSize * sizeof(char));
    MU_Calibration_getAnalyzeResultLog(
            mu2AnalyzeResult,
            mu2AnalyzeResultLogMessage,
            mu2AnalyzeResultLogSize,
            MU_CALIBRATION_ANALYZE_RESULT_LOG_ALL);
    printf("%s\n", mu2AnalyzeResultLogMessage);
    free(mu2AnalyzeResultLogMessage);

    MU_Calibration_RelativeAnalogTrackAdjustments mu2RelativeMasterTrackAdjustments;
    MU_Calibration_getRelativeMasterTrackAdjustments(
            mu2AnalyzeResult, &mu2RelativeMasterTrackAdjustments);
    MU_Calibration_RelativeAnalogTrackAdjustments mu2RelativeNoniusTrackAdjustments;
    MU_Calibration_getRelativeNoniusTrackAdjustments(
            mu2AnalyzeResult, &mu2RelativeNoniusTrackAdjustments);

    printf("Relative track adjustments (relative changes in \"LSB\")\n"
           "Track:             Master |   Nonius\n"
           "  Cosine gain:   %8.4f | %8.4f\n"
           "  Sine offset:   %8.4f | %8.4f\n"
           "  Cosine offset: %8.4f | %8.4f\n"
           "  Phase adjust:  %8.4f | %8.4f\n\n",
           mu2RelativeMasterTrackAdjustments.cosineGain_lsb,
           mu2RelativeNoniusTrackAdjustments.cosineGain_lsb,
           mu2RelativeMasterTrackAdjustments.sineOffset_lsb,
           mu2RelativeNoniusTrackAdjustments.sineOffset_lsb,
           mu2RelativeMasterTrackAdjustments.cosineOffset_lsb,
           mu2RelativeNoniusTrackAdjustments.cosineOffset_lsb,
           mu2RelativeMasterTrackAdjustments.phase_lsb,
           mu2RelativeNoniusTrackAdjustments.phase_lsb);

    printAnalogAnalyzeResultAdjustableLog(mu2Calibration, mu2AnalyzeResult);

    MU_Calibration_adjustAnalogByAnalyzeResult(mu2Calibration, mu2AnalyzeResult);

    printf("iC-MU signal conditioning parameters after calibration:\n");
    printAnalogAdjustments(mu2Calibration);
    printf("\n\n");

    MU_setCalibration(muHandle, mu2Calibration);
    CHECK(MU_WriteParams(muHandle, false, NULL));

    MU_CalibrationAnalyzeResult_delete(mu2AnalyzeResult);


    printf("\n"
           "---------------------------------------------------------------\n"
           "---------------- Nonius Calibration of iC-MU 2 ----------------\n"
           "---------------------------------------------------------------\n");

    CHECK(MU_activateCalibrationConfig(muHandle));
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

        free(masterRawData);
        free(noniusRawData);
        MU_Calibration_delete(mu2Calibration);
        MU_Close(muHandle);
        return EXIT_FAILURE;
    }
    CHECK(MU_deactivateCalibrationConfig(muHandle));

    mu2AnalyzeResult = MU_Calibration_analyzeRawData(
            mu2Calibration, masterRawData, noniusRawData, numberOfSamples);

    if (mu2AnalyzeResult == NULL) {
        fprintf(stderr, "Raw data are not analyzable\n");
        free(masterRawData);
        free(noniusRawData);
        MU_Calibration_delete(mu2Calibration);
        MU_Close(muHandle);
        return EXIT_FAILURE;
    }

    mu2AnalyzeResultLogSize =
            MU_Calibration_getAnalyzeResultLog(
                    mu2AnalyzeResult, NULL, 0, MU_CALIBRATION_ANALYZE_RESULT_LOG_ALL)
            + 1;
    mu2AnalyzeResultLogMessage = (char*)malloc(sizeof(char) * mu2AnalyzeResultLogSize);
    MU_Calibration_getAnalyzeResultLog(
            mu2AnalyzeResult,
            mu2AnalyzeResultLogMessage,
            mu2AnalyzeResultLogSize,
            MU_CALIBRATION_ANALYZE_RESULT_LOG_ALL);
    printf("%s\n", mu2AnalyzeResultLogMessage);
    free(mu2AnalyzeResultLogMessage);


    MU_Calibration_getRelativeMasterTrackAdjustments(
            mu2AnalyzeResult, &mu2RelativeMasterTrackAdjustments);
    MU_Calibration_getRelativeNoniusTrackAdjustments(
            mu2AnalyzeResult, &mu2RelativeNoniusTrackAdjustments);
    printf("Relative track adjustments (relative changes in \"LSB\")\n"
           "Track:             Master |   Nonius\n"
           "  Cosine gain:   %8.4f | %8.4f\n"
           "  Sine offset:   %8.4f | %8.4f\n"
           "  Cosine offset: %8.4f | %8.4f\n"
           "  Phase adjust:  %8.4f | %8.4f\n\n",
           mu2RelativeMasterTrackAdjustments.cosineGain_lsb,
           mu2RelativeNoniusTrackAdjustments.cosineGain_lsb,
           mu2RelativeMasterTrackAdjustments.sineOffset_lsb,
           mu2RelativeNoniusTrackAdjustments.sineOffset_lsb,
           mu2RelativeMasterTrackAdjustments.cosineOffset_lsb,
           mu2RelativeNoniusTrackAdjustments.cosineOffset_lsb,
           mu2RelativeMasterTrackAdjustments.phase_lsb,
           mu2RelativeNoniusTrackAdjustments.phase_lsb);

    MU_Calibration_NoniusTrackOffsetTable mu2OptimizedNoniusTrackOffsetTable;
    MU_Calibration_getOptimizedNoniusTrackOffsetTable(
            mu2AnalyzeResult, &mu2OptimizedNoniusTrackOffsetTable);
    MU_Calibration_setCurrentNoniusTrackOffsetTable(
            mu2Calibration, &mu2OptimizedNoniusTrackOffsetTable);
    MU_CalibrationAnalyzeResult_delete(mu2AnalyzeResult);
    // Generate a new analysis with the optimized nonius track offset table
    mu2AnalyzeResult = MU_Calibration_analyzeRawData(
            mu2Calibration, masterRawData, noniusRawData, numberOfSamples);

    optionalPrintOptimizedNoniusTrackOffsetTable(mu2AnalyzeResult, mu2NoniusCurveCsvFilePath);

    MU_setCalibration(muHandle, mu2Calibration);
    CHECK(MU_WriteParams(muHandle, false, NULL));

    CHECK(MU_WriteCmdRegister(muHandle, MU_CMD_WRITE_ALL));

    CHECK(MU_WriteCmdRegister(muHandle, MU_CMD_CRC_CALC));
    CHECK(MU_WriteCmdRegister(muHandle, MU_CMD_ABS_RESET));

    const uint32_t MODEA_SSI_ERRL = 5;
    CHECK(MU_WriteSwitchCommand(muHandle, MODEA_SSI_ERRL, 0));

    MU_CalibrationAnalyzeResult_delete(mu2AnalyzeResult);
    MU_Calibration_delete(mu2Calibration);



    printf("\n"
           "---------------------------------------------------------------\n"
           "------------------- Calibration of iC-MU 1 --------------------\n"
           "---------------------------------------------------------------\n");

    // Switch to the single turn iC-MU
    CHECK(MU_SetConfig(muHandle, MU_SLAVE_ID, 1));
    // Synchronize with the chosen slave
    CHECK(MU_ReadParams(muHandle));

    MU_Calibration* mu1Calibration = MU_getCalibration(muHandle);

    uint32_t mu1MasterPeriodCode;
    MU_GetParam(muHandle, MU_MPC, NULL, &mu1MasterPeriodCode);


    printf("Initial single turn iC-MU signal conditioning parameters:\n");
    printAnalogAdjustments(mu1Calibration);
    printf("\n\n");


    printf("\n"
           "---------------------------------------------------------------\n"
           "---------------- Analog Calibration of iC-MU 1 ----------------\n"
           "---------------------------------------------------------------\n");

    CHECK(MU_activateCalibrationConfig(
            muHandle)); // Disables GET_MT-> Changes the BiSS chain;
                        // call MU_deactivateCalibrationConfig to reset the GET_MT state.
    MU_GetConfig(
            muHandle,
            MU_SLAVE_ID,
            &currentSlaveId); // Get the new slave ID in the changed BiSS chain
    if (MU_acquireRawData(
                muHandle,
                masterRawData,
                noniusRawData,
                numberOfSamples,
                currentSlaveId,
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
        MU_Calibration_delete(mu1Calibration);
        MU_Close(muHandle);
        return EXIT_FAILURE;
    }
    CHECK(MU_deactivateCalibrationConfig(muHandle));

    MU_CalibrationAnalyzeResult* mu1AnalyzeResult = MU_Calibration_analyzeRawData(
            mu1Calibration, masterRawData, noniusRawData, numberOfSamples);

    if (mu1AnalyzeResult == NULL) {
        fprintf(stderr, "Raw data are not analyzable\n");
        free(masterRawData);
        free(noniusRawData);
        MU_Calibration_delete(mu1Calibration);
        MU_Close(muHandle);
        return EXIT_FAILURE;
    }

    size_t mu1AnalyzeResultLogSize =
            MU_Calibration_getAnalyzeResultLog(
                    mu1AnalyzeResult, NULL, 0, MU_CALIBRATION_ANALYZE_RESULT_LOG_ALL)
            + 1;
    char* mu1AnalyzeResultLogMessage = (char*)malloc(mu1AnalyzeResultLogSize * sizeof(char));
    MU_Calibration_getAnalyzeResultLog(
            mu1AnalyzeResult,
            mu1AnalyzeResultLogMessage,
            mu1AnalyzeResultLogSize,
            MU_CALIBRATION_ANALYZE_RESULT_LOG_ALL);
    printf("%s\n", mu1AnalyzeResultLogMessage);
    free(mu1AnalyzeResultLogMessage);

    MU_Calibration_RelativeAnalogTrackAdjustments mu1RelativeMasterTrackAdjustments;
    MU_Calibration_getRelativeMasterTrackAdjustments(
            mu1AnalyzeResult, &mu1RelativeMasterTrackAdjustments);
    MU_Calibration_RelativeAnalogTrackAdjustments mu1RelativeNoniusTrackAdjustments;
    MU_Calibration_getRelativeNoniusTrackAdjustments(
            mu1AnalyzeResult, &mu1RelativeNoniusTrackAdjustments);

    printf("Relative track adjustments (relative changes in \"LSB\")\n"
           "Track:             Master |   Nonius\n"
           "  Cosine gain:   %8.4f | %8.4f\n"
           "  Sine offset:   %8.4f | %8.4f\n"
           "  Cosine offset: %8.4f | %8.4f\n"
           "  Phase adjust:  %8.4f | %8.4f\n\n",
           mu1RelativeMasterTrackAdjustments.cosineGain_lsb,
           mu1RelativeNoniusTrackAdjustments.cosineGain_lsb,
           mu1RelativeMasterTrackAdjustments.sineOffset_lsb,
           mu1RelativeNoniusTrackAdjustments.sineOffset_lsb,
           mu1RelativeMasterTrackAdjustments.cosineOffset_lsb,
           mu1RelativeNoniusTrackAdjustments.cosineOffset_lsb,
           mu1RelativeMasterTrackAdjustments.phase_lsb,
           mu1RelativeNoniusTrackAdjustments.phase_lsb);

    printAnalogAnalyzeResultAdjustableLog(mu1Calibration, mu1AnalyzeResult);

    MU_Calibration_adjustAnalogByAnalyzeResult(mu1Calibration, mu1AnalyzeResult);

    printf("iC-MU signal conditioning parameters after calibration:\n");
    printAnalogAdjustments(mu1Calibration);
    printf("\n\n");

    MU_setCalibration(muHandle, mu1Calibration);
    CHECK(MU_WriteParams(muHandle, false, NULL));

    MU_CalibrationAnalyzeResult_delete(mu1AnalyzeResult);


    printf("\n"
           "---------------------------------------------------------------\n"
           "---------------- Nonius Calibration of iC-MU 1 ----------------\n"
           "---------------------------------------------------------------\n");

    CHECK(MU_activateCalibrationConfig(muHandle));
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

        free(masterRawData);
        free(noniusRawData);
        MU_Calibration_delete(mu1Calibration);
        MU_Close(muHandle);
        return EXIT_FAILURE;
    }
    CHECK(MU_deactivateCalibrationConfig(muHandle));

    mu1AnalyzeResult = MU_Calibration_analyzeRawData(
            mu1Calibration, masterRawData, noniusRawData, numberOfSamples);

    if (mu1AnalyzeResult == NULL) {
        fprintf(stderr, "Raw data are not analyzable\n");
        free(masterRawData);
        free(noniusRawData);
        MU_Calibration_delete(mu1Calibration);
        MU_Close(muHandle);
        return EXIT_FAILURE;
    }

    mu1AnalyzeResultLogSize =
            MU_Calibration_getAnalyzeResultLog(
                    mu1AnalyzeResult, NULL, 0, MU_CALIBRATION_ANALYZE_RESULT_LOG_ALL)
            + 1;
    mu1AnalyzeResultLogMessage = (char*)malloc(sizeof(char) * mu1AnalyzeResultLogSize);
    MU_Calibration_getAnalyzeResultLog(
            mu1AnalyzeResult,
            mu1AnalyzeResultLogMessage,
            mu1AnalyzeResultLogSize,
            MU_CALIBRATION_ANALYZE_RESULT_LOG_ALL);
    printf("%s\n", mu1AnalyzeResultLogMessage);
    free(mu1AnalyzeResultLogMessage);



    MU_Calibration_getRelativeMasterTrackAdjustments(
            mu1AnalyzeResult, &mu1RelativeMasterTrackAdjustments);
    MU_Calibration_getRelativeNoniusTrackAdjustments(
            mu1AnalyzeResult, &mu1RelativeNoniusTrackAdjustments);
    printf("Relative track adjustments (relative changes in \"LSB\")\n"
           "Track:             Master |   Nonius\n"
           "  Cosine gain:   %8.4f | %8.4f\n"
           "  Sine offset:   %8.4f | %8.4f\n"
           "  Cosine offset: %8.4f | %8.4f\n"
           "  Phase adjust:  %8.4f | %8.4f\n\n",
           mu1RelativeMasterTrackAdjustments.cosineGain_lsb,
           mu1RelativeNoniusTrackAdjustments.cosineGain_lsb,
           mu1RelativeMasterTrackAdjustments.sineOffset_lsb,
           mu1RelativeNoniusTrackAdjustments.sineOffset_lsb,
           mu1RelativeMasterTrackAdjustments.cosineOffset_lsb,
           mu1RelativeNoniusTrackAdjustments.cosineOffset_lsb,
           mu1RelativeMasterTrackAdjustments.phase_lsb,
           mu1RelativeNoniusTrackAdjustments.phase_lsb);

    printAnalogAnalyzeResultAdjustableLog(mu1Calibration, mu1AnalyzeResult);

    MU_Calibration_adjustAnalogByAnalyzeResult(mu1Calibration, mu1AnalyzeResult);

    MU_Calibration_NoniusTrackOffsetTable mu1OptimizedNoniusTrackOffsetTable;
    MU_Calibration_getOptimizedNoniusTrackOffsetTable(
            mu1AnalyzeResult, &mu1OptimizedNoniusTrackOffsetTable);
    MU_Calibration_setCurrentNoniusTrackOffsetTable(
            mu1Calibration, &mu1OptimizedNoniusTrackOffsetTable);
    MU_CalibrationAnalyzeResult_delete(mu1AnalyzeResult);
    // Generate a new analysis with the optimized nonius track offset table
    mu1AnalyzeResult = MU_Calibration_analyzeRawData(
            mu1Calibration, masterRawData, noniusRawData, numberOfSamples);

    optionalPrintOptimizedNoniusTrackOffsetTable(mu1AnalyzeResult, mu1NoniusCurveCsvFilePath);

    MU_setCalibration(muHandle, mu1Calibration);
    CHECK(MU_WriteParams(muHandle, false, NULL));

    CHECK(MU_WriteCmdRegister(muHandle, MU_CMD_CRC_CALC));
    CHECK(MU_WriteCmdRegister(muHandle, MU_CMD_ABS_RESET));

    MU_CalibrationAnalyzeResult_delete(mu1AnalyzeResult);
    MU_Calibration_delete(mu1Calibration);


    printf("\n"
           "---------------------------------------------------------------\n"
           "----------------- Multi Turn Synchronization ------------------\n"
           "---------------------------------------------------------------\n");

    // Switch to the single turn iC-MU
    CHECK(MU_SetConfig(muHandle, MU_SLAVE_ID, 1));
    // Synchronize with the chosen slave
    CHECK(MU_ReadParams(muHandle));

    MU_MtSyncData* synchronizationData =
            (MU_MtSyncData*)malloc(numberOfSynchronizationDataSamples * sizeof(MU_MtSyncData));
    CHECK(MU_activate3TrackMtSyncConfig(muHandle));
    CHECK(MU_acquire3TrackMtSyncData(
            muHandle, synchronizationData, numberOfSynchronizationDataSamples));
    CHECK(MU_deactivate3TrackMtSyncConfig(muHandle));

    MU_MtSync* mtSynchronization        = MU_getMtSync(muHandle);
    MU_MtAnalyzeResult* mtAnalyzeResult = MU_MtSync_analyzeData(
            mtSynchronization, synchronizationData, numberOfSynchronizationDataSamples);

    uint8_t optimalSpoMt = MU_MtAnalyzeResult_optimalSpoMt(mtAnalyzeResult);
    printf("optimal SPO_MT = %i\n", (int)optimalSpoMt);

    const uint64_t systemResolution = 1ull << (mu2MasterPeriodCode + 14);
    optionalMtOffsetErrorData(
            synchronizationData,
            numberOfSynchronizationDataSamples,
            mtSynchronization,
            mtAnalyzeResult,
            optimalSpoMt,
            systemResolution,
            mtSyncCurveCsvFilePath);
    free(synchronizationData);

    MU_updateMtSync(muHandle, mtAnalyzeResult);

    CHECK(MU_WriteParams(muHandle, false, NULL));

    CHECK(MU_DisableGetMT(muHandle));
    CHECK(MU_WriteCmdRegister(muHandle, MU_CMD_WRITE_ALL));

    MU_MtAnalyzeResult_delete(mtAnalyzeResult);


    printf("\n"
           "---------------------------------------------------------------\n"
           "----------------------> Power Reset <--------------------------\n"
           "---------------------------------------------------------------\n\n");
    MU_SetInterface(muHandle, MU_NO_INTERFACE, "");
    sleepMs(500);
    CHECK(MU_SetInterface(muHandle, MU_MB5U, ""));

    MU_SetConfig(muHandle, MU_SLAVE_ID, 0);
    CHECK(MU_ReadParams(muHandle));


    free(adjustmentMessage);
    free(masterRawData);
    free(noniusRawData);
    MU_Close(muHandle);

    return EXIT_SUCCESS;
}
