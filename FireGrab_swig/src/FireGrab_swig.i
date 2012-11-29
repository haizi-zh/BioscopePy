/* File: FireGrab.i */
%module(docstring = "This is the python wrapper for AVT FireGrab library.") FireGrab_swig

%include "carrays.i"
%include "cpointer.i"
%include "cstring.i"
%include "cdata.i"
%include "typemaps.i"

typedef unsigned int UINT32;
typedef unsigned char UINT8;
typedef unsigned short UINT16;

%array_functions(char, charArray);

%{
#define SWIG_FILE_WITH_INIT
#include "FireGrab_swig.h"
%}


%feature("autodoc", "1");

UINT32 MakeImageFormat(int Res, int Col, int RateOrMode);

unsigned int test(FGFRAME* pFrame, int n);

////////////////////////

// Frame flags
enum FGF
{
	FGF_INVALID = 0x00000001,      // Data area might be damaged
	FGF_LAST = 0x00000002,      // Last in queue
	FGF_DMAHALTED = 0x00000004,      // Dma was halted in between
	FGF_FORCEPOST = 0x10000000      // Force post to driver in LIMPMODE
};

// Special parameter value for burst count
enum BC
{
	BC_INFINITE = 0,
	BC_ONESHOT = 1,
};

// Enumeration for resolutions
enum FG_RESOLUTION
{
  RES_160_120=0,
  RES_320_240,
  RES_640_480,
  RES_800_600,
  RES_1024_768,
  RES_1280_960,
  RES_1600_1200,
  RES_SCALABLE,
  RES_LAST
};

// Enumeration for color modes
enum FG_COLORMODE
{
  CM_Y8=0,
  CM_YUV411,
  CM_YUV422,
  CM_YUV444,
  CM_RGB8,
  CM_Y16,
  CM_RGB16,
  CM_SY16,
  CM_SRGB16,
  CM_RAW8,
  CM_RAW16,
  CM_LAST
};

// Enumeration for frame rates
enum FG_FRAMERATE
{
  FR_1_875=0,
  FR_3_75,
  FR_7_5,
  FR_15,
  FR_30,
  FR_60,
  FR_120,
  FR_240,
  FR_LAST
};

// Enumeration for DMA mode
enum FG_DMA
{
  DMA_CONTINOUS=0,
  DMA_LIMP,
  DMA_REPLACE,
  DMA_LAST
};

// Enumeration for Bayer pattern
enum FG_BAYERPATTERN
{
  BP_RGGB=0,
  BP_GRBG,
  BP_BGGR,
  BP_GBRG,
  BP_LAST
};

// Specific Parameter data types
enum FG_PARSPECIFIC
{
  FGPS_INVALID=0,
  FGPS_FEATUREINFO,
  FGPS_TRIGGERINFO,
  FGPS_COLORFORMAT,
  FGPS_LAST
};

// Error codes
enum FG_ERROR
{
	FCE_NOERROR = 0,     /* No Error */
	FCE_ALREADYOPENED = 1001,     /* Something already opened */
	FCE_NOTOPENED = 1002,     /* Need open before */
	FCE_NODETAILS = 1003,     /* No details */
	FCE_DRVNOTINSTALLED = 1004,     /* Driver not installed */
	FCE_MISSINGBUFFERS = 1005,     /* Don't have buffers */
	FCE_INPARMS = 1006,     /* Parameter error */
	FCE_CREATEDEVICE = 1007,     /* Error creating WinDevice */
	FCE_WINERROR = 1008,     /* Internal Windows error */
	FCE_IOCTL = 1009,     /* Error DevIoCtl */
	FCE_DRVRETURNLENGTH = 1010,     /* Wrong length return data */
	FCE_INVALIDHANDLE = 1011,     /* Wrong handle */
	FCE_NOTIMPLEMENTED = 1012,     /* Function not implemented */
	FCE_DRVRUNNING = 1013,     /* Driver runs already */
	FCE_STARTERROR = 1014,     /* Couldn't start */
	FCE_INSTALLERROR = 1015,     /* Installation error */
	FCE_DRVVERSION = 1016,     /* Driver has wrong version */
	FCE_NODEADDRESS = 1017,     /* Wrong nodeaddress */
	FCE_PARTIAL = 1018,     /* Partial info. copied */
	FCE_NOMEM = 1019,     /* No memory */
	FCE_NOTAVAILABLE = 1020,     /* Requested function not available */
	FCE_NOTCONNECTED = 1021,     /* Not connected to target */
	FCE_ADJUSTED = 1022     /* A pararmeter had to be adjusted */
};

// HALER
enum HALER
{
	/* Lowest layer errors */
	HALER_NOERROR = 0,
	HALER_NOCARD = 1,   /* Card is not present */
	HALER_NONTDEVICE = 2,   /* No logical Device */
	HALER_NOMEM = 3,   /* Not enough memory */
	HALER_MODE = 4,   /* Not allowed in this mode */
	HALER_TIMEOUT = 5,   /* Timeout */
	HALER_ALREADYSTARTED = 6,   /* Something is started */
	HALER_NOTSTARTED = 7,   /* Not started */
	HALER_BUSY = 8,   /* Busy at the moment */
	HALER_NORESOURCES = 9,   /* No resources available */
	HALER_NODATA = 10,   /* No data available */
	HALER_NOACK = 11,   /* Didn't get acknowledge */
	HALER_NOIRQ = 12,   /* Interruptinstallerror */
	HALER_NOBUSRESET = 13,   /* Error waiting for busreset */
	HALER_NOLICENSE = 14,   /* No license */
	HALER_RCODEOTHER = 15,   /* RCode not RCODE_COMPLETE */
	HALER_PENDING = 16,   /* Something still pending */
	HALER_INPARMS = 17,   /* Input parameter range */
	HALER_CHIPVERSION = 18,   /* Unrecognized chipversion */
	HALER_HARDWARE = 19,   /* Hardware error */
	HALER_NOTIMPLEMENTED = 20,   /* Not implemented */
	HALER_CANCELLED = 21,   /* Cancelled */
	HALER_NOTLOCKED = 22,   /* Memory is not locked */
	HALER_GENERATIONCNT = 23,   /* Bus reset in between */
	HALER_NOISOMANAGER = 24,   /* No IsoManager present */
	HALER_NOBUSMANAGER = 25,   /* No BusManager present */
	HALER_UNEXPECTED = 26,   /* Unexpected value */
	HALER_REMOVED = 27,   /* Target was removed */
	HALER_NOBUSRESOURCES = 28,   /* No ISO resources available */
	HALER_DMAHALTED = 29   /* DMA halted */
};

// Enumeration for physical speed
enum FG_PHYSPEED
{
  PS_100MBIT=0,
  PS_200MBIT,
  PS_400MBIT,
  PS_800MBIT,
  PS_AUTO,
  PS_LAST
};

// Parameters
enum FG_PARAMETER
{
  FGP_IMAGEFORMAT=0,                            // Compact image format
  FGP_ENUMIMAGEFORMAT,                          // Enumeration (Reset,Get)
  FGP_BRIGHTNESS,                               // Set image brightness
  FGP_AUTOEXPOSURE,                             // Set auto exposure
  FGP_SHARPNESS,                                // Set image sharpness
  FGP_WHITEBALCB,                               // Blue
  FGP_WHITEBALCR,                               // Red
  FGP_HUE,                                      // Set image hue
  FGP_SATURATION,                               // Set color saturation
  FGP_GAMMA,                                    // Set gamma
  FGP_SHUTTER,                                  // Shutter time
  FGP_GAIN,                                     // Gain
  FGP_IRIS,                                     // Iris
  FGP_FOCUS,                                    // Focus
  FGP_TEMPERATURE,                              // Color temperature
  FGP_TRIGGER,                                  // Trigger
  FGP_TRIGGERDLY,                               // Delay of trigger
  FGP_WHITESHD,                                 // Whiteshade
  FGP_FRAMERATE,                                // Frame rate
  FGP_ZOOM,                                     // Zoom
  FGP_PAN,                                      // Pan
  FGP_TILT,                                     // Tilt
  FGP_OPTICALFILTER,                            // Filter
  FGP_CAPTURESIZE,                              // Size of capture
  FGP_CAPTUREQUALITY,                           // Quality
  FGP_PHYSPEED,                                 // Set speed for asy/iso
  FGP_XSIZE,                                    // Image XSize
  FGP_YSIZE,                                    // Image YSize
  FGP_XPOSITION,                                // Image x position
  FGP_YPOSITION,                                // Image y position
  FGP_PACKETSIZE,                               // Packet size
  FGP_DMAMODE,                                  // DMA mode (continuous or limp)
  FGP_BURSTCOUNT,                               // Number of images to produce
  FGP_FRAMEBUFFERCOUNT,                         // Number of frame buffers
  FGP_USEIRMFORBW,                              // Allocate bandwidth or not (IsoRscMgr)
  FGP_ADJUSTPARAMETERS,                         // Adjust parameters or fail
  FGP_STARTIMMEDIATELY,                         // Start bursting immediately
  FGP_FRAMEMEMORYSIZE,                          // Read only: Frame buffer size
  FGP_COLORFORMAT,                              // Read only: Colorformat
  FGP_IRMFREEBW,                                // Read only: Free iso bytes for 400MBit
  FGP_DO_FASTTRIGGER,                           // Fast trigger (no ACK)
  FGP_DO_BUSTRIGGER,                            // Broadcast trigger
  FGP_RESIZE,                                   // Start/Stop resizing
  FGP_USEIRMFORCHN,                             // Get channel over isochronous resource manager
  FGP_CAMACCEPTDELAY,                           // Delay after writing values
  FGP_ISOCHANNEL,                               // Iso channel
  FGP_CYCLETIME,                                // Read cycle time
  FGP_DORESET,                                  // Reset camera
  FGP_DMAFLAGS,                                 // Flags for ISO DMA
  FGP_R0C,                                      // Ring 0 call gate
  FGP_BUSADDRESS,                               // Exact bus address
  FGP_CMDTIMEOUT,                               // Global bus command timeout
  FGP_CARD,                                     // Card number of this camera (set before connect)
  FGP_LICENSEINFO,                              // Query license information
  FGP_PACKETCOUNT,                              // Read only: Packet count
  FGP_DO_MULTIBUSTRIGGER,                       // Do trigger on several busses
  FGP_CARDRESET,                                // Do reset on card (for hard errors)

  FGP_LAST
};

typedef struct
{
  UINT32        IsValue;                        // Actual value
  UINT32        MinValue;                       // Parameters min. value
  UINT32        MaxValue;                       // Parameters max. value
  UINT32        Unit;                           // Parameters unit
  FGPSPECIFIC   Specific;                       // Parameters specific
}FGPINFO;

typedef struct
{
  UINT32        Low;
  UINT32        High;
}UINT32HL;

typedef struct                                  // Info for a device
{
  UINT32HL      Guid;                           // GUID of this device
  UINT8         CardNumber;                     // Card number
  UINT8         NodeId;                         // Depends on bus topology
  UINT8         Busy;                           // Actually busy
}FGNODEINFO;

typedef struct                                  // Struct for a frame
{
  void*         System;                         // For system use only
  UINT32        Flags;                          // Flags: Last, Invalid, no post etc...
  UINT16        Id;                             // Continous ID
  UINT8        *pData;                          // Data pointer
  UINT32        Length;                         // Buffers length
  UINT32HL      RxTime;                         // Receive time as 100ns ticks since 1.1.1601
  UINT32        BeginCycleTime;                 // Frame begin as bus time
  UINT32        EndCycleTime;                   // Frame end as bus time
  UINT32        Reserved[2];                    // Reserved for future use
}FGFRAME;

%array_functions(FGNODEINFO, FGNodeInfoArray);

UINT32 FGInitModule();
void   FGExitModule();

%apply int *OUTPUT { UINT32 *pRealCnt };
UINT32 FGGetNodeList(FGNODEINFO *pInfo,UINT32 MaxCnt,UINT32 *pRealCnt);
%cstring_output_maxsize(char *pStr,UINT32 MaxLen);
UINT32  FGGetHostLicenseRequest(char *pStr,UINT32 MaxLen);
%apply int *OUTPUT { UINT8 *pLicenseType };
UINT32  FGGetLicenseInfo(UINT8 *pLicenseType);

%cstring_output_withsize(char* pData, int* pLen);
void Deinterlace(FGFRAME *pFrame, int method, int width, int height, int scanline, char* pData, int* pLen);
void DeinterlaceTest(char* pData, int* pLen);

class CCamera;

class  CFGCamera
{
public:
                        CFGCamera();
  virtual              ~CFGCamera();
  virtual UINT32        WriteRegister(UINT32 Address,UINT32 Value);
  %apply int *OUTPUT { UINT8 *pValue };
  virtual UINT32        ReadRegister(UINT32 Address,UINT32 *pValue);
  virtual UINT32        WriteBlock(UINT32 Address,UINT8 *pData,UINT32 Length);
  virtual UINT32        ReadBlock(UINT32 Address,UINT8 *pData,UINT32 Length);

  virtual UINT32        Connect(UINT32HL *pGuid);
  virtual UINT32        Disconnect();

  virtual UINT32        SetParameter(UINT16 Which,UINT32 Value);
  %apply int *OUTPUT { UINT8 *pValue };
  virtual UINT32        GetParameter(UINT16 Which,UINT32 *pValue);
  virtual UINT32        GetParameterInfo(UINT16 Which,FGPINFO *pInfo);

  virtual UINT32        OpenCapture();
  virtual UINT32        CloseCapture();

  virtual UINT32        AssignUserBuffers(UINT32 Cnt,UINT32 Size,void* *ppMemArray);

  virtual UINT32        StartDevice();
  virtual UINT32        StopDevice();

  virtual UINT32        GetFrame(FGFRAME *pFrame,UINT32 TimeoutInMs=INFINITE);
  virtual UINT32        PutFrame(FGFRAME *pFrame);
  virtual UINT32        DiscardFrames();

  %cstring_output_maxsize(char *pAll,UINT32 MaxLength);
  virtual UINT32        GetDeviceName(char *pAll,UINT32 MaxLength);
  virtual void*         GetContext();
  %cstring_output_maxsize(char *pStr,UINT32 MaxLen);
  virtual UINT32        GetLicenseRequest(char *pStr,UINT32 MaxLen);
};

////////////////////////////////////////////////////////////////////////////////
// Class for a broadcast object.
////////////////////////////////////////////////////////////////////////////////

class  CBroadcast
{
protected:
  CFGCamera            *m_pFGCamera;
  void                 *m_Handle;

public:
                        CBroadcast(CFGCamera *pFGCamera);

  virtual UINT32        WriteRegister(UINT32 Address,UINT32 Value);
  virtual UINT32        WriteBlock(UINT32 Address,UINT8 *pData,UINT32 Length);
};

////////////////////////////////////////////////////////////////////////////////
// Class for a pure DMA object.
////////////////////////////////////////////////////////////////////////////////

class CIsoDma;

class CFGIsoDma
{
public:
  CIsoDma              *m_pIsoDma;              // Worker object

                        CFGIsoDma();
  virtual               ~CFGIsoDma();

  virtual UINT32        OpenCapture(FGISODMAPARMS *pParms);
  virtual UINT32        CloseCapture();

  virtual UINT32        GetFrame(FGFRAME *pFrame,UINT32 TimeoutInMs);
  virtual UINT32        PutFrame(FGFRAME *pFrame);
  virtual UINT32        DiscardFrames();

  virtual UINT32        AssignUserBuffers(UINT32 Cnt,UINT32 Size,void* *ppMemArray);
  virtual UINT32        Resize(UINT32 PktCnt,UINT32 PktSize);
};

class PVAL
{
public:
  // Special parameter value for DCAM 'feature'
  static const UINT32 PVAL_OFF = ((unsigned long)-1);
  static const UINT32 PVAL_AUTO = ((unsigned long)-2);
  static const UINT32 PVAL_ONESHOT = ((unsigned long)-3);
};