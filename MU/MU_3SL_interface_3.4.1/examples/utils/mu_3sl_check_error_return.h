/*
 * Software and its documentation is provided by iC-Haus GmbH or contributors "AS IS" and is
 * subject to the ZVEI General Conditions for the Supply of Products and Services with iC-Haus
 * amendments and the ZVEI Software clause with iC-Haus amendments (http://www.ichaus.de/EULA).
 */

#ifndef MU_3SL_CHECK_ERROR_RETURN_H
#define MU_3SL_CHECK_ERROR_RETURN_H

#include "MU_3SL_defs.h"
#include "MU_3SL_interface.h"


const char* errorEnumName(MU_Error errorCode);


#define CHECK(x)                                                                                   \
    {                                                                                              \
        MU_Error e = (x);                                                                          \
        if (e != MU_OK) {                                                                          \
            MU_Error code;                                                                         \
            MU_ErrorType type;                                                                     \
            char message[1024];                                                                    \
            MU_GetLastError(muHandle, &code, &type, message);                                      \
            fprintf(stderr,                                                                        \
                    "Error: \"%s\" returned error code %s (%d) in line %d\n%s",                    \
                    #x,                                                                            \
                    errorEnumName(e),                                                              \
                    e,                                                                             \
                    __LINE__,                                                                      \
                    message);                                                                      \
            MU_Close(muHandle);                                                                    \
            exit(EXIT_FAILURE);                                                                    \
        }                                                                                          \
    }


#endif // MU_3SL_CHECK_ERROR_RETURN_H
