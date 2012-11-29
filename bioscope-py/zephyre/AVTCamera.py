'''
Created on Mar 21, 2012

@author: Zephyre
'''

import FireGrab_swig as fg
import logging
import threading
import numpy
import Queue
import sys
import time
import json

camErrNo = {}
with open('CamErrNo.txt', 'r') as errFile:
    data = errFile.readlines()[0]
    camErrNo = json.loads(data)
    
class AVTCameraError(Exception):
    '''
    General AVT camera error
    '''
    def __init__(self, errId= -1, errMsg=''):
        self.__errId, self.__errMsg = errId, errMsg
        if camErrNo.has_key(errId):
            self.__errMsg = camErrNo[errId]
        
    def __str__(self):
        return 'Error id: %d, message: %s' % (self.__errId, self.__errMsg)
    
class AVTCamera(object):
    '''
    A python class for AVTCamera
    '''
    
    parameters = {
        'FGP_IMAGEFORMAT':0,
        'FGP_ENUMIMAGEFORMAT':1,
        'FGP_BRIGHTNESS':2,
        'FGP_AUTOEXPOSURE':3,
        'FGP_SHARPNESS':4,
        'FGP_WHITEBALCB':5,
        'FGP_WHITEBALCR':6,
        'FGP_HUE':7,
        'FGP_SATURATION':8,
        'FGP_GAMMA':9,
        'FGP_SHUTTER':10,
        'FGP_GAIN':11,
        'FGP_IRIS':12,
        'FGP_FOCUS':13,
        'FGP_TEMPERATURE':14,
        'FGP_TRIGGER':15,
        'FGP_TRIGGERDLY':16,
        'FGP_WHITESHD':17,
        'FGP_FRAMERATE':18,
        'FGP_ZOOM':19,
        'FGP_PAN':20,
        'FGP_TILT':21,
        'FGP_OPTICALFILTER':22,
        'FGP_CAPTURESIZE':23,
        'FGP_CAPTUREQUALITY':24,
        'FGP_PHYSPEED':25,
        'FGP_XSIZE':26,
        'FGP_YSIZE':27,
        'FGP_XPOSITION':28,
        'FGP_YPOSITION':29,
        'FGP_PACKETSIZE':30,
        'FGP_DMAMODE':31,
        'FGP_BURSTCOUNT':32,
        'FGP_FRAMEBUFFERCOUNT':33,
        'FGP_USEIRMFORBW':34,
        'FGP_ADJUSTPARAMETERS':35,
        'FGP_STARTIMMEDIATELY':36,
        'FGP_FRAMEMEMORYSIZE':37,
        'FGP_COLORFORMAT':38,
        'FGP_IRMFREEBW':39,
        'FGP_DO_FASTTRIGGER':40,
        'FGP_DO_BUSTRIGGER':41,
        'FGP_RESIZE':42,
        'FGP_USEIRMFORCHN':43,
        'FGP_CAMACCEPTDELAY':44,
        'FGP_ISOCHANNEL':45,
        'FGP_CYCLETIME':46,
        'FGP_DORESET':47,
        'FGP_DMAFLAGS':48,
        'FGP_R0C':49,
        'FGP_BUSADDRESS':50,
        'FGP_CMDTIMEOUT':51,
        'FGP_CARD':52,
        'FGP_LICENSEINFO':53,
        'FGP_PACKETCOUNT':54,
        'FGP_DO_MULTIBUSTRIGGER':55,
        'FGP_CARDRESET':56,
        }
    
    @staticmethod
    def initLibrary():
        ret = fg.FGInitModule()
        if ret != fg.FCE_NOERROR:
            raise AVTCameraError(ret)
        
    @staticmethod
    def releaseLibrary():
        fg.FGExitModule()
    
    @classmethod
    def getNodeList(cls):
        '''
        Get available node list.
        '''
        maxCnt = 16
        nodeList = fg.new_FGNodeInfoArray(maxCnt)
        ret, cnt = fg.FGGetNodeList(nodeList, maxCnt)
        if ret != fg.FCE_NOERROR:
            raise AVTCameraError(ret)
        return tuple(fg.FGNodeInfoArray_getitem(nodeList, i) for i in xrange(cnt))
    
    @classmethod
    def makeCameraInstance(cls, node):
        return cls(node)
    
    def __init__(self, node):
        '''
        Constructor. node is returned by getNodeList
        '''
        self.__node = node
        self.__cam = fg.CFGCamera()
        self.isConnected = False
        self.__thread = None
        self.deinterlace = None
        self.__imageCache = Queue.Queue(64)
        self.__stopFlag = False
        self.__imageMode = 0

    def connect(self):
        ret = self.__cam.Connect(self.__node.Guid)
        if ret != fg.FCE_NOERROR:
            raise AVTCameraError(ret)
        ret = self.__cam.SetParameter(fg.FGP_XPOSITION, 0)
        if ret != fg.FCE_NOERROR:
            raise AVTCameraError(ret)
        ret = self.__cam.SetParameter(fg.FGP_YPOSITION, 0)
        if ret != fg.FCE_NOERROR:
            raise AVTCameraError(ret)
        self.isConnected = True
        
    def disconnect(self):
        ret = self.__cam.Disconnect()
        if ret != fg.FCE_NOERROR:
            raise AVTCameraError(ret)
        self.isConnected = False
        
    def setImageMode(self, mode):
        ret = self.__cam.SetParameter(fg.FGP_IMAGEFORMAT, fg.MakeImageFormat(fg.RES_SCALABLE, fg.CM_Y8, mode))
        if ret != fg.FCE_NOERROR:
            raise AVTCameraError(ret)
        self.__imageMode = mode
    @property
    def imageMode(self):
        return self.__imageMode
    
    def getParameter(self, para):
        pinfo = fg.FGPINFO()
        ret = self.__cam.GetParameterInfo(para, pinfo)
        if ret != fg.FCE_NOERROR:
            raise AVTCameraError(ret)
        if pinfo.IsValue == fg.PVAL.PVAL_OFF:
            val = 'OFF'
        elif pinfo.IsValue == fg.PVAL.PVAL_ONESHOT:
            val = 'ONESHOT'
        elif pinfo.IsValue == fg.PVAL.PVAL_AUTO:
            val = 'Auto'
        else:
            val = pinfo.IsValue
        return {'Value':val, 'Min':pinfo.MinValue, 'Max':pinfo.MaxValue}
    
    def setParameter(self, para, value):
        ret = self.__cam.SetParameter(para, value)
        if ret != fg.FCE_NOERROR:
            raise AVTCameraError(ret)
    
    @property
    def brightness(self):
        return self.getParameter(fg.FGP_BRIGHTNESS)
    @brightness.setter
    def brightness(self, value):
        self.setParameter(fg.FGP_BRIGHTNESS, value)
    
    @property
    def shutter(self):
        return self.getParameter(fg.FGP_SHUTTER)
    @shutter.setter
    def shutter(self, value):
        self.setParameter(fg.FGP_SHUTTER, value)
        
    @property
    def gain(self):
        return self.getParameter(fg.FGP_GAIN)
    @gain.setter
    def gain(self, value):
        self.setParameter(fg.FGP_GAIN, value)
        
    @property
    def deviceName(self):
        ret, name = self.__cam.GetDeviceName(512)
        if ret != fg.FCE_NOERROR:
            raise AVTCameraError(ret)
        return name
    
    def openCapture(self):
        ret = self.__cam.OpenCapture()
        if ret != fg.FCE_NOERROR:
            raise AVTCameraError(ret)
        
    def closeCapture(self):
        ret = self.__cam.CloseCapture()
        if ret != fg.FCE_NOERROR:
            raise AVTCameraError(ret)
        
    @property
    def burstCount(self):
        return self.getParameter(fg.FGP_BURSTCOUNT)
    @burstCount.setter
    def burstCount(self, value):
        self.setParameter(fg.FGP_BURSTCOUNT, value)
        
    @property
    def roi(self):
        return map(lambda x : self.getParameter(x)['Value'],
                 (fg.FGP_XPOSITION, fg.FGP_YPOSITION, fg.FGP_XSIZE, fg.FGP_YSIZE))
    @roi.setter
    def roi(self, value):
        map(lambda para, v:self.setParameter(para, v),
            (fg.FGP_XPOSITION, fg.FGP_YPOSITION, fg.FGP_XSIZE, fg.FGP_YSIZE), value)
        
    @property
    def width(self):
        return self.getParameter(fg.FGP_XSIZE)
    @property
    def height(self):
        return self.getParameter(fg.FGP_YSIZE)
        

    def snapshot(self, timeout=1):
        self.__imageCache = Queue.Queue(64)
        self.burstCount = 2
        self.openCapture()
        ret = self.__cam.StartDevice()
        if ret != fg.FCE_NOERROR:
            raise AVTCameraError(ret)
        frame = fg.FGFRAME()
        for i in xrange(2):
            ret = self.__cam.GetFrame(frame)
            if ret != fg.FCE_NOERROR:
                raise AVTCameraError(ret)
            if i != 1:
                ret = self.__cam.PutFrame(frame)
                if ret != fg.FCE_NOERROR:
                    raise AVTCameraError(ret)
                continue
            
            try:
                rc = self.roi
                w = rc[2]
                h = rc[3]
                flagInvalid = frame.Flags & fg.FGF_INVALID
                flagLast = frame.Flags & fg.FGF_LAST
                flagDMAHalted = frame.Flags & fg.FGF_DMAHALTED
                flagForcePost = frame.Flags & fg.FGF_FORCEPOST
                tsl = frame.RxTime.Low
                tsh = frame.RxTime.High
                if self.deinterlace is None:
                    # No deinterlace
                    rawData = fg.cdata(frame.pData, frame.Length)
                else:
                    rawData = fg.Deinterlace(frame, self.deinterlace, w, h, w, w * h)
                snapshotData = {'RawData':rawData, 'ROI':rc,
                        'FrameId':frame.Id, 'Invalid':bool(flagInvalid), 'Last':bool(flagLast),
                        'DMAHalted':bool(flagDMAHalted), 'ForcePost':bool(flagForcePost),
                        'TimeStamp':tsl, 'BufferLength':frame.Length,
                        'Depth':8}
            except Queue.Full:
                logging.debug('Queue full')
                pass
            finally:
                ret = self.__cam.PutFrame(frame)
                if ret != fg.FCE_NOERROR:
                    raise AVTCameraError(ret)
        
        self.__cam.StopDevice()
        self.__cam.CloseCapture()
        return snapshotData
    
    @property
    def isAcquiring(self):
        return self.__thread.isAlive() if self.__thread is not None else False
    
    def startDevice(self, count=None):
        self.__imageCache = Queue.Queue(64)
        if count is None:
            frameCnt = self.burstCount['Value']
            self.burstCount = frameCnt
        else:
            self.burstCount = count
            frameCnt = count        
        rc = self.roi
        ret = self.__cam.StartDevice()
        if ret != fg.FCE_NOERROR:
            raise AVTCameraError(ret)
        
        def frameMonitor():
            for cnt in xrange(frameCnt):
                if self.__stopFlag:
                    break
                frame = fg.FGFRAME()
                timeout = 1000
                ret = self.__cam.GetFrame(frame, timeout)
                if ret == fg.FCE_NOERROR:
                    try:
                        w = rc[2]
                        h = rc[3]
                        flagInvalid = frame.Flags & fg.FGF_INVALID
                        flagLast = frame.Flags & fg.FGF_LAST
                        flagDMAHalted = frame.Flags & fg.FGF_DMAHALTED
                        flagForcePost = frame.Flags & fg.FGF_FORCEPOST
                        tsh = frame.RxTime.High
                        tsl = frame.RxTime.Low
                        if self.deinterlace is None:
                            # No deinterlace
                            rawData = fg.cdata(frame.pData, frame.Length)
                        else:
                            rawData = fg.Deinterlace(frame, self.deinterlace, w, h, w, w * h)
                        self.__imageCache.put_nowait({'RawData':rawData, 'ROI':rc,
                                'FrameId':frame.Id, 'Invalid':bool(flagInvalid), 'Last':bool(flagLast),
                                'DMAHalted':bool(flagDMAHalted), 'ForcePost':bool(flagForcePost),
                                'TimeStamp':tsh * 2 ** 32 + tsl, 'BufferLength':frame.Length,
                                'Depth':8})
                    except Queue.Full:
#                        logging.debug('Queue full')
                        pass
                    finally:
                        ret = self.__cam.PutFrame(frame)
                        if ret != fg.FCE_NOERROR:
                            raise AVTCameraError(ret)
                else:
                    raise AVTCameraError(ret)
        
        self.__stopFlag = False
        self.__thread = threading.Thread(group=None, target=frameMonitor, name='FrameMonitor')
        self.__thread.start()
    
    def getImage(self, timeout=1):
        return self.__imageCache.get(True, timeout)
     
    def stopDevice(self):
        # Check the stop flag and wait for the monitor to exit naturally. Then we'll stop the 
        # device.
        self.__stopFlag = True
        self.__thread.join()
        ret = self.__cam.StopDevice()
        if ret != fg.FCE_NOERROR:
            raise AVTCameraError(ret)    
            
class SimCamera(object):
    parameters = {
        'FGP_IMAGEFORMAT':0,
        'FGP_ENUMIMAGEFORMAT':1,
        'FGP_BRIGHTNESS':2,
        'FGP_AUTOEXPOSURE':3,
        'FGP_SHARPNESS':4,
        'FGP_WHITEBALCB':5,
        'FGP_WHITEBALCR':6,
        'FGP_HUE':7,
        'FGP_SATURATION':8,
        'FGP_GAMMA':9,
        'FGP_SHUTTER':10,
        'FGP_GAIN':11,
        'FGP_IRIS':12,
        'FGP_FOCUS':13,
        'FGP_TEMPERATURE':14,
        'FGP_TRIGGER':15,
        'FGP_TRIGGERDLY':16,
        'FGP_WHITESHD':17,
        'FGP_FRAMERATE':18,
        'FGP_ZOOM':19,
        'FGP_PAN':20,
        'FGP_TILT':21,
        'FGP_OPTICALFILTER':22,
        'FGP_CAPTURESIZE':23,
        'FGP_CAPTUREQUALITY':24,
        'FGP_PHYSPEED':25,
        'FGP_XSIZE':26,
        'FGP_YSIZE':27,
        'FGP_XPOSITION':28,
        'FGP_YPOSITION':29,
        'FGP_PACKETSIZE':30,
        'FGP_DMAMODE':31,
        'FGP_BURSTCOUNT':32,
        'FGP_FRAMEBUFFERCOUNT':33,
        'FGP_USEIRMFORBW':34,
        'FGP_ADJUSTPARAMETERS':35,
        'FGP_STARTIMMEDIATELY':36,
        'FGP_FRAMEMEMORYSIZE':37,
        'FGP_COLORFORMAT':38,
        'FGP_IRMFREEBW':39,
        'FGP_DO_FASTTRIGGER':40,
        'FGP_DO_BUSTRIGGER':41,
        'FGP_RESIZE':42,
        'FGP_USEIRMFORCHN':43,
        'FGP_CAMACCEPTDELAY':44,
        'FGP_ISOCHANNEL':45,
        'FGP_CYCLETIME':46,
        'FGP_DORESET':47,
        'FGP_DMAFLAGS':48,
        'FGP_R0C':49,
        'FGP_BUSADDRESS':50,
        'FGP_CMDTIMEOUT':51,
        'FGP_CARD':52,
        'FGP_LICENSEINFO':53,
        'FGP_PACKETCOUNT':54,
        'FGP_DO_MULTIBUSTRIGGER':55,
        'FGP_CARDRESET':56,
        }
    
    @staticmethod
    def initLibrary():
        pass
        
    @staticmethod
    def releaseLibrary():
        pass
    
    @classmethod
    def getNodeList(cls):
        '''
        Get available node list.
        '''
        return (fg.FGNODEINFO(),)
    
    @classmethod
    def makeCameraInstance(cls, node):
        return cls(node)
    
    def __init__(self, node):
        '''
        Constructor. node is returned by getNodeList
        '''
        self.__node = node
        self.isConnected = False
        self.__thread = None
        self.deinterlace = None
        self.__imageCache = Queue.Queue(64)
        self.__stopFlag = False
        self.__imageMode = 0
        frame = fg.FGFRAME()
        frame.RxTime.Low = 5
        logging.debug(frame.RxTime.Low)
        logging.debug(fg.test(frame, 31) / 1e7)
        logging.debug(frame.RxTime.Low)

    def connect(self):
        self.isConnected = True
        self.__shutter = {'Value':2000, 'Min':1, 'Max':4095}
        self.__gain = {'Value':100, 'Min':0, 'Max':680}
        self.__brightness = {'Value':50, 'Min':1, 'Max':100}
        self.__burstCount = {'Value':1, 'Min':1, 'Max':65535}
        self.__roi = (0, 0, 128, 96)
        # (x, y, I, r)
        self.__particles = ((30, 25, 200, 6.5), (91, 75, 140, 7.4))
        self.__genGrids()
        
    def __genGrids(self):
        self.__xGrid = reduce(lambda x, y:numpy.concatenate((x, y)),
                              map(lambda i : numpy.linspace(0, self.__roi[2] - 1, self.__roi[2]), xrange(self.__roi[3])))
        self.__xGrid.shape = self.__roi[3], -1
        self.__xGrid += self.__roi[0]
        self.__yGrid = reduce(lambda x, y:numpy.concatenate((x, y)),
                              map(lambda i : numpy.linspace(i, i, self.__roi[2]), xrange(self.__roi[3])))
        self.__yGrid.shape = self.__roi[3], -1
        self.__yGrid += self.__roi[1]
        
    def disconnect(self):
        self.isConnected = False
    
    @property
    def brightness(self):
        return self.__brightness
    @brightness.setter
    def brightness(self, value):
        self.__brightness['Value'] = value
    
    @property
    def shutter(self):
        return self.__shutter
    @shutter.setter
    def shutter(self, value):
        self.__shutter['Value'] = value
        
    @property
    def gain(self):
        return self.__gain
    @gain.setter
    def gain(self, value):
        self.__gain['Value'] = value
        
    @property
    def deviceName(self):
        return 'SimCamera'
    
    def openCapture(self):
        pass
        
    def closeCapture(self):
        pass
        
    @property
    def burstCount(self):
        return self.__burstCount
    @burstCount.setter
    def burstCount(self, value):
        self.__burstCount['Value'] = value
        
    @property
    def roi(self):
        return self.__roi
    @roi.setter
    def roi(self, value):
        self.__roi = value
        
    @property
    def width(self):
        return {'Value':self.__roi[2], 'Min':2, 'Max':128}
    @property
    def height(self):
        return {'Value':self.__roi[3], 'Min':2, 'Max':128}
    
    def __genImage(self):
        sz = self.__roi[2] * self.__roi[3]
        if self.__xGrid.size != sz or self.__yGrid.size != sz:
            self.__genGrids()
        
        def func(particle):
            x0, y0, I0, r0 = particle
            tmp = (x0, y0) + numpy.random.randn(1, 2) * 0.1
            x0, y0 = tmp[0]
            I0 = (I0 + numpy.random.randn(1, 1) * 5)[0, 0] 
            I0 *= self.shutter['Value'] / 2000.0 * self.gain['Value'] / 100.0
            return I0 * numpy.exp(-((self.__xGrid - x0) ** 2 + (self.__yGrid - y0) ** 2) / (r0 ** 2))
            
        dataMat = numpy.array(reduce(numpy.add, map(func, self.__particles)) + \
                              numpy.random.randint(0, 15, size=(self.__roi[3], self.__roi[2])), dtype=numpy.uint8)
        return dataMat.tostring()

    def snapshot(self, timeout=1):
        self.burstCount = 1
        self.openCapture()
        self.startDevice()
        data = self.getImage(timeout)
        self.stopDevice()
        self.closeCapture()
#        map(lambda f : f(data), self.__callbacks)
        return data
    
    @property
    def isAcquiring(self):
        return self.__thread.isAlive() if self.__thread is not None else False
    
    def setImageMode(self, mode):
        self.__imageMode = mode
    @property
    def imageMode(self):
        return self.__imageMode
    
    def startDevice(self, count=None):
        self.__imageCache = Queue.Queue(64)
        if count is None:
            frameCnt = self.burstCount['Value']
        else:
            self.burstCount = count
            frameCnt = count
            
        rc = self.__roi
        
        def frameMonitor():
            for cnt in xrange(frameCnt):
                if self.__stopFlag:
                    break
                time.sleep(self.__shutter['Value'] / 4e4)
                rawData = self.__genImage()
                try:
                    w = rc[2]
                    h = rc[3]
                    self.__imageCache.put_nowait({'RawData':rawData, 'ROI':rc,
                            'FrameId':cnt, 'Invalid':False, 'Last':True,
                            'DMAHalted':False, 'ForcePost':False,
                            'TimeStamp':time.clock(), 'BufferLength':w * h,
                            'Depth':8})
                except Queue.Full:
                    pass
        
        self.__stopFlag = False
        self.__thread = threading.Thread(group=None, target=frameMonitor, name='FrameMonitor')
        self.__thread.start()
    
    def getImage(self, timeout=1):
        return self.__imageCache.get(True, timeout)
     
    def stopDevice(self):
        # Check the stop flag and wait for the monitor to exit naturally. Then we'll stop the 
        # device.
        self.__stopFlag = True
        self.__thread.join()


def main(argv):
    AVTCamera.initLibrary()
    node = AVTCamera.getNodeList()[0]
    cam = AVTCamera.makeCameraInstance(node)
    cam.connect()
    logging.info(cam.deviceName)
    
    cam.shutter = 2000
    cam.gain = 100
    cam.brightness = 50
    data = cam.snapshot()
    import Image
    im = Image.fromstring('L', (cam.roi[2], cam.roi[3]), data['RawData'])
    im.save('Test.bmp')

    cam.disconnect()
    
    AVTCamera.releaseLibrary()
#    im.show()
    
if __name__ == '__main__':
    main(sys.argv)
