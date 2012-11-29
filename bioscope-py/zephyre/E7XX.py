'''
Created on Mar 19, 2012

@author: Zephyre
'''
import E7XX_swig as es
import time
import logging
import socket
from struct import * 
from hashlib import md5

class PiezoStageError(Exception):
    '''
    General piezo stage error
    '''
    def __init__(self, errId= -1, errMsg='', cause=None):
        self.errId, self.errMsg, self.cause = errId, errMsg, cause
        
    def __str__(self):
        return 'Error id: %d, message: %s, cause: %s' % (self.errId, self.errMsg, self.cause)
    
class PiezoStage(object):
    '''
    E761 piezo stage.
    '''

    def __init__(self, boardId=1):
        '''
        Constructor
        '''
        self.__boardId, self.__devId = boardId, None
        
        # Array helpers:
        self.__intArrayFuncs = {'Init':es.new_intArray, 'Getter':es.intArray_getitem, 'Setter':es.intArray_setitem}
        self.__doubleArrayFuncs = {'Init':es.new_doubleArray, 'Getter':es.doubleArray_getitem, 'Setter':es.doubleArray_setitem}
        
    def connect(self, boardId=None, reboot=False):
        if boardId is not None:
            self.__boardId = boardId
        if reboot:
            ret = es.E7XX_ConnectPciBoardAndReboot(self.__boardId)
        else:
            ret = es.E7XX_ConnectPciBoard(self.__boardId)
        if ret < 0:
            err = es.E7XX_TranslateError(ret, 512)
            raise PiezoStageError(ret, err[1])
        self.__devId = ret
        # Get the axis names
        ret = es.E7XX_qSAI_ALL(self.__devId, 512)
        if ret[0] == 0:
            self.__raiseLastError()
        self.__axisNames = ret[1]
        
    def reboot(self):
        ret = es.E7XX_RBT(self.__devId)
        if ret == 0:
            self.__raiseLastError()
        
    @property
    def axisNames(self):
        return self.__axisNames
    @axisNames.setter
    def axisNames(self, value):
        if len(value) != len(self.__axisNames):
            raise PiezoStageError(errMsg='Invalid names.')
        self.configStatuses = (True,) * len(self.__axisNames)
        ret = es.E7XX_SAI(self.__devId, self.__axisNames, value)
        if ret == 0:
            self.__raiseLastError()
        ret, self.__axisNames = es.E7XX_qSAI_ALL(self.__devId, 512)
        if ret == 0:
            self.__raiseLastError()
    
    @property
    def numTotalAxes(self):
        '''
        Get the total number of axes
        '''
        return len(self.__axisNames)
    
    def getHome(self):
        '''
        Get the home position => (2,5,2.8)
        '''
        return self.__dataOutput(self.__doubleArrayFuncs, es.E7XX_qDFH)
    
    def setHome(self, axis=None):
        '''
        Set current position as the home position.
        '''
        self.__control(es.E7XX_DFH, axis)
        
    def goHome(self, axis=None):
        '''
        Go to the home position
        Usage: self.goHome()
               self.goHome((2,3))
        '''
        self.__control(es.E7XX_GOH, axis)
                
    @property
    def position(self):
        '''
        Get the position. => (1.2, 2.4, 8.1)
        '''
        return self.__dataOutput(self.__doubleArrayFuncs, es.E7XX_qPOS)
    @position.setter
    def position(self, value):
        '''
        Set the position.
        Usage: self.position = (2,3,4)
               self.position = (10, 2)   # for the 1st and 2nd axes
               self.position = {1:2, 3:8.7}
        '''
        self.__dataInput(self.__doubleArrayFuncs, es.E7XX_MOV, value)
        
    @property
    def configStatuses(self):
        '''
        Get configuration status: ID-STAGE/NOSTAGE
        '''
        ret, statusStr = es.E7XX_qCST(self.__devId, None, 512)
        if ret == 0:
            self.__raiseLastError()
        cfgs = statusStr.split('\n')
        
        def isConfig(desc):
            return desc.find('ID-STAGE') != -1
        return map(isConfig, cfgs[:len(self.__axisNames)])
    @configStatuses.setter
    def configStatuses(self, data):
        try:
            # dictionary usage
            indice = data.keys()
            numAxes = len(indice)
            axisNames = ''.join(self.__axisNames[i - 1] for i in indice)
            
            names = map(lambda i: '%s\n' % ('ID-STAGE' if data[indice[i]] else 'NOSTAGE'),
                xrange(numAxes))
            ret = es.E7XX_CST(self.__devId, axisNames, ''.join(names))
            if ret == 0:
                self.__raiseLastError()
        except AttributeError:
            # list usage
            numAxes = len(data)
            axisNames = ''.join(self.__axisNames[i] for i in xrange(numAxes))
            names = map(lambda i:'%s\n' % ('ID-STAGE' if data[i] else 'NOSTAGE'),
                      xrange(numAxes))
            ret = es.E7XX_CST(self.__devId, axisNames, ''.join(names))
            if ret == 0:
                self.__raiseLastError()
                
    def __dataOutput(self, arrayFunc, stageFunc, axis=None):
        '''
        General call form: BOOL ret = stageFuncQ(id, arrayFunc, stageFunc, axisIndice) => (length, array)
        For querying functions
        arrayFunc: ('Init':init, 'Getter':getter)
        '''
        numAxes = len(self.__axisNames if axis is None else axis)
        axisNames = ''.join(self.__axisNames[i - 1]\
                            for i in (xrange(1, len(self.__axisNames) + 1) if axis is None else axis))
        arrayInit = arrayFunc['Init']
        arrayGetter = arrayFunc['Getter']
        valArray = arrayInit(numAxes)
        ret = stageFunc(self.__devId, axisNames, valArray)
        if ret == 0:
            self.__raiseLastError()
        return tuple(arrayGetter(valArray, i) for i in xrange(numAxes))
    
    def __dataInput(self, arrayFunc, stageFunc, data):
        '''        
        For setting functions
        Usage: __dataInput(arrayFunc, stageFunc, {1:2,2:3})
               __dataInput(arrayFunc, stageFunc, (3,5))
        arrayFunc: ('Init':init, 'Setter':setter) 
        '''
        try:
            # dictionary usage
            indice = data.keys()
            numAxes = len(indice)
            axisNames = ''.join(self.__axisNames[i - 1] for i in indice)
            arrayInit = arrayFunc['Init']
            arraySetter = arrayFunc['Setter']
            valArray = arrayInit(numAxes)
            
            map(lambda i : arraySetter(valArray, i, data[indice[i]]),
                xrange(numAxes))
            ret = stageFunc(self.__devId, axisNames, valArray)
            if ret == 0:
                self.__raiseLastError()
        except AttributeError:
            # list usage
            numAxes = len(data)
            axisNames = ''.join(self.__axisNames[i] for i in xrange(numAxes))
            arrayInit = arrayFunc['Init']
            arraySetter = arrayFunc['Setter']
            valArray = arrayInit(numAxes)
            map(lambda i : arraySetter(valArray, i, data[i]), xrange(numAxes))
            ret = stageFunc(self.__devId, axisNames, valArray)
            if ret == 0:
                self.__raiseLastError()
                
    def __control(self, stageFunc, axis):
        '''
        General form for controlling functions. axis: (1,2,3) or None
        '''
        axisNames = ''.join(self.__axisNames[i - 1] for i in \
                            (axis if axis is not None else xrange(1, len(self.__axisNames) + 1)))
        ret = stageFunc(self.__devId, axisNames)
        if ret == 0:
            self.__raiseLastError()
            
    def waitForAxis(self, axis=None):
        '''
        Wait for the specified axis to stop
        '''
        getStatus = lambda : tuple((self.isOnTarget)[i - 1] for i in \
                       (axis if axis is not None else xrange(self.numTotalAxes)))
        s = getStatus()
        while not reduce(lambda x, y: x and y, s):
            time.sleep(0.001)
            s = getStatus()
        
    @property
    def svoStatus(self):
        '''
        Get the servo status. => (True, False, False)
        '''
        valArray = self.__dataOutput(self.__intArrayFuncs, es.E7XX_qSVO)
        return map(lambda i : i != 0, valArray)
    @svoStatus.setter
    def svoStatus(self, value):
        '''
        Set the servo status
        '''
        self.__dataInput(self.__intArrayFuncs, es.E7XX_SVO, value)
        
    @property
    def isOnTarget(self):
        '''
        Check if the stage is on targeted positions
        '''
        valArray = self.__dataOutput(self.__intArrayFuncs, es.E7XX_qONT)
        return tuple(v != 0 for v in valArray)
    
    @property
    def openLoopValue(self):
        '''
        Get the open-loop values
        '''
        return self.__dataOutput(self.__doubleArrayFuncs, es.E7XX_qSVA)
    @openLoopValue.setter
    def openLoopValue(self, value):
        self.__dataInput(self.__doubleArrayFuncs, es.E7XX_SVA, value)

        
    def disconnect(self):
        if self.__devId is not None:
            es.E7XX_CloseConnection(self.__devId)
            self.__devId = None
        
    @property
    def isConnected(self):
        return (self.__devId is not None) and (es.E7XX_IsConnected(self.__devId) != 0)
    
    def __raiseLastError(self):
        errId = es.E7XX_GetError(self.__devId)
        errMsg = es.E7XX_TranslateError(errId, 512)
        raise PiezoStageError(errId, errMsg[1])
    
    def halt(self, axes=None):
        self.__control(es.E7XX_HLT, axes)
            
    @property
    def isMoving(self):
        valArray = self.__dataOutput(self.__intArrayFuncs, es.E7XX_IsMoving)
        return tuple(v != 0 for v in valArray)

    def moveRelative(self, delta):
        '''
        Move relatively.
        Usage: self.movRelative((2,3))
               self.movRelative({1:2,2:-1})
        '''
        self.__dataInput(self.__doubleArrayFuncs, es.E7XX_MVR, delta)
        
    @property
    def upperLimit(self):
        return self.__dataOutput(self.__doubleArrayFuncs, es.E7XX_qPLM)
    @upperLimit.setter
    def upperLimit(self, value):
        self.__dataInput(self.__doubleArrayFuncs, es.E7XX_PLM, value)
    @property
    def lowerLimit(self):
        return self.__dataOutput(self.__doubleArrayFuncs, es.E7XX_qNLM)
    @lowerLimit.setter
    def lowerLimit(self, value):
        self.__dataInput(self.__doubleArrayFuncs, es.E7XX_NLM, value)
        
    @property
    def travelRanges(self):
        '''
        Get the travel ranges of all axes
        '''
        low = self.__dataOutput(self.__doubleArrayFuncs, es.E7XX_qTMN)
        high = self.__dataOutput(self.__doubleArrayFuncs, es.E7XX_qTMX)
        return dict(zip(xrange(len(self.__axisNames)), zip(low, high)))
        
    @property
    def velControl(self):
        '''
        Velocity control
        '''
        valArray = self.__dataOutput(self.__intArrayFuncs, es.E7XX_qVCO)
        return tuple(v != 0 for v in valArray)
    @velControl.setter
    def velControl(self, value):
        self.__dataInput(self.__intArrayFuncs, es.E7XX_VCO, value)
        
    @property
    def velocity(self):
        '''
        Velocity settings
        '''
        return self.__dataOutput(self.__doubleArrayFuncs, es.E7XX_qVEL)
    @velocity.setter
    def velocity(self, value):
        self.__dataInput(self.__doubleArrayFuncs, es.E7XX_VEL, value)
        
    @property
    def firmwareVer(self):
        ret, desc = es.E7XX_qVER(self.__devId, 512)
        if ret == 0:
            self.__raiseLastError()
        return desc
    
    @property
    def numPiezoChannels(self):
        ret, num = es.E7XX_qTPC(self.__devId)
        if ret == 0:
            self.__raiseLastError()
        return num
    
    @property
    def numSensorChannels(self):
        ret, num = es.E7XX_qTSC(self.__devId)
        if ret == 0:
            self.__raiseLastError()
        return num
    
    @property
    def normalizedSensorValues(self):
        return self.__dataOutput(self.__doubleArrayFuncs, es.E7XX_qTNS)
        
    @property
    def sensorPositions(self):
        return self.__dataOutput(self.__doubleArrayFuncs, es.E7XX_qTSP)
    
    @property
    def voltageRange(self):
        '''
        Get the voltage ranges of all piezo channels
        '''
        low = self.__dataOutput(self.__doubleArrayFuncs, es.E7XX_qVMI)
        high = self.__dataOutput(self.__doubleArrayFuncs, es.E7XX_qVMA)
        return dict(zip(xrange(len(self.__axisNames)), zip(low, high)))
    
    @property
    def voltage(self):
        return self.__dataOutput(self.__doubleArrayFuncs, es.E7XX_VOL)
    @voltage.setter
    def voltage(self, value):
        self.__dataInput(self.__doubleArrayFuncs, es.E7XX_VOL, value) 
        
class PiezoStageAdapter(object):
    '''
    E761 piezo stage Adapter
    '''
    
    START_FLAG = 0xFFFE
    qPOS, MOV, MVR, SVO, qSVO, CST, qCST, SVA, qSVA, PLM, qPLM, NLM, qNLM, DFH, qDFH, GOH, qONT, HLT = range(18)
    
    def __init__(self):
        self.__isConnected = False
        self.__typeSize = {'?':1, 'c':1, 'h':2, 'H':2, 'i':4, 'I':4, 'f':4, 'd':8}
        self.address = '127.0.0.1'
        self.port = 50501

    def connect(self, boardId=None, reboot=False):
        if self.__isConnected:
            return
        
        try:
            self.__socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.__socket.connect((self.address, self.port))
            self.__isConnected = True
        except socket.error as e:
            raise PiezoStageError(cause=e)
        
    @property
    def numTotalAxes(self):
        '''
        Get the total number of axes
        '''
        return len(self.__axisNames)
    
    def getHome(self):
        '''
        Get the home position => (2,5,2.8)
        '''
        if not self.__isConnected:
            raise PiezoStageError(-1, 'Not connected.')
        
        return self.__sendData(PiezoStageAdapter.qDFH, ())
    
    def setHome(self, axis=None):
        '''
        Set current position as the home position.
        '''
        if not self.__isConnected:
            raise PiezoStageError(-1, 'Not connected.')
        self.__sendData(PiezoStageError.DFH, self.__controlParams(axis))
        
    def goHome(self, axis=None):
        '''
        Go to the home position
        Usage: self.goHome()
               self.goHome((2,3))
        '''
        if not self.__isConnected:
            raise PiezoStageError(-1, 'Not connected.')
        self.__sendData(PiezoStageError.GOH, self.__controlParams(axis))
                
    @property
    def position(self):
        '''
        Get the position. => (1.2, 2.4, 8.1)
        '''
        if not self.__isConnected:
            raise PiezoStageError(-1, 'Not connected.')
        
        return self.__sendData(PiezoStageAdapter.qPOS, ())

    @position.setter
    def position(self, value):
        '''
        Set the position.
        Usage: self.position = (2,3,4)
               self.position = (10, 2)   # for the 1st and 2nd axes
               self.position = {1:2, 3:8.7}
        '''
        if not self.__isConnected:
            raise PiezoStageError(-1, 'Not connected.')
        self.__sendData(PiezoStageAdapter.MOV, self.__paramsBuilder(value, 'd'))
        
    @property
    def configStatuses(self):
        '''
        Get configuration status: ID-STAGE/NOSTAGE
        return: (True, False, False)
        '''
        if not self.__isConnected:
            raise PiezoStageError(-1, 'Not connected.')
        
        return self.__sendData(PiezoStageAdapter.qCST, ())
    
    @configStatuses.setter
    def configStatuses(self, data):
        '''
        Set the configuration status
        '''
        if not self.__isConnected:
            raise PiezoStageError(-1, 'Not connected.')
        
        self.__sendData(PiezoStageAdapter.CST, self.__paramsBuilder(data, '?'))
        
    def __controlParams(self, value):
        '''
        value: (1,2,3) or None
        output: params tuple
        '''
        if value is None:
            value = (1, 2, 3)
        params = []
        for v in value:
            params.append(tuple('I', self.__typeSize('I'), v - 1))
        return tuple(params)
            
    def __paramsBuilder(self, data, ptype):
        '''
        Input data: dict usage: {1:True, 3:False}
        list usage: (True, False, False)
        ptype: 'H', 'h', 'f', 'd', etc.
        
        Output: this function will build the full parameter tuple.
        paras: ((ptype('H','c',etc. See struct.pack), plen(16-bit integer), pdata(string), ...)
        '''
        if not isinstance(data, dict):
            # list usage
            # Build the dictionary
            val = {}
            for i in xrange(len(data)):
                val[i + 1] = data[i]
            data = val
        # dictionary usage
        params = []
        for k in data.keys():
            params.append(('I', self.__typeSize['I'], k - 1))
            params.append((ptype, self.__typeSize[ptype], data[k]))
        return tuple(params)
        
    def __attachMD5(self, data):
        m = md5(data)
        return data + m.digest()
    
    def __checkMD5(self, data):
        if len(data) < 16:
            return False
        l = len(data)
        frame, md5Str = data[:l - 16], data[l - 16:]
        m = md5(frame)
        return m.digest() == md5Str
    
    def __recvData(self):
        '''
        Receive data from the socket.
        return: (cmd, (para1, para2, ...))
        '''
        try:
            data = self.__socket.recv(4)
        except socket.error as e:
            raise PiezoStageError(cause=e)
        
        startFlag, frameLen = unpack('>HH', data)
        if startFlag != PiezoStageAdapter.START_FLAG:
            raise PiezoStageError(-1, 'Connection error.')
        # Receive the remaining
        data = data + self.__socket.recv(frameLen - 4)
        if not self.__checkMD5(data):
            raise PiezoStageError(-1, 'Connection error.')
        # Unpack
        # 0xff 0xfe [length] [cmd] [numPara] [p1] [p2] ... [pn] [md5]
        cmd, numPara = tuple(ord(c) for c in unpack('>cc', data[4:6]))
        paras = self.__extractParameters(data[6:], numPara)
        if not paras[0]:
            # Some error occured
            raise PiezoStageError(errMsg=paras[1])
        # Returning the remaining values
        return (cmd, paras[1:])
    
    def __sendData(self, cmd, paras):
        '''
        Send data
        cmd: command code(integer)
        paras: ((ptype('H','c',etc. See struct.pack), plen(16-bit integer), pdata(string), ...)
        '''
        # 0xff 0xfe [length] [cmd] [numpara] [paras] [md5]
        frameLen = 6 + sum(tuple(4 + p[1] for p in paras)) + 16
        data = pack('>HHcc', PiezoStageAdapter.START_FLAG, frameLen, chr(cmd), chr(len(paras)))
        # Build the para string
        for p in paras:
            data += pack('>ccH' + p[0], chr(0), p[0], p[1], p[2])
            
        data = self.__attachMD5(data)
        try:
            self.__socket.sendall(data)
        except socket.error as e:
            raise PiezoStageError(cause=e)
        
        cmdRet, params = self.__recvData()
        if cmdRet != cmd:
            raise PiezoStageError()
        return params
        
    def __extractParameters(self, data, num):
        '''
        Extract parameters from the data string
        data: 0x00 [para type] [para len] [para data]...
        return: (para1, para2, ...)
        '''
        offset = 0
        para = [None, ] * num
        for i in xrange(num):
            # hdr: [para type] [para len]
            ptype, plen = unpack('>cH', data[offset + 1:offset + 4])
            if ptype == 's':
                # string
                pdata = (data[offset + 4:offset + 4 + plen],)                
            else:
                pdata = unpack('>' + ptype, data[offset + 4:offset + 4 + plen])
            para[i] = pdata[0]
            offset += 4 + plen
        return tuple(para)
            
    @property
    def svoStatus(self):
        '''
        Get the servo status. => (True, False, False)
        '''
        if not self.__isConnected:
            raise PiezoStageError(-1, 'Not connected.')
        
        return self.__sendData(PiezoStageAdapter.qSVO, ())
    
    @svoStatus.setter
    def svoStatus(self, value):
        '''
        Set the servo status
        '''
        if not self.__isConnected:
            raise PiezoStageError(-1, 'Not connected.')
        self.__sendData(PiezoStageAdapter.SVO, self.__paramsBuilder(value, '?'))
        
    @property
    def isOnTarget(self):
        '''
        Check if the stage is on targeted positions
        '''
        if not self.__isConnected:
            raise PiezoStageError(-1, 'Not connected.')
        
        return self.__sendData(PiezoStageAdapter.qONT, ())
    
    @property
    def openLoopValue(self):
        '''
        Get the open loop values.
        '''
        if not self.__isConnected:
            raise PiezoStageError(-1, 'Not connected.')
        
        return self.__sendData(PiezoStageAdapter.qSVA, ())
    
    @openLoopValue.setter
    def openLoopValue(self, value):
        '''
        Set the open loop values.
        '''
        if not self.__isConnected:
            raise PiezoStageError(-1, 'Not connected.')
        
        self.__sendData(PiezoStageAdapter.SVA, self.__paramsBuilder(value, 'd'))
        
    def disconnect(self):
        if not self.__isConnected:
            return
        self.__socket.shutdown(socket.SHUT_RDWR)
        self.__socket.close()
        
    @property
    def isConnected(self):
        return self.__isConnected
    
    def halt(self, axes=None):
        if not self.__isConnected:
            raise PiezoStageError(-1, 'Not connected.')
        self.__sendData(PiezoStageError.HLT, self.__controlParams(axes))
            
    @property
    def isMoving(self):
        return (True,) * 3

    def moveRelative(self, delta):
        '''
        Move relatively.
        Usage: self.movRelative((2,3))
               self.movRelative({1:2,2:-1})
        '''
        if not self.__isConnected:
            raise PiezoStageError(-1, 'Not connected.')
        
        self.__sendData(PiezoStageAdapter.MVR, self.__paramsBuilder(delta, 'd'))

    @property
    def upperLimit(self):
        '''
        Get the upper limits => (100.0, 100.0, 10.0)
        '''
        if not self.__isConnected:
            raise PiezoStageError(-1, 'Not connected.')
        
        return self.__sendData(PiezoStageAdapter.qPLM, ())
    @upperLimit.setter
    def upperLimit(self, value):
        '''
        Set the upper limits.
        '''
        if not self.__isConnected:
            raise PiezoStageError(-1, 'Not connected.')
        
        self.__sendData(PiezoStageAdapter.PLM, self.__paramsBuilder(value, 'd'))
        
    @property
    def lowerLimit(self):
        '''
        Get the lower limits => (0.0, 0.0, 0.0)
        '''
        if not self.__isConnected:
            raise PiezoStageError(-1, 'Not connected.')
        
        return self.__sendData(PiezoStageAdapter.qNLM, ())
    @lowerLimit.setter
    def lowerLimit(self, value):
        '''
        Set the lower limits.
        '''
        if not self.__isConnected:
            raise PiezoStageError(-1, 'Not connected.')
        
        self.__sendData(PiezoStageAdapter.NLM, self.__paramsBuilder(value, 'd'))
        
#    @property
#    def travelRanges(self):
#        '''
#        Get the travel ranges of all axes
#        '''
#        low = self.__dataOutput(self.__doubleArrayFuncs, es.E7XX_qTMN)
#        high = self.__dataOutput(self.__doubleArrayFuncs, es.E7XX_qTMX)
#        return dict(zip(xrange(len(self.__axisNames)), zip(low, high)))
        
#    @property
#    def velControl(self):
#        '''
#        Velocity control
#        '''
#        valArray = self.__dataOutput(self.__intArrayFuncs, es.E7XX_qVCO)
#        return tuple(v != 0 for v in valArray)
#    @velControl.setter
#    def velControl(self, value):
#        self.__dataInput(self.__intArrayFuncs, es.E7XX_VCO, value)
#        
#    @property
#    def velocity(self):
#        '''
#        Velocity settings
#        '''
#        return self.__dataOutput(self.__doubleArrayFuncs, es.E7XX_qVEL)
#    @velocity.setter
#    def velocity(self, value):
#        self.__dataInput(self.__doubleArrayFuncs, es.E7XX_VEL, value)
#        
#    @property
#    def firmwareVer(self):
#        ret, desc = es.E7XX_qVER(self.__devId, 512)
#        if ret == 0:
#            self.__raiseLastError()
#        return desc
#    
#    @property
#    def numPiezoChannels(self):
#        ret, num = es.E7XX_qTPC(self.__devId)
#        if ret == 0:
#            self.__raiseLastError()
#        return num
#    
#    @property
#    def numSensorChannels(self):
#        ret, num = es.E7XX_qTSC(self.__devId)
#        if ret == 0:
#            self.__raiseLastError()
#        return num
#    
#    @property
#    def normalizedSensorValues(self):
#        return self.__dataOutput(self.__doubleArrayFuncs, es.E7XX_qTNS)
#        
#    @property
#    def sensorPositions(self):
#        return self.__dataOutput(self.__doubleArrayFuncs, es.E7XX_qTSP)
#    
#    @property
#    def voltageRange(self):
#        '''
#        Get the voltage ranges of all piezo channels
#        '''
#        low = self.__dataOutput(self.__doubleArrayFuncs, es.E7XX_qVMI)
#        high = self.__dataOutput(self.__doubleArrayFuncs, es.E7XX_qVMA)
#        return dict(zip(xrange(len(self.__axisNames)), zip(low, high)))
#    
#    @property
#    def voltage(self):
#        return self.__dataOutput(self.__doubleArrayFuncs, es.E7XX_VOL)
#    @voltage.setter
#    def voltage(self, value):
#        self.__dataInput(self.__doubleArrayFuncs, es.E7XX_VOL, value)                       

#if __name__ == '__main__':
#    
#    def createArr(data, type='double'):
#        num = len(data)
#        func1, func2 = (es.new_doubleArray, es.doubleArray_setitem) if type == 'double' else (es.new_intArray, es.intArray_setitem) 
#        array = func1(num)
#        map(lambda i:func2(array, i, data[i]), xrange(num))
#        return array
#    
#    def getArr(array, num, type='double'):
#        func = es.doubleArray_getitem if type == 'double' else es.intArray_getitem
#        return tuple(func(array, i) for i in xrange(num))
#    
#    devId = es.E7XX_ConnectPciBoard(1)
#    assert(devId >= 0)
#    
#    logging.info('qTSC %d' % es.E7XX_qTSC(devId)[1])
#    logging.info('qTPC %d' % es.E7XX_qTPC(devId)[1])
#    
#    data = createArr((99,) * 10, type='double')
#    assert(es.E7XX_qTNS(devId, '', data) != 0)
#    print(getArr(data, 10, type='double'))
#    
#    data = createArr((99,) * 10, type='double')
#    assert(es.E7XX_qTSP(devId, '', data) != 0)
#    print(getArr(data, 10, type='double'))
#    
#    data = createArr((99,) * 10, type='double')
#    assert(es.E7XX_qVMA(devId, '', data) != 0)
#    print(getArr(data, 10, type='double'))
#    
#    data = createArr((99,) * 10, type='double')
#    assert(es.E7XX_qVMI(devId, '', data) != 0)
#    print(getArr(data, 10, type='double'))
#    
#    data = createArr((99,) * 10, type='double')
#    assert(es.E7XX_qVOL(devId, '', data) != 0)
#    print(getArr(data, 10, type='double'))
#    
#    es.E7XX_CloseConnection(devId)


if __name__ == '__main__':
    pi = PiezoStageAdapter()
    pi.address = '127.0.0.1'
    pi.port = 50501
    pi.connect()
    pi.svoStatus = (True,) * 3
    
    print(pi.position)
    pi.position = (2.5, 5.5)
    pi.position = {3:4.8, 2:2.2}
    pi.position = {1:20, 2:40, 3:7.2}
    print(pi.position)
    
    print(pi.svoStatus)
    pi.svoStatus = (True, False)
    pi.svoStatus = {3:False, 1:True}
    pi.svoStatus = (False,) * 3
    print(pi.svoStatus)
    
    ov = pi.openLoopValue
    print(ov)
    ov = tuple(v + 1 for v in ov)
    pi.openLoopValue = ov
    print(pi.openLoopValue)
    
    pi.svoStatus = (True,) * 3
    
    pi.disconnect()
