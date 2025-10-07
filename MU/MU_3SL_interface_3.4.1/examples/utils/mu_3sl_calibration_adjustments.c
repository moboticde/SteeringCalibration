/*
 * Software and its documentation is provided by iC-Haus GmbH or contributors "AS IS" and is
 * subject to the ZVEI General Conditions for the Supply of Products and Services with iC-Haus
 * amendments and the ZVEI Software clause with iC-Haus amendments (http://www.ichaus.de/EULA).
 */

#include "mu_3sl_calibration_adjustments.h"

#include "MU_3SL_defs.h"
#include "MU_3SL_interface.h"

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>


void printAnalogTrackAdjustments(
        const MU_Calibration_AnalogTrackAdjustments* adjustments,
        const char* trackShortName)
{
    printf("Cosine gain (GX_%s):     %4d (0x%02X)\n"
           "Sine offset (VOSS_%s):   %4d (0x%02X)\n"
           "Cosine offset (VOSC_%s): %4d (0x%02X)\n"
           "Phase (PH_%s):           %4d (0x%02X)\n"
           "Phase range (PHR_%s):    %4d (0x%02X)\n",
           trackShortName,
           adjustments->cosineGain,
           adjustments->cosineGain,
           trackShortName,
           adjustments->sineOffset,
           adjustments->sineOffset,
           trackShortName,
           adjustments->cosineOffset,
           adjustments->cosineOffset,
           trackShortName,
           adjustments->phase,
           adjustments->phase,
           trackShortName,
           adjustments->phaseRange,
           adjustments->phaseRange);
}


void printAnalogAdjustments(const MU_Calibration* calibration)
{
    MU_Calibration_AnalogTrackAdjustments masterTrackAdjustments;
    MU_Calibration_getAnalogMasterTrackAdjustments(calibration, &masterTrackAdjustments);
    printAnalogTrackAdjustments(&masterTrackAdjustments, "M");
    MU_Calibration_AnalogTrackAdjustments noniusTrackAdjustments;
    MU_Calibration_getAnalogNoniusTrackAdjustments(calibration, &noniusTrackAdjustments);
    printAnalogTrackAdjustments(&noniusTrackAdjustments, "N");
}


void printRelativeAdjustments(const MU_CalibrationAnalyzeResult* analyzeResult)
{
    MU_Calibration_RelativeAnalogTrackAdjustments relativeMasterTrackAdjustments;
    MU_Calibration_getRelativeMasterTrackAdjustments(
            analyzeResult, &relativeMasterTrackAdjustments);

    MU_Calibration_RelativeAnalogTrackAdjustments relativeNoniusTrackAdjustments;
    MU_Calibration_getRelativeNoniusTrackAdjustments(
            analyzeResult, &relativeNoniusTrackAdjustments);

    printf("Track:             Master |   Nonius\n"
           "  Cosine gain:   %8.4f | %8.4f\n"
           "  Sine offset:   %8.4f | %8.4f\n"
           "  Cosine offset: %8.4f | %8.4f\n"
           "  Phase adjust:  %8.4f | %8.4f\n\n",
           relativeMasterTrackAdjustments.cosineGain_lsb,
           relativeNoniusTrackAdjustments.cosineGain_lsb,
           relativeMasterTrackAdjustments.sineOffset_lsb,
           relativeNoniusTrackAdjustments.sineOffset_lsb,
           relativeMasterTrackAdjustments.cosineOffset_lsb,
           relativeNoniusTrackAdjustments.cosineOffset_lsb,
           relativeMasterTrackAdjustments.phase_lsb,
           relativeNoniusTrackAdjustments.phase_lsb);
}


void printAnalyzeResultLog(const MU_CalibrationAnalyzeResult* analyzeResult)
{
    size_t analyzeResultLogSize =
            MU_Calibration_getAnalyzeResultLog(
                    analyzeResult, NULL, 0, MU_CALIBRATION_ANALYZE_RESULT_LOG_ALL)
            + 1;

    char* analyzeResultLogMessage = (char*)malloc(analyzeResultLogSize * sizeof(char));
    MU_Calibration_getAnalyzeResultLog(
            analyzeResult,
            analyzeResultLogMessage,
            analyzeResultLogSize,
            MU_CALIBRATION_ANALYZE_RESULT_LOG_ALL);

    printf("%s\n", analyzeResultLogMessage);

    free(analyzeResultLogMessage);
}


void printAnalogAnalyzeResultAdjustableLog(
        const MU_Calibration* calibration,
        const MU_CalibrationAnalyzeResult* analyzeResult)
{
    const size_t adjustmentMessageSize = 1024;

    char* adjustmentMessage = (char*)malloc(adjustmentMessageSize * sizeof(char));
    bool isAdjustable       = MU_Calibration_isAnalogAnalyzeResultAdjustable(
                  calibration,
                  analyzeResult,
                  adjustmentMessage,
                  adjustmentMessageSize,
                  MU_ADJUSTMENT_MESSAGE_LOG_ALL);
    if (isAdjustable) {
        printf("Analyze result is adjustable.\nMessage:\n%s\n", adjustmentMessage);
    } else {
        printf("Analyze result is not adjustable!\nMessage:\n%s\n", adjustmentMessage);
    }
    free(adjustmentMessage);
}
