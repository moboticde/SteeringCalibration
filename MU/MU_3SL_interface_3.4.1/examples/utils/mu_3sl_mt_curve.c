/*
* Software and its documentation is provided by iC-Haus GmbH or contributors "AS IS" and is
* subject to the ZVEI General Conditions for the Supply of Products and Services with iC-Haus
* amendments and the ZVEI Software clause with iC-Haus amendments (http://www.ichaus.de/EULA).
 */

#include "mu_3sl_mt_curve.h"

#include "MU_3SL_defs.h"
#include "MU_3SL_interface.h"

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <math.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>


void optionalMtOffsetErrorData(
        const MU_MtSyncData* syncData,
        size_t nSamples,
        const MU_MtSync* mtSynchronization,
        const MU_MtAnalyzeResult* mtAnalyzeResult,
        uint8_t spoMt,
        uint64_t resolution,
        const char* csvFilePath)
{
    const double maxOffsetError = MU_MtAnalyzeResult_maxOffsetError(mtAnalyzeResult, spoMt);
    const double minOffsetError = MU_MtAnalyzeResult_minOffsetError(mtAnalyzeResult, spoMt);

    const double offsetErrorRangeLimit = MU_MtAnalyzeResult_offsetErrorRangeLimit(mtAnalyzeResult);
    const double upperOffsetErrorMargin =
            MU_MtAnalyzeResult_upperOffsetErrorMargin(mtAnalyzeResult, spoMt);
    const double lowerOffsetErrorMargin =
            MU_MtAnalyzeResult_lowerOffsetErrorMargin(mtAnalyzeResult, spoMt);

    const double maxOffsetError_percent =
            maxOffsetError / offsetErrorRangeLimit * 100;
    const double minOffsetError_percent =
            minOffsetError / -offsetErrorRangeLimit * 100;
    printf("Multi turn synchronization error: Max.: %f° (%.3f%%) Min.: %f° (%.3f%%)\n",
           maxOffsetError,
           maxOffsetError_percent,
           minOffsetError,
           minOffsetError_percent);

    printf("Multi turn synchronization upper error margin: %f%%\n",
           upperOffsetErrorMargin);
    printf("Multi turn synchronization lower error margin: %f%%\n",
           lowerOffsetErrorMargin);


    double* mtPosition = (double*)malloc(nSamples * sizeof(double));
    double* mtError    = (double*)malloc(nSamples * sizeof(double));

    MU_MtSync_calculatePosition(
            mtSynchronization,
            mtPosition,
            syncData,
            nSamples,
            spoMt,
            resolution,
            MU_CALIBRATION_UNIT_DEGREE,
            false);

    MU_MtAnalyzeResult_calculateOffsetError(mtAnalyzeResult, mtError, nSamples, spoMt);


    FILE* csvFile = NULL;
    if (csvFilePath != NULL && strcmp(csvFilePath, "") != 0) {
        csvFile = fopen(csvFilePath, "w");
    }
    if (csvFile) {
        fprintf(csvFile,
                "position,"
                "error\n");
        for (size_t i = 0; i < nSamples; ++i) {
            fprintf(csvFile,
                    "%f,%f\n",
                    mtPosition[i],
                    mtError[i]);
        }
        fclose(csvFile);
    } else {
        fprintf(stderr,
                "Error: Can't create and/or open CSV file \"%s\"\n",
                csvFilePath);
    }

    free(mtError);
    free(mtPosition);
}
