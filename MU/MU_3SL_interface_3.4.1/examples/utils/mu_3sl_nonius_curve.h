/*
* Software and its documentation is provided by iC-Haus GmbH or contributors "AS IS" and is
* subject to the ZVEI General Conditions for the Supply of Products and Services with iC-Haus
* amendments and the ZVEI Software clause with iC-Haus amendments (http://www.ichaus.de/EULA).
*/

#ifndef MU_3SL_NONIUS_CURVE_H
#define MU_3SL_NONIUS_CURVE_H

#include "MU_3SL_defs.h"
#include "MU_3SL_interface.h"

#ifdef __cplusplus
    #include <cstdbool>
    #include <cstddef>
    #include <cstdint>
    #include <cmath>
    #include <cstdio>
    #include <cstring>
    #include <cstdlib>
#else
    #include <stdbool.h>
    #include <stddef.h>
    #include <stdint.h>
    #include <math.h>
    #include <stdio.h>
    #include <string.h>
    #include <stdlib.h>
#endif


#ifdef __cplusplus
extern "C" {
#endif


void optionalPrintOptimizedNoniusTrackOffsetTable(
        const MU_CalibrationAnalyzeResult* analyzeResult,
        const char* noniusCurveCsvFilePath);

void optionalPrintOptimizedNoniusTrackOffsetParameters(
        const MU_CalibrationAnalyzeResult* analyzeResult);


#ifdef __cplusplus
}
#endif

#endif // MU_3SL_NONIUS_CURVE_H
