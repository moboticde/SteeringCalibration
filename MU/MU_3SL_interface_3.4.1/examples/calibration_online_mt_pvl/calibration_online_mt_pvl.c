/*
 * Software and its documentation is provided by iC-Haus GmbH or contributors "AS IS" and is
 * subject to the ZVEI General Conditions for the Supply of Products and Services with iC-Haus
 * amendments and the ZVEI Software clause with iC-Haus amendments (http://www.ichaus.de/EULA).
 */

#include "MU_3SL_defs.h"
#include "MU_3SL_interface.h"

#include "mu_3sl_analog_nonius_calibration.h"
#include "mu_3sl_calibration_adjustments.h"
#include "mu_3sl_check_error_return.h"
#include "mu_3sl_mt_curve.h"
#include "mu_3sl_nonius_curve.h"

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

#define NUMBER_OF_PVL_EEPROM_REGISTERS (0x100)
#define PVL_REGISTER_CMD               (0x11)
#define PVL_CMD_REBOOT                 (0x03)
#define PVL_CMD_SCLR                   (0x05)


int main(int argc, char** argv)
{
    const double acquireFrameCycleTime_s  = 187.5E-6;
    const double acquireClockFrequency_hz = 2E6;
    // Calculation of the number of samples based on acquisition time in seconds
    const double acquisitionTime_s = 5.0;
    const unsigned long numberOfSamples = lround(acquisitionTime_s / acquireFrameCycleTime_s);
    // const unsigned long numberOfSamples = 20000; // min. 16 (recommended 128) values per period
    const size_t numberOfSynchronizationDataSamples = 5000;

    const char* noniusCurveCsvFilePath = argc <= 1 ? "nonius_curve.csv" : argv[1];
    const char* mtSyncCurveCsvFilePath = argc <= 2 ? "mt_sync_curve.csv" : argv[2];

    const char* muConfigFilePath  = "resources/ic_mu.cfg";
    const char* pvlConfigFilePath = "resources/ic_pvl.cfg";

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


    printf("\n"
           "---------------------------------------------------------------\n"
           "------------------ Setup iC-MU (single turn) ------------------\n"
           "---------------------------------------------------------------\n");

    MU_Error error = MU_LoadParams(muHandle, muConfigFilePath);
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

    // Write configuration to iC-MU without verification
    CHECK(MU_WriteParams(muHandle, false, NULL));
    CHECK(MU_WriteCmdRegister(muHandle, MU_CMD_CRC_CALC));


    printf("\n"
           "---------------------------------------------------------------\n"
           "------------------ Setup iC-PVL (multi turn) ------------------\n"
           "---------------------------------------------------------------\n");

    const uint8_t eepromI2cAddress = 0x50;
    const uint8_t pvlI2cAddress    = 0x61;
    uint32_t registerData[NUMBER_OF_PVL_EEPROM_REGISTERS];
    bool registerValid[NUMBER_OF_PVL_EEPROM_REGISTERS];
    CHECK(MU_LoadRegisterEx(
            muHandle,
            pvlConfigFilePath,
            NUMBER_OF_PVL_EEPROM_REGISTERS,
            registerData,
            registerValid));

    // Write configuration to the EEPROM at I2C device ID 0x50
    CHECK(MU_WriteRegister_I2C_Ex(
            muHandle,
            NUMBER_OF_PVL_EEPROM_REGISTERS,
            eepromI2cAddress,
            registerData,
            registerValid));

    // Reboot the iC-PVL and clear the status register
    registerData[0] = PVL_CMD_REBOOT;
    CHECK(MU_WriteRegister_I2C(muHandle, PVL_REGISTER_CMD, 1, pvlI2cAddress, registerData));
    registerData[0] = PVL_CMD_SCLR;
    CHECK(MU_WriteRegister_I2C(muHandle, PVL_REGISTER_CMD, 1, pvlI2cAddress, registerData));


    printf("\n"
           "---------------------------------------------------------------\n"
           "-------------------- Calibration of iC-MU ---------------------\n"
           "---------------------------------------------------------------\n");

    MU_Calibration* calibration = MU_getCalibration(muHandle);

    uint32_t masterPeriodCode;
    CHECK(MU_GetParam(muHandle, MU_MPC, NULL, &masterPeriodCode));


    printf("\n"
           "---------------------------------------------------------------\n"
           "----------------- Analog Calibration of iC-MU -----------------\n"
           "---------------------------------------------------------------\n");

    MU_CalibrationAnalyzeResult* analyzeResult = acquireAndAnalyzeRawData(
            muHandle,
            calibration,
            0,
            numberOfSamples,
            acquireFrameCycleTime_s,
            acquireClockFrequency_hz,
            false);
    if (analyzeResult == NULL) {
        fprintf(stderr, "Raw data are not analyzable\n");
        MU_Calibration_delete(calibration);
        MU_Close(muHandle);
        return EXIT_FAILURE;
    }

    printAnalyzeResultLog(analyzeResult);

    printf("Relative track adjustments (relative changes in \"LSB\")\n");
    printRelativeAdjustments(analyzeResult);

    printAnalogAnalyzeResultAdjustableLog(calibration, analyzeResult);

    MU_Calibration_adjustAnalogByAnalyzeResult(calibration, analyzeResult);

    printf("iC-MU signal conditioning parameters after calibration:\n");
    printAnalogAdjustments(calibration);

    MU_setCalibration(muHandle, calibration);
    CHECK(MU_WriteParams(muHandle, false, NULL));

    MU_CalibrationAnalyzeResult_delete(analyzeResult);


    printf("\n"
           "---------------------------------------------------------------\n"
           "----------------- Nonius Calibration of iC-MU -----------------\n"
           "---------------------------------------------------------------\n");

    analyzeResult = acquireAndAnalyzeRawData(
            muHandle,
            calibration,
            0,
            numberOfSamples,
            acquireFrameCycleTime_s,
            acquireClockFrequency_hz,
            true);
    if (analyzeResult == NULL) {
        fprintf(stderr, "Raw data are not analyzable\n");
        MU_Calibration_delete(calibration);
        MU_Close(muHandle);
        return EXIT_FAILURE;
    }

    printAnalyzeResultLog(analyzeResult);

    printf("Residual errors (relative changes in \"LSB\")\n");
    printRelativeAdjustments(analyzeResult);

    optionalPrintOptimizedNoniusTrackOffsetTable(analyzeResult, noniusCurveCsvFilePath);

    MU_setCalibration(muHandle, calibration);
    CHECK(MU_WriteParams(muHandle, false, NULL));

    CHECK(MU_WriteCmdRegister(muHandle, MU_CMD_CRC_CALC));
    CHECK(MU_WriteCmdRegister(muHandle, MU_CMD_ABS_RESET));

    MU_CalibrationAnalyzeResult_delete(analyzeResult);
    MU_Calibration_delete(calibration);


    printf("\n"
           "---------------------------------------------------------------\n"
           "----------------- Multi Turn Synchronization ------------------\n"
           "---------------------------------------------------------------\n");

    MU_MtSyncData* synchronizationData =
            (MU_MtSyncData*)malloc(numberOfSynchronizationDataSamples * sizeof(MU_MtSyncData));
    CHECK(MU_activateMtSyncConfig(muHandle));
    CHECK(MU_acquireMtSyncData(muHandle, synchronizationData, numberOfSynchronizationDataSamples));
    CHECK(MU_deactivateMtSyncConfig(muHandle));

    MU_MtSync* mtSynchronization        = MU_getMtSync(muHandle);
    MU_MtAnalyzeResult* mtAnalyzeResult = MU_MtSync_analyzeData(
            mtSynchronization, synchronizationData, numberOfSynchronizationDataSamples);

    uint8_t optimalSpoMt = MU_MtAnalyzeResult_optimalSpoMt(mtAnalyzeResult);
    printf("optimal SPO_MT = %i\n", (int)optimalSpoMt);

    const uint64_t systemResolution = 1ull << (masterPeriodCode + 14);
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

    MU_MtAnalyzeResult_delete(mtAnalyzeResult);
    MU_MtSync_delete(mtSynchronization);


    printf("\n"
           "---------------------------------------------------------------\n"
           "--------------- Send WRITE_ALL Command to iC-MU ---------------\n"
           "---------------------------------------------------------------\n");

    CHECK(MU_WriteCmdRegister(muHandle, MU_CMD_WRITE_ALL));

    MU_Close(muHandle);

    return EXIT_SUCCESS;
}
