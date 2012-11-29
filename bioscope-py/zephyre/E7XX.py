'''
Created on Mar 19, 2012

@author: Zephyre
'''
import E7XX_swig as es
import time
import logging

class PiezoStageError(Exception):
    '''
    General piezo stage error
    '''
    def __init__(self, errId= -1, errMsg=''):
        self.errId, self.errMsg = errId, errMsg
        
    def __str__(self):
        return 'Error id: %d, message: %s' % (self.errId, self.errMsg)
    
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

if __name__ == '__main__':
    
    def createArr(data, type='double'):
        num = len(data)
        func1, func2 = (es.new_doubleArray, es.doubleArray_setitem) if type == 'double' else (es.new_intArray, es.intArray_setitem) 
        array = func1(num)
        map(lambda i:func2(array, i, data[i]), xrange(num))
        return array
    
    def getArr(array, num, type='double'):
        func = es.doubleArray_getitem if type == 'double' else es.intArray_getitem
        return tuple(func(array, i) for i in xrange(num))
    
    devId = es.E7XX_ConnectPciBoard(1)
    assert(devId >= 0)
    
    logging.info('qTSC %d' % es.E7XX_qTSC(devId)[1])
    logging.info('qTPC %d' % es.E7XX_qTPC(devId)[1])
    
    data = createArr((99,) * 10, type='double')
    assert(es.E7XX_qTNS(devId, '', data) != 0)
    print(getArr(data, 10, type='double'))
    
    data = createArr((99,) * 10, type='double')
    assert(es.E7XX_qTSP(devId, '', data) != 0)
    print(getArr(data, 10, type='double'))
    
    data = createArr((99,) * 10, type='double')
    assert(es.E7XX_qVMA(devId, '', data) != 0)
    print(getArr(data, 10, type='double'))
    
    data = createArr((99,) * 10, type='double')
    assert(es.E7XX_qVMI(devId, '', data) != 0)
    print(getArr(data, 10, type='double'))
    
    data = createArr((99,) * 10, type='double')
    assert(es.E7XX_qVOL(devId, '', data) != 0)
    print(getArr(data, 10, type='double'))
    
    es.E7XX_CloseConnection(devId)
