/*
 * Software and its documentation is provided by iC-Haus GmbH or contributors "AS IS" and is
 * subject to the ZVEI General Conditions for the Supply of Products and Services with iC-Haus
 * amendments and the ZVEI Software clause with iC-Haus amendments (http://www.ichaus.de/EULA).
 */

#include "MU_3SL_defs.h"
#include "MU_3SL_interface.h"

#include "csv_file.h"
#include "mu_3sl_calibration_adjustments.h"
#include "mu_3sl_nonius_curve.h"

#include <inttypes.h>
#include <math.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>


int main(int argc, char** argv)
{
    const char* filePrefixPath = argc <= 1 ? "measure/MU28S_34-32N/calibration_data" : argv[1];
    const char* noniusCurveCsvFilePath = argc <= 2 ? "nonius_curve.csv" : argv[2];

    const bool enableMasterPeriodAutoDetection                    = false;
    const double permissibleResidualErrorsDuringAnalogCalibration = 1.0;

    printf("Library version: %s%s\n\n", MU_GetVersionString(), MU_GetVersionSuffixString());

    uint8_t revisionCode               = MU_REV_MU128_X1;
    uint8_t masterPeriodCode           = 5;
    unsigned int numberOfMasterPeriods = 1u << masterPeriodCode;

    MU_Calibration* calibration = NULL;

    MU_Calibration_AnalogTrackAdjustments initialMasterAdjustments = {0, 0, 0, 0, 0};
    MU_Calibration_AnalogTrackAdjustments initialNoniusAdjustments = {0, 0, 0, 0, 0};

    MU_CalibrationAnalyzeResult* analyzeResult = NULL;

    char filepath[512];
    size_t numberOfSamples    = 0;
    uint16_t* masterRawData   = NULL;
    uint16_t* noniusRawData   = NULL;
    size_t calibrationDataIdx = 0;
    while (true) {
        snprintf(
                filepath,
                sizeof(filepath) / sizeof(char),
                "%s_%" PRIuPTR ".csv",
                filePrefixPath,
                calibrationDataIdx);

        FILE* file = fopen(filepath, "r");
        if (file == NULL) {
            if (calibrationDataIdx == 0) {
                fprintf(stderr, "Error: Calibration data file not found!\n");
                exit(EXIT_FAILURE);
            }
            break;
        }
        fclose(file);

        printf("---------------------------------------------------------------\n"
               "---------------- Acquire raw data (from file) -----------------\n"
               "---------------------------------------------------------------\n");

        printf("Read master and nonius track raw data from file:\n"
               "\"%s\"\n\n",
               filepath);

        uint8_t fileRevisionCode     = 0;
        uint8_t fileMasterPeriodCode = 0;
        free(masterRawData);
        free(noniusRawData);
        if (readCalibrationDataCSVFile(
                    &masterRawData,
                    &noniusRawData,
                    &numberOfSamples,
                    filepath,
                    1,
                    &fileRevisionCode,
                    &fileMasterPeriodCode,
                    &initialMasterAdjustments,
                    &initialNoniusAdjustments)
            < 0) {
            fprintf(stderr, "Error: Unable to read data file!\n");
            exit(EXIT_FAILURE);
        }
        if (calibrationDataIdx > 0 && revisionCode != fileRevisionCode) {
            fprintf(stderr,
                    "Error: Calibration data file revision code missmatch with previous files!\n");
            exit(EXIT_FAILURE);
        }
        if (calibrationDataIdx > 0 && masterPeriodCode != fileMasterPeriodCode) {
            fprintf(stderr,
                    "Error: Calibration data file master period code missmatch with previous "
                    "files!\n");
            exit(EXIT_FAILURE);
        }

        if (calibrationDataIdx == 0) {
            revisionCode          = fileRevisionCode;
            masterPeriodCode      = fileMasterPeriodCode;
            numberOfMasterPeriods = 1u << masterPeriodCode;

            calibration = MU_createCalibration(revisionCode);
            if (!enableMasterPeriodAutoDetection) {
                MU_Calibration_preconfigureNumberOfMasterPeriods(
                        calibration, numberOfMasterPeriods);
            }
        }
        ++calibrationDataIdx;

        MU_Calibration_setCurrentAnalogTrackAdjustments(
                calibration, &initialMasterAdjustments, &initialNoniusAdjustments);

        printf("Previous iC-MU analog parameters:\n");
        printAnalogAdjustments(calibration);
        printf("\n\n");

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
            free(masterRawData);
            free(noniusRawData);
            MU_Calibration_delete(calibration);
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
    free(masterRawData);
    free(noniusRawData);

    int numberOfCalculatedMasterPeriods =
            MU_Calibration_numberOfCalculatedMasterPeriods(analyzeResult);
    uint32_t calculatedMasterPeriodCode = (uint32_t)round(log2(numberOfCalculatedMasterPeriods));
    optionalPrintOptimizedNoniusTrackOffsetTable(analyzeResult, noniusCurveCsvFilePath);
    printf("\n");
    optionalPrintOptimizedNoniusTrackOffsetParameters(analyzeResult);

    MU_CalibrationAnalyzeResult_delete(analyzeResult);
    MU_Calibration_delete(calibration);

    return EXIT_SUCCESS;
}
