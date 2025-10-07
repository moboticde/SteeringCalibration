/*
 * Software and its documentation is provided by iC-Haus GmbH or contributors "AS IS" and is
 * subject to the ZVEI General Conditions for the Supply of Products and Services with iC-Haus
 * amendments and the ZVEI Software clause with iC-Haus amendments (http://www.ichaus.de/EULA).
 */

#ifndef MU_3SL_CALIBRATION_ADJUSTMENTS_H
#define MU_3SL_CALIBRATION_ADJUSTMENTS_H

#include "MU_3SL_defs.h"
#include "MU_3SL_interface.h"


#ifdef __cplusplus
extern "C" {
#endif

void printAnalogTrackAdjustments(
        const MU_Calibration_AnalogTrackAdjustments* adjustments,
        const char* trackShortName);

void printAnalogAdjustments(const MU_Calibration* calibration);

void printRelativeAdjustments(const MU_CalibrationAnalyzeResult* analyzeResult);

void printAnalyzeResultLog(const MU_CalibrationAnalyzeResult* analyzeResult);

void printAnalogAnalyzeResultAdjustableLog(
        const MU_Calibration* calibration,
        const MU_CalibrationAnalyzeResult* analyzeResult);


#ifdef __cplusplus
}
#endif

#endif // MU_3SL_CALIBRATION_ADJUSTMENTS_H
