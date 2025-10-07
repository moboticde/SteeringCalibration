/*
 * Software and its documentation is provided by iC-Haus GmbH or contributors "AS IS" and is
 * subject to the ZVEI General Conditions for the Supply of Products and Services with iC-Haus
 * amendments and the ZVEI Software clause with iC-Haus amendments (http://www.ichaus.de/EULA).
 */

#ifndef MU_3SL_ANALOG_NONIUS_CALIBRATION_H
#define MU_3SL_ANALOG_NONIUS_CALIBRATION_H

#include "MU_3SL_defs.h"
#include "MU_3SL_interface.h"


MU_CalibrationAnalyzeResult* acquireAndAnalyzeRawData(
        MU_Handle muHandle,
        MU_Calibration* calibration,
        uint32_t slaveId,
        unsigned long numberOfSamples,
        double acquireFrameCycleTime_s,
        double acquireClockFrequency_hz,
        bool setOptimizedNoniusTrackOffsetTable);


#endif // MU_3SL_ANALOG_NONIUS_CALIBRATION_H
