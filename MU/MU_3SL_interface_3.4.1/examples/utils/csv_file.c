/*
 * Software and its documentation is provided by iC-Haus GmbH or contributors "AS IS" and is
 * subject to the ZVEI General Conditions for the Supply of Products and Services with iC-Haus
 * amendments and the ZVEI Software clause with iC-Haus amendments (http://www.ichaus.de/EULA).
 */

#include "csv_file.h"
#include "MU_3SL_interface.h"

#include <ctype.h>
#include <inttypes.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>


#define CALIBRATION_FILE_COMMENT_CHAR                  '#'
#define CALIBRATION_FILE_CONFIGURATION_DATA_TAG        "Pre-Califiguration:"
#define CALIBRATION_FILE_KEY_VALUE_SEPERATOR_CHAR      ':'
#define CALIBRATION_FILE_KEY_VALUE_PAIR_SEPERATOR_CHAR ','


ssize_t getLine(char** lineptr, size_t* n, FILE* stream)
{
    const size_t lineBufferInitSize = 512;

    if (lineptr == NULL || n == NULL) {
        return -1;
    }
    if (stream == NULL || ferror(stream) || feof(stream)) {
        return -1;
    }

    if (*lineptr == NULL) {
        *lineptr = (char*)malloc(lineBufferInitSize);
        if (*lineptr == NULL) {
            return -1;
        }
        *n = lineBufferInitSize;
    }

    char* p = *lineptr;
    int c;
    while ((c = fgetc(stream)) != EOF) {
        if (c == '\r') {
            continue;
        }
        if (c == '\n') {
            break;
        }

        if ((p - *lineptr) > ((ssize_t)(*n) - 1)) {
            size_t nsize = *n * 2;
            if ((*lineptr = (char*)realloc(*lineptr, nsize)) == NULL) {
                return -1;
            }
            *n = nsize;
        }

        *p++ = (char)c;
    }

    *p++ = 0;
    return p - *lineptr - 1;
}


bool setCalibrationKeyValueConfigurationPair(
        const char* key,
        const char* keyEnd,
        const char* value,
        const char* valueEnd,
        uint8_t* hardRev,
        uint8_t* mpc,
        MU_Calibration_AnalogTrackAdjustments* masterAdjustments,
        MU_Calibration_AnalogTrackAdjustments* noniusAdjustments)
{
    char* vParseEnd = (char*)valueEnd;
    uint8_t v       = (uint8_t)strtoul(value, &vParseEnd, 0);

    if (strncmp(key, "HARD_REV", keyEnd - key) == 0) {
        if (hardRev != NULL) {
            *hardRev = v;
        }
    } else if (strncmp(key, "MPC", keyEnd - key) == 0) {
        if (mpc != NULL) {
            *mpc = v;
        }
    } else if (strncmp(key, "GX_M", keyEnd - key) == 0) {
        if (masterAdjustments != NULL) {
            masterAdjustments->cosineGain = v;
        }
    } else if (strncmp(key, "VOSS_M", keyEnd - key) == 0) {
        if (masterAdjustments != NULL) {
            masterAdjustments->sineOffset = v;
        }
    } else if (strncmp(key, "VOSC_M", keyEnd - key) == 0) {
        if (masterAdjustments != NULL) {
            masterAdjustments->cosineOffset = v;
        }
    } else if (strncmp(key, "PH_M", keyEnd - key) == 0) {
        if (masterAdjustments != NULL) {
            masterAdjustments->phase = v;
        }
    } else if (strncmp(key, "PHR_M", keyEnd - key) == 0) {
        if (masterAdjustments != NULL) {
            masterAdjustments->phaseRange = v;
        }
    } else if (strncmp(key, "GX_N", keyEnd - key) == 0) {
        if (noniusAdjustments != NULL) {
            noniusAdjustments->cosineGain = v;
        }
    } else if (strncmp(key, "VOSS_N", keyEnd - key) == 0) {
        if (noniusAdjustments != NULL) {
            noniusAdjustments->sineOffset = v;
        }
    } else if (strncmp(key, "VOSC_N", keyEnd - key) == 0) {
        if (noniusAdjustments != NULL) {
            noniusAdjustments->cosineOffset = v;
        }
    } else if (strncmp(key, "PH_N", keyEnd - key) == 0) {
        if (noniusAdjustments != NULL) {
            noniusAdjustments->phase = v;
        }
    } else if (strncmp(key, "PHR_N", keyEnd - key) == 0) {
        if (noniusAdjustments != NULL) {
            noniusAdjustments->phaseRange = v;
        }
    } else {
        return false;
    }

    return true;
}


bool parseCalibrationFileConfigurationData(
        const char* line,
        size_t lineLength,
        uint8_t* hardRev,
        uint8_t* mpc,
        MU_Calibration_AnalogTrackAdjustments* masterAdjustments,
        MU_Calibration_AnalogTrackAdjustments* noniusAdjustments)
{
    static const char* calibrationFileConfigurationDataTag =
            CALIBRATION_FILE_CONFIGURATION_DATA_TAG;

    const size_t calibrationFileConfigurationDataTagLen =
            strlen(calibrationFileConfigurationDataTag);

    if (line == NULL) {
        return false;
    }
    if (lineLength < (1 + calibrationFileConfigurationDataTagLen)) {
        return false;
    }
    if (line[0] != CALIBRATION_FILE_COMMENT_CHAR) {
        return false;
    }

    const char* calibrationFileConfigurationDataTagPos =
            strstr(line, calibrationFileConfigurationDataTag);
    if (calibrationFileConfigurationDataTagPos == NULL) {
        return false;
    }

    const char* const lineEnd = line + lineLength;

    const char* c = calibrationFileConfigurationDataTagPos + calibrationFileConfigurationDataTagLen;

    const char* kBegin = NULL;
    const char* kEnd   = NULL;
    bool kvSeparated   = false;
    const char* vBegin = NULL;
    const char* vEnd   = NULL;
    bool kvpSeparated  = true;

    while (c < lineEnd) {
        if ((isalnum(*c) != 0) || *c == '_') {
            if (kBegin == NULL) {
                kBegin = c;
            } else if (kvSeparated && vBegin == NULL) {
                vBegin = c;
            } else if (!kvSeparated && kEnd != NULL) {
                break;
            }
            if ((c + 1) < lineEnd) {
                ++c;
                continue;
            } else {
                vEnd = c;
            }
        } else {
            if (kBegin != NULL && kEnd == NULL) {
                kEnd = c;
            } else if (vBegin != NULL && vEnd == NULL) {
                vEnd = c;
            }
        }

        if (*c == CALIBRATION_FILE_KEY_VALUE_SEPERATOR_CHAR) {
            if (kBegin == NULL || kEnd == NULL) {
                break;
            }
            kvSeparated = true;
            ++c;
            continue;
        }

        if (kBegin != NULL && kEnd != NULL && kvSeparated && vBegin != NULL && vEnd != NULL) {
            if (!kvpSeparated) {
                break;
            }
            setCalibrationKeyValueConfigurationPair(
                    kBegin, kEnd, vBegin, vEnd, hardRev, mpc, masterAdjustments, noniusAdjustments);
            kBegin       = NULL;
            kEnd         = NULL;
            kvSeparated  = false;
            vBegin       = NULL;
            vEnd         = NULL;
            kvpSeparated = false;
        }

        if (*c == CALIBRATION_FILE_KEY_VALUE_PAIR_SEPERATOR_CHAR) {
            kvpSeparated = true;
            ++c;
            continue;
        }

        if (*c != ' ' && (c + 1) < lineEnd) {
            break;
        }

        ++c;
    }

    return true;
}


int readCalibrationDataCSVFile(
        uint16_t** masterDataArray,
        uint16_t** noniusDataArray,
        size_t* numberOfSamples,
        const char* filepath,
        unsigned long skipLines,
        uint8_t* hardRev,
        uint8_t* mpc,
        MU_Calibration_AnalogTrackAdjustments* masterAdjustments,
        MU_Calibration_AnalogTrackAdjustments* noniusAdjustments)
{
    FILE* rawdataFile = fopen(filepath, "r");
    if (rawdataFile == NULL) {
        fprintf(stderr, "Error: Unable to open data file: \"%s\"\n", filepath);
        return -1;
    }

    *numberOfSamples            = 0;
    ssize_t firstNonCommentLine = -1;
    size_t lineCap              = 1024;
    char* line                  = (char*)malloc(lineCap + sizeof(char));
    ssize_t lineLen;
    size_t numberOfValidLines = 0;
    size_t lineNumber         = 0;
    while ((lineLen = getLine(&line, &lineCap, rawdataFile)) >= 0) {
        ++lineNumber;
        if (parseCalibrationFileConfigurationData(
                    line, lineLen, hardRev, mpc, masterAdjustments, noniusAdjustments)) {
            continue;
        }
        if (line[0] == '#') {
            continue;
        }
        if (firstNonCommentLine < 0) {
            firstNonCommentLine = (ssize_t)lineNumber;
        }
        if (lineNumber <= (firstNonCommentLine - 1 + skipLines)) {
            continue;
        }
        int masterData;
        int noniusData;
        if (sscanf(line, "%d,%d", &masterData, &noniusData) > 0) {
            ++numberOfValidLines;
        }
        if (feof(rawdataFile) || ferror(rawdataFile)) {
            break;
        }
    }

    rewind(rawdataFile);
    fseek(rawdataFile, 0, SEEK_SET);
    fseek(rawdataFile, 0, SEEK_CUR);
    lineNumber = 0;

    *masterDataArray = (uint16_t*)malloc(numberOfValidLines * sizeof(uint16_t));
    *noniusDataArray = (uint16_t*)malloc(numberOfValidLines * sizeof(uint16_t));

    while ((lineLen = getLine(&line, &lineCap, rawdataFile)) >= 0) {
        ++lineNumber;
        if (line[0] == '#') {
            continue;
        }
        if (lineNumber <= (firstNonCommentLine - 1 + skipLines)) {
            continue;
        }
        int masterData;
        int noniusData;
        if (sscanf(line, "%d,%d", &masterData, &noniusData) > 0) {
            (*masterDataArray)[*numberOfSamples] = masterData;
            (*noniusDataArray)[*numberOfSamples] = noniusData;
            ++(*numberOfSamples);
        } else if (strlen(line) > 0) {
            fprintf(stderr, "Error read file in line %" PRIuPTR "\n", lineNumber);
        }
        if (feof(rawdataFile) || ferror(rawdataFile)) {
            break;
        }
    }
    free(line);

    fclose(rawdataFile);
    return (int)(*numberOfSamples);
}


int readMtSyncCSVFile(
        MU_MtSyncData** syncData,
        size_t* numberOfSamples,
        const char* filepath,
        const unsigned long skipLines)
{
    FILE* rawdataFile = fopen(filepath, "r");
    if (rawdataFile == NULL) {
        fprintf(stderr, "Error: Unable to open data file: \"%s\"\n", filepath);
        return -1;
    }

    *numberOfSamples = 0;
    size_t lineCap   = 1024;
    char* line       = (char*)malloc(lineCap + sizeof(char));
    ssize_t lineLen;
    size_t numberOfValidLines = 0;
    size_t lineNumber         = 0;
    while ((lineLen = getLine(&line, &lineCap, rawdataFile)) >= 0) {
        ++lineNumber;
        if (lineNumber <= skipLines) {
            continue;
        }
        uint32_t singleTurnPosition;
        uint32_t internalSingleTurnPosition;
        uint32_t normalizedExternalMultiTurnSyncBits;
        uint32_t normalizedInternalMultiTurnSyncBits;
        uint32_t externalMultiTurnPosition;
        uint32_t multiTurnPosition;
        if (sscanf(line,
                   "%" SCNu32 ",%" SCNu32 ",%" SCNu32 ",%" SCNu32 ",%" SCNu32 ",%" SCNu32,
                   &singleTurnPosition,
                   &internalSingleTurnPosition,
                   &normalizedExternalMultiTurnSyncBits,
                   &normalizedInternalMultiTurnSyncBits,
                   &externalMultiTurnPosition,
                   &multiTurnPosition)
            > 0) {
            ++numberOfValidLines;
        }
        if (feof(rawdataFile) || ferror(rawdataFile)) {
            break;
        }
    }

    rewind(rawdataFile);
    fseek(rawdataFile, 0, SEEK_SET);
    fseek(rawdataFile, 0, SEEK_CUR);
    lineNumber = 0;

    *syncData = (MU_MtSyncData*)malloc(numberOfValidLines * sizeof(MU_MtSyncData));

    while ((lineLen = getLine(&line, &lineCap, rawdataFile)) >= 0) {
        ++lineNumber;
        if (lineNumber <= skipLines) {
            continue;
        }
        uint32_t singleTurnPosition;
        uint32_t internalSingleTurnPosition;
        uint32_t normalizedExternalMultiTurnSyncBits;
        uint32_t normalizedInternalMultiTurnSyncBits;
        uint32_t externalMultiTurnPosition;
        uint32_t multiTurnPosition;
        if (sscanf(line,
                   "%" SCNu32 ",%" SCNu32 ",%" SCNu32 ",%" SCNu32 ",%" SCNu32 ",%" SCNu32,
                   &singleTurnPosition,
                   &internalSingleTurnPosition,
                   &normalizedExternalMultiTurnSyncBits,
                   &normalizedInternalMultiTurnSyncBits,
                   &externalMultiTurnPosition,
                   &multiTurnPosition)
            > 0) {
            (*syncData)[*numberOfSamples].singleTurnPosition         = singleTurnPosition;
            (*syncData)[*numberOfSamples].internalSingleTurnPosition = internalSingleTurnPosition;
            (*syncData)[*numberOfSamples].normalizedExternalMultiTurnSyncBits =
                    normalizedExternalMultiTurnSyncBits;
            (*syncData)[*numberOfSamples].normalizedInternalMultiTurnSyncBits =
                    normalizedInternalMultiTurnSyncBits;
            (*syncData)[*numberOfSamples].externalMultiTurnPosition = externalMultiTurnPosition;
            (*syncData)[*numberOfSamples].multiTurnPosition         = multiTurnPosition;
            ++(*numberOfSamples);
        } else if (strlen(line) > 0) {
            fprintf(stderr, "Error read file in line %" PRIuPTR "\n", lineNumber);
        }
        if (feof(rawdataFile) || ferror(rawdataFile)) {
            break;
        }
    }
    free(line);

    fclose(rawdataFile);
    return (int)(*numberOfSamples);
}


size_t writeCalibrationDataCSVFile(
        const uint16_t* masterData,
        const uint16_t* noniusData,
        size_t numberOfSamples,
        const char* filepath,
        const uint8_t* hardRev,
        const uint8_t* mpc,
        const MU_Calibration_AnalogTrackAdjustments* masterAdjustments,
        const MU_Calibration_AnalogTrackAdjustments* noniusAdjustments)
{
    FILE* rawdataFile = fopen(filepath, "w");
    if (rawdataFile == NULL) {
        fprintf(stderr, "Error: Unable to open data file: \"%s\"\n", filepath);
        return -1;
    }

    size_t nCharactersWritten = 0;

    if (hardRev != NULL || mpc != NULL || masterAdjustments != NULL || noniusAdjustments != NULL) {
        nCharactersWritten +=
                fprintf(rawdataFile,
                        "%c " CALIBRATION_FILE_CONFIGURATION_DATA_TAG " ",
                        CALIBRATION_FILE_COMMENT_CHAR);

        bool isFirst = true;

        if (hardRev != NULL) {
            nCharactersWritten +=
                    fprintf(rawdataFile,
                            "HARD_REV%c0x%02" PRIX8,
                            CALIBRATION_FILE_KEY_VALUE_SEPERATOR_CHAR,
                            *hardRev);
            isFirst = false;
        }

        if (mpc != NULL) {
            if (!isFirst) {
                nCharactersWritten +=
                        fprintf(rawdataFile, "%c", CALIBRATION_FILE_KEY_VALUE_PAIR_SEPERATOR_CHAR);
            }
            nCharactersWritten +=
                    fprintf(rawdataFile,
                            "MPC%c0x%02" PRIX8,
                            CALIBRATION_FILE_KEY_VALUE_SEPERATOR_CHAR,
                            *mpc);
            isFirst = false;
        }

        if (masterAdjustments != NULL) {
            if (!isFirst) {
                nCharactersWritten +=
                        fprintf(rawdataFile, "%c", CALIBRATION_FILE_KEY_VALUE_PAIR_SEPERATOR_CHAR);
            }
            nCharactersWritten +=
                    fprintf(rawdataFile,
                            "GX_M%c0x%02" PRIX8,
                            CALIBRATION_FILE_KEY_VALUE_SEPERATOR_CHAR,
                            masterAdjustments->cosineGain);
            nCharactersWritten +=
                    fprintf(rawdataFile,
                            ",VOSS_M%c0x%02" PRIX8,
                            CALIBRATION_FILE_KEY_VALUE_SEPERATOR_CHAR,
                            masterAdjustments->sineOffset);
            nCharactersWritten +=
                    fprintf(rawdataFile,
                            ",VOSC_M%c0x%02" PRIX8,
                            CALIBRATION_FILE_KEY_VALUE_SEPERATOR_CHAR,
                            masterAdjustments->cosineOffset);
            nCharactersWritten +=
                    fprintf(rawdataFile,
                            ",PH_M%c0x%02" PRIX8,
                            CALIBRATION_FILE_KEY_VALUE_SEPERATOR_CHAR,
                            masterAdjustments->phase);
            nCharactersWritten +=
                    fprintf(rawdataFile,
                            ",PHR_M%c0x%02" PRIX8,
                            CALIBRATION_FILE_KEY_VALUE_SEPERATOR_CHAR,
                            masterAdjustments->phaseRange);
            isFirst = false;
        }

        if (noniusAdjustments != NULL) {
            if (!isFirst) {
                nCharactersWritten +=
                        fprintf(rawdataFile, "%c", CALIBRATION_FILE_KEY_VALUE_PAIR_SEPERATOR_CHAR);
            }
            nCharactersWritten +=
                    fprintf(rawdataFile,
                            "GX_N%c0x%02" PRIX8,
                            CALIBRATION_FILE_KEY_VALUE_SEPERATOR_CHAR,
                            noniusAdjustments->cosineGain);
            nCharactersWritten +=
                    fprintf(rawdataFile,
                            ",VOSS_N%c0x%02" PRIX8,
                            CALIBRATION_FILE_KEY_VALUE_SEPERATOR_CHAR,
                            noniusAdjustments->sineOffset);
            nCharactersWritten +=
                    fprintf(rawdataFile,
                            ",VOSC_N%c0x%02" PRIX8,
                            CALIBRATION_FILE_KEY_VALUE_SEPERATOR_CHAR,
                            noniusAdjustments->cosineOffset);
            nCharactersWritten +=
                    fprintf(rawdataFile,
                            ",PH_N%c0x%02" PRIX8,
                            CALIBRATION_FILE_KEY_VALUE_SEPERATOR_CHAR,
                            noniusAdjustments->phase);
            nCharactersWritten +=
                    fprintf(rawdataFile,
                            ",PHR_N%c0x%02" PRIX8,
                            CALIBRATION_FILE_KEY_VALUE_SEPERATOR_CHAR,
                            noniusAdjustments->phaseRange);
            isFirst = false;
        }


        nCharactersWritten += fprintf(rawdataFile, "\n");
    }

    nCharactersWritten += fprintf(rawdataFile, "MASTER_RAW,NONIUS_RAW");
    for (size_t i = 0; i < numberOfSamples; ++i) {
        nCharactersWritten += fprintf(rawdataFile, "\n%i,%i", masterData[i], noniusData[i]);
    }

    fclose(rawdataFile);
    return nCharactersWritten;
}
