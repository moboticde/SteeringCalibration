/*
 * Software and its documentation is provided by iC-Haus GmbH or contributors "AS IS" and is
 * subject to the ZVEI General Conditions for the Supply of Products and Services with iC-Haus
 * amendments and the ZVEI Software clause with iC-Haus amendments (http://www.ichaus.de/EULA).
 */

#include "MU_3SL_defs.h"
#include "MU_3SL_interface.h"

#include "mu_3sl_check_error_return.h"

#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>


int main(void)
{
    // Get the version of the library
    printf("Library version: %s%s\n\n", MU_GetVersionString(), MU_GetVersionSuffixString());

    // Construct a new instance of a virtual chip object and obtain a handle for it.
    MU_Handle muHandle;
    CHECK(MU_Open(&muHandle));

    // Connect the interface (USB-BiSS adapter) MB5U
    CHECK(MU_SetInterface(muHandle, MU_MB5U, ""));

    uint8_t revisionId = MU_REV_MU128_X1;
    CHECK(MU_ReadChipRevision(muHandle, &revisionId));
    CHECK(MU_UseRevision(muHandle, revisionId));

    // Read all configuration parameters from the connected iC-MU* in the virtual chip object
    CHECK(MU_ReadParams(muHandle));

    // Set some parameters to the virtual chip object and write the corresponding register to the
    // iC-MU* immediately
    CHECK(MU_SetParam(muHandle, MU_GC_M, 0, 0, MU_VERIFY));
    CHECK(MU_SetParam(muHandle, MU_GC_N, 0, 1, MU_VERIFY));

    // Get the parameter MPC from the virtual chip object
    uint32_t masterPeriodCountCode;
    CHECK(MU_GetParam(muHandle, MU_MPC, NULL, &masterPeriodCountCode));

    // Get the first 12 iC-MU* parameters in the MU_ParamEnum from the virtual chip object
    for (int i = 0; i <= 11; i++) {
        uint32_t paramValueH, paramValueL;
        MU_Param iParam = (MU_Param)(MU_GF_M + i);
        MU_Error error  = MU_GetParam(muHandle, iParam, &paramValueH, &paramValueL);
        if (error == MU_OK) {
            uint64_t paramValue = (uint64_t)(paramValueH) << 32u;
            paramValue |= paramValueL;
            printf("Param(%i): 0x%02llX\n", i, paramValue);
        }
    }

    MU_Close(muHandle);

    return EXIT_SUCCESS;
}
