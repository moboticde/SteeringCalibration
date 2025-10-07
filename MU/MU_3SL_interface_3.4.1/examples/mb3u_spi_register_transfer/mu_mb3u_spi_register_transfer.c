/*
 * Software and its documentation is provided by iC-Haus GmbH or contributors "AS IS" and is
 * subject to the ZVEI General Conditions for the Supply of Products and Services with iC-Haus
 * amendments and the ZVEI Software clause with iC-Haus amendments (http://www.ichaus.de/EULA).
 */

#include "MU_3SL_defs.h"
#include "MU_3SL_interface.h"

#include "mu_3sl_check_error_return.h"

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


void printMuRegisters(MU_Handle muHandle, uint8_t startRegAdr, uint8_t endRegAdr, bool header);

void printMuCalibrationRegisters(MU_Handle muHandle);


int main(void)
{
    // Get the version of the library
    printf("Library version: %s%s\n\n", MU_GetVersionString(), MU_GetVersionSuffixString());

    // Open iC-MU instance and get handle
    MU_Handle muHandle;
    CHECK(MU_Open(&muHandle));

    CHECK(MU_SetInterface(muHandle, MU_MB3U_SPI, ""));

    uint8_t revisionId = MU_REV_MU128_X1;
    CHECK(MU_ReadChipRevision(muHandle, &revisionId));
    CHECK(MU_UseRevision(muHandle, revisionId));

    CHECK(MU_ReadParams(muHandle));

    printf("\n"
           ",---------------,\n"
           "| iC-MU regist. |\n");
    printMuRegisters(muHandle, 0x00, 0x7F, true);
    printf("'---------------'\n\n");

    uint32_t masterPeriodCountCode;
    MU_GetParam(muHandle, MU_MPC, NULL, &masterPeriodCountCode);

    // Clear current calibration configuration (loaded from EEPROM)
    MU_SetParam(muHandle, MU_GC_M, 0, 0, MU_SETONLY);
    MU_SetParam(muHandle, MU_GF_M, 0, 0, MU_SETONLY);
    MU_SetParam(muHandle, MU_GX_M, 0, 0, MU_SETONLY);
    MU_SetParam(muHandle, MU_VOSS_M, 0, 0, MU_SETONLY);
    MU_SetParam(muHandle, MU_VOSC_M, 0, 0, MU_SETONLY);
    MU_SetParam(muHandle, MU_PH_M, 0, 0, MU_SETONLY);

    MU_SetParam(muHandle, MU_GC_N, 0, 0, MU_SETONLY);
    MU_SetParam(muHandle, MU_GF_N, 0, 0, MU_SETONLY);
    MU_SetParam(muHandle, MU_GX_N, 0, 0, MU_SETONLY);
    MU_SetParam(muHandle, MU_VOSS_N, 0, 0, MU_SETONLY);
    MU_SetParam(muHandle, MU_VOSC_N, 0, 0, MU_SETONLY);
    MU_SetParam(muHandle, MU_PH_N, 0, 0, MU_SETONLY);

    MU_SetParam(muHandle, MU_SPO_BASE, 0, 0, MU_SETONLY);
    for (int i = 0; i < 15; ++i) {
        MU_SetParam(muHandle, (MU_Param)(MU_SPO_0 + i), 0, 0, MU_SETONLY);
    }

    CHECK(MU_WriteParams(muHandle, false, NULL));

    printMuCalibrationRegisters(muHandle);

    MU_Close(muHandle);

    return EXIT_SUCCESS;
}


void printMuRegisters(MU_Handle muHandle, uint8_t startRegAdr, uint8_t endRegAdr, bool header)
{
    if (header) {
        printf("| Addr. | Value |\n"
               "|-------|-------|\n");
    }
    for (uint8_t i = startRegAdr; i <= endRegAdr; i++) {
        uint32_t readBufferLength = 1;
        uint32_t readBuffer;
        if (MU_ReadRegister(muHandle, i, &readBufferLength, &readBuffer) != MU_OK) {
            printf("| 0x%02X  |  ???? |\n", i);
            continue;
        }
        printf("| 0x%02X  |  0x%02X |\n", i, readBuffer);
    }
}

void printMuCalibrationRegisters(MU_Handle muHandle)
{
    printf("\n"
           ",---------------,\n"
           "| iC-MU regist. |\n");
    printMuRegisters(muHandle, 0x01, 0x04, true);
    printf("|-------|-------|\n");
    printMuRegisters(muHandle, 0x07, 0x0A, false);
    printf("|-------|-------|\n");
    printMuRegisters(muHandle, 0x52, 0x59, false);
    printf("'---------------'\n\n");
}
