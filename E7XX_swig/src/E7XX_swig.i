%module(docstring = "This is the python wrapper for E7XX Piezo Stage library.") E7XX_swig

%{
#define SWIG_FILE_WITH_INIT
#include <Windows.h>
#include "E7XX_GCS_DLL.h"
%}

%include "typemaps.i"
%include "cstring.i"
%include "carrays.i"
%array_functions(double, doubleArray);
%array_functions(int, intArray);

typedef int BOOL;

%feature("autodoc", "1");

/////////////////////////////////////////////////////////////////////////////
// DLL initialization and comm functions
int 	E7XX_InterfaceSetupDlg(const char* szRegKeyName);
int  E7XX_ConnectRS232(int iPortNumber, int iBaudRate);
int 	E7XX_ConnectNIgpib(int iBoardNumber, int iDeviceAddress);
int 	E7XX_ConnectPciBoard(int iBoardNumber);
int 	E7XX_ConnectPciBoardAndReboot(int iBoardNumber);
BOOL E7XX_ChangeNIgpibAddress(int ID, int iDeviceAddress);
BOOL E7XX_IsConnected(int ID);
void E7XX_CloseConnection(int ID);
int 	E7XX_GetError(int ID);
BOOL E7XX_SetErrorCheck(int ID, BOOL bErrorCheck);

%cstring_output_maxsize(char* szErrorMessage, int iBufferSize);
BOOL E7XX_TranslateError(int iErrorNumber, char* szErrorMessage, int iBufferSize);

int 	E7XX_CountPciBoards(void);


/////////////////////////////////////////////////////////////////////////////
// general
%apply int *OUTPUT { int *piError };
BOOL  E7XX_qERR(int ID, int* piError);
%cstring_output_maxsize(char* szBuffer, int iBufferSize);
BOOL  E7XX_qIDN(int ID, char* szBuffer, int iBufferSize);
BOOL  E7XX_INI(int ID, const char* szAxes);
BOOL  E7XX_qHLP(int ID, char* szBuffer, int iBufferSize);
BOOL  E7XX_qHPA(int ID, char* szBuffer, int iBufferSize);
BOOL  E7XX_CSV(int ID, double pdCommandSyntaxVersion);
BOOL  E7XX_qCSV(int ID, double* pdCommandSyntaxVersion);
BOOL  E7XX_qOVF(int ID, const char* szAxes, BOOL* pbValueArray);
BOOL  E7XX_RBT(int ID);
BOOL  E7XX_REP(int ID);
%cstring_output_maxsize(char* szSerialNumber, int iBufferSize);
BOOL  E7XX_qSSN(int ID,char* szSerialNumber, int iBufferSize);
%cstring_output_maxsize(char* szVersion, int iBufferSize);
BOOL  E7XX_qVER(int ID, char* szVersion, int iBufferSize);
BOOL  E7XX_CCT(int ID, int iCommandType);

BOOL  E7XX_MOV(int ID, const char* szAxes, const double* pdValueArray);
BOOL  E7XX_qMOV(int ID, const char* szAxes, double* pdValueArray);
BOOL  E7XX_MVR(int ID, const char* szAxes, const double* pdValueArray);
BOOL  E7XX_qPOS(int ID, const char* szAxes, double* pdValueArray);
BOOL  E7XX_IsMoving(int ID, const char* szAxes, BOOL* pbValueArray);
BOOL  E7XX_HLT(int ID, const char* szAxes);
BOOL  E7XX_qONT(int ID, const char* szAxes, BOOL* pbValueArray);

BOOL  E7XX_SVA(int ID, const char* szAxes, const double* pdValueArray);
BOOL  E7XX_qSVA(int ID, const char* szAxes, double* pdValueArray);
BOOL  E7XX_SVR(int ID, const char* szAxes, const double* pdValueArray);

BOOL  E7XX_DFH(int ID, const char* szAxes);
BOOL  E7XX_qDFH(int ID, const char* szAxes, double* pdValueArray);
BOOL  E7XX_GOH(int ID, const char* szAxes);
BOOL  E7XX_DFF(int ID, const char* szAxes, const double* pdValueArray);
BOOL  E7XX_qDFF(int ID, const char* szAxes, double* pdValueArray);

%cstring_output_maxsize(char* szNames, int iBufferSize);
BOOL  E7XX_qCST(int ID, const char* szAxes, char* szNames, int iBufferSize);
BOOL  E7XX_CST(int ID, const char* szAxes, const char* szNames);
%cstring_output_maxsize(char* szValideStages, int iBufferSize);
BOOL  E7XX_qVST(int ID, char* szValideStages, int iBufferSize);
%cstring_output_maxsize(char* szPossibleAxisCharacters, int iBufferSize);
BOOL  E7XX_qTVI(int ID, char* szPossibleAxisCharacters, int iBufferSize);

BOOL  E7XX_SVO(int ID, const char* szAxes, const int* pbValueArray);
BOOL  E7XX_qSVO(int ID, const char* szAxes, BOOL* pbValueArray);

BOOL  E7XX_VCO(int ID, const char* szAxes, const BOOL* pbValueArray);
BOOL  E7XX_qVCO(int ID, const char* szAxes, BOOL* pbValueArray);

BOOL  E7XX_VEL(int ID, const char* szAxes, const double* pdValueArray);
BOOL  E7XX_qVEL(int ID, const char* szAxes, double* pdValueArray);

BOOL  E7XX_SPA(int ID, const char* szAxes, const int* iParameterArray, const double* pdValueArray, const char* szStrings);
BOOL  E7XX_qSPA(int ID, const char* szAxes, int* iParameterArray, double* pdValueArray, char* szStrings, int iMaxStringSize);
BOOL  E7XX_SEP(int ID, const char* szPassword, const char* szAxes, const int* iParameterArray, const double* pdValueArray, const char* szStrings);
BOOL  E7XX_qSEP(int ID, const char* szAxes, int* iParameterArray, double* pdValueArray, char* szStrings, int iMaxStringSize);
BOOL  E7XX_WPA(int ID, const char* szPassword, const char* szAxes, const int* iParameterArray);
BOOL  E7XX_RPA(int ID, const char* szAxes, const int* iParameterArray);
BOOL  E7XX_SPA_String(int ID, const char* szAxes, const int* iParameterArray, const char* szStrings);
BOOL  E7XX_qSPA_String(int ID, const char* szAxes, int* iParameterArray, char* szStrings, int iMaxStringSize);
BOOL  E7XX_SEP_String(int ID, const char* szPassword, const char* szAxes, const int* iParameterArray, const char* szStrings);
BOOL  E7XX_qSEP_String(int ID, const char* szAxes, int* iParameterArray, char* szStrings, int iMaxStringSize);

BOOL  E7XX_STE(int ID, char cAxis, double dStepSize);
BOOL  E7XX_qSTE(int ID, char cAxis, int iOffsetOfFirstPointInRecordTable, int iNumberOfValues, double* pdValueArray);
BOOL  E7XX_IMP(int ID, char cAxis, double dImpulseSize);
BOOL  E7XX_IMP_PulseWidth(int ID, char cAxis, double dImpulseSize, int iPulseWidth);
BOOL  E7XX_qIMP(int ID, char cAxis, int iOffsetOfFirstPointInRecordTable, int iNumberOfValues, double* pdValueArray);

BOOL  E7XX_SAI(int ID, const char* szOldAxes, const char* szNewAxes);
%cstring_output_maxsize(char* axes, int iBufferSize);
BOOL  E7XX_qSAI(int ID, char* axes, int iBufferSize);
BOOL  E7XX_qSAI_ALL(int ID, char* axes, int iBufferSize);

BOOL  E7XX_CCL(int ID, int iComandLevel, const char* szPassWord);
BOOL  E7XX_qCCL(int ID, int* piComandLevel);

BOOL  E7XX_AVG(int ID, int iAverrageTime);
BOOL  E7XX_qAVG(int ID, int *iAverrageTime);

BOOL  E7XX_DIO(int ID, const char* szChannels, const BOOL* pbValueArray);
BOOL  E7XX_qTIO(int ID, int* piInputNr, int* piOutputNr);

/////////////////////////////////////////////////////////////////////////////
// String commands.
BOOL  E7XX_E7XXSendString(int ID, const char* szString);
BOOL  E7XX_E7XXGetLineSize(int ID, int* iLineSize);
BOOL  E7XX_E7XXReadLine(int ID, char* szString, int iBufferSize);
BOOL  E7XX_GcsCommandset(int ID, const char* szCommand);
BOOL  E7XX_GcsGetAnswer(int ID, char* szAnswer, int iBufferSize);
BOOL  E7XX_GcsGetAnswerSize(int ID, int* iAnswerSize);


/////////////////////////////////////////////////////////////////////////////
// limits
BOOL  E7XX_ATZ(int ID,  const char* szAxes, const double* pdLowVoltageArray, const BOOL* pfUseDefaultArray);
BOOL  E7XX_qTMN(int ID, const char* szAxes, double* pdValueArray);
BOOL  E7XX_qTMX(int ID, const char* szAxes, double* pdValueArray);
BOOL  E7XX_NLM(int ID, const char* szAxes, const double* pdValueArray);
BOOL  E7XX_qNLM(int ID, const char* szAxes, double* pdValueArray);
BOOL  E7XX_PLM(int ID, const char* szAxes, const double* pdValueArray);
BOOL  E7XX_qPLM(int ID, const char* szAxes, double* pdValueArray);
BOOL  E7XX_GetRefResult(int ID, const char* szAxes, int* piReferenceResult);


/////////////////////////////////////////////////////////////////////////////
// Wave commands.
BOOL  E7XX_WAV_SIN_P(int ID, const char* szWaveTableId, int iOffsetOfFirstPointInWaveTable, int iNumberOfPoints, int iAddAppendWave, int iCenterPointOfWave, double dAmplitudeOfWave, double dOffsetOfWave, int iSegmentLength);
BOOL  E7XX_WAV_LIN(int ID, const char* szWaveTableId, int iOffsetOfFirstPointInWaveTable, int iNumberOfPoints, int iAddAppendWave, int iNumberOfSpeedUpDownPointsInWave, double dAmplitudeOfWave, double dOffsetOfWave, int iSegmentLength);
BOOL  E7XX_WAV_RAMP(int ID, const char* szWaveTableId, int iOffsetOfFirstPointInWaveTable, int iNumberOfPoints, int iAddAppendWave, int iCenterPointOfWave, int iNumberOfSpeedUpDownPointsInWave, double dAmplitudeOfWave, double dOffsetOfWave, int iSegmentLength);
BOOL  E7XX_WAV_PNT(int ID, const char* szWaveTableId, int iOffsetOfFirstPointInWaveTable, int iNumberOfPoints, int iAddAppendWave, double* pdWavePoints);
BOOL  E7XX_qWAV(int ID, const char* szWaveTableIds, int* piParamereIdsArray, double* pdValueArray);
BOOL  E7XX_qGWD(int ID, char cWaveTableId, int iOffsetOfFirstPointInWaveTable, int iNumberOfValues, double* pdValueArray);
BOOL  E7XX_WGO(int ID, const char* szWaveGeneratorIds, const int* iStartModArray);
BOOL  E7XX_qWGO(int ID, const char* szWaveGeneratorIds, int* piValueArray);
BOOL  E7XX_WGC(int ID, const char* szWaveGeneratorIds, const int* piNumberOfCyclesArray);
BOOL  E7XX_qWGC(int ID, const char* szWaveGeneratorIds, int* piValueArray);
%apply int *OUTPUT { int *iRecordCannels };
BOOL  E7XX_qTNR(int ID, int* iRecordCannels);
BOOL  E7XX_DRC(int ID, const int* piRecordChannelIdsArray, const char* szRecordSourceIds, const int* piRecordOptionArray, const int* piTriggerOption);
BOOL  E7XX_qDRC(int ID, const int* piRecordChannelIdsArray, char* szRecordSourceIds, int* piRecordOptionArray, int* piTriggerOption, int iArraySize);
BOOL  E7XX_WGR(int ID);
BOOL  E7XX_qDRR_SYNC(int ID, int iRecordChannelId, int iOffsetOfFirstPointInRecordTable, int iNumberOfValues, double* pdValueArray);
BOOL  E7XX_RTR(int ID, int iReportTableRate);
BOOL  E7XX_qRTR(int ID, int* piReportTableRate);
BOOL  E7XX_qTWG(int ID, int* piGenerator);
BOOL  E7XX_WMS(int ID, const char* szWaveTablesIds, const int* iMaxWaveSize);
BOOL  E7XX_qWMS(int ID, const char* szWaveTablesIds, int* iMaxWaveSize);
BOOL  E7XX_DTC(int ID, int iDdlTableId);
BOOL  E7XX_WCL(int ID, int iWaveTableId);
BOOL  E7XX_DDL(int ID, int iDdlTableId, int iOffsetOfFirstPointInDdlTable, int iNumberOfValues, const double* pdValueArray);
BOOL  E7XX_qDDL(int ID, int iDdlTableId, int iOffsetOfFirstPointInDdlTable, int iNumberOfValues, double* pdValueArray);
BOOL  E7XX_TWS(int ID, const int* piWavePointNumberArray, const int* piTriggerLevelArray, int iNumberOfPoints);
BOOL  E7XX_TWC(int ID);
BOOL  E7XX_qTLT(int ID, int* piDdlTables);
BOOL  E7XX_DPO(int ID, const char* szAxes);
BOOL  E7XX_IsGeneratorRunning(int ID, const char* szWaveGeneratorIds, BOOL* pbValueArray);


/////////////////////////////////////////////////////////////////////////////
// Piezo-Channel commands.
BOOL  E7XX_VMA(int ID, const char* szPiezoChannels, const double* pdValueArray);
BOOL  E7XX_qVMA(int ID, const char* szPiezoChannels, double* pdValueArray);
BOOL  E7XX_VMI(int ID, const char* szPiezoChannels, const double* pdValueArray);
BOOL  E7XX_qVMI(int ID, const char* szPiezoChannels, double* pdValueArray);
BOOL  E7XX_VOL(int ID, const char* szPiezoChannels, const double* pdValueArray);
BOOL  E7XX_qVOL(int ID, const char* szPiezoChannels, double* pdValueArray);
%apply int *OUTPUT { int *iPiezoCannels };
BOOL  E7XX_qTPC(int ID, int* iPiezoCannels);


/////////////////////////////////////////////////////////////////////////////
// Sensor-Channel commands.
BOOL  E7XX_qTAD(int ID, const char* szSensorChannels, int* piValueArray);
BOOL  E7XX_qTNS(int ID, const char* szSensorChannels, double* pdValueArray);
BOOL  E7XX_qTSP(int ID, const char* szSensorChannels, double* pdValueArray);
%apply int *OUTPUT { int *iSensorCannels };
BOOL  E7XX_qTSC(int ID, int* iSensorCannels);
BOOL  E7XX_qTAV(int ID, const char* szAnalogInputChannels, int* piValarray);

/////////////////////////////////////////////////////////////////////////////
// Spezial
BOOL E7XX_GetSupportedFunctions(int ID, int* piComandLevelArray, int iMaxlen, char* szFunctionNames, int iMaxFunctioNamesLength);
BOOL E7XX_GetSupportedParameters(int ID, int* piParameterIdArray, int* piComandLevelArray, int* piMennoryLocationArray, int iMaxlen, char* szParameterName, int iMaxParameterNameSize);
BOOL E7XX_GetSupportedControllers(char* szBuffer, int iBufferSize);
BOOL E7XX_NMOV(int ID, const char* szAxes, const double* pdValueArray);
BOOL E7XX_NMVR(int ID, const char* szAxes, const double* pdValueArray);

BOOL E7XX_TWS_EQU_DIST(int ID, int iTriggerPointStart, int iTriggerDistance, int iTriggerPointsPerPuls, int iTriggerPointsCount, int iTriggerLevel);
BOOL E7XX_WAV_LIN_SPEED_UP(int ID, int iSpeedUpDown, double rSpeed, double* rSpeedUpDown);


BOOL E761_SetDirectTarget(int ID, const PI_E761_DIRECT_TARGET_WRITE piDirectTargetData);
BOOL E761_GetDirectPosition(int ID, PI_E761_DIRECT_POSITION_READ *ppiDirectPositionData);

