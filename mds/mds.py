'''
Created on Nov 22, 2011

@author: Zephyre
'''

import serial
import time

class MDS_Exception:        
    def __init__(self, errorId, errorMsg=''):
        '''
        errorId is the exception id
        errorMsg is the exception message
        '''
        self.errorId = errorId
        self.errorMsg = errorMsg
        
    def __str__(self):
        '''
        Get the full exception message
        '''
        return 'Exception %d: %s' % (self.errorId, self.errorMsg)
    
class MDS:
    '''
    A class for controlling MDS AOTF controller.
    '''
    ser1 = 1
    _ser2 = 2
    __ser3 = 3
    def __init__(self, port, baudrate=19200):
        '''
        Constructor
        '''
        self.__ser = serial.Serial()
        self.__ser.port = int(port.strip()[3]) - 1
        self.__ser.baudrate = baudrate
        self.__ser.open()
        if not self.__ser.isOpen():
            raise MDS_Exception(0, 'Can\'t open the port')
        
    def __del__(self):
        '''Destructor'''
        if self.__ser is not None:
            if self.__ser.isOpen():
                self.__ser.close()
                print('Device closed.')
        
    def close(self):
        self.__ser.close()
        
    def isOpen(self):
        return self.__ser.isOpen()
        
    def getPortStr(self):
        return self.__ser.portstr
    
    def getBaudRate(self):
        return self.__ser.baudrate
    
    def getCurLine(self):
        '''Get the current selected line number.'''
        self.__ser.flushInput()
        self.__ser.write('x\r')
        self.__ser.readline()
        string = self.__ser.readline().strip()
        return str(string[-1])
    
    def setLine(self, line):
        '''Selected a line'''
        self.__ser.flushOutput()
        self.__ser.write('x' + str(line) + '\r')
        
    def getHelp(self):
        '''Get help information.'''
        self.__ser.flushOutput()
        self.__ser.flushInput()
        self.__ser.write('\r')
        string = ''
        while True:
            remain = self.__ser.inWaiting()
            if remain == 0:
                time.sleep(0.1)
                remain = self.__ser.inWaiting()
                if remain == 0:
                    break
            string += self.__ser.read(remain)
        return string
    
    def getStatus(self):
        '''Get the status.'''
        self.__ser.flushInput()
        self.__ser.flushOutput()
        self.__ser.write('s')
        string = ''
        while True:
            remain = self.__ser.inWaiting()
            if remain == 0:
                time.sleep(0.1)
                remain = self.__ser.inWaiting()
                if remain == 0:
                    break
            string += self.__ser.read(remain)
            
        return string
        
    def setFrequency(self, freq):
        '''Set the frequency for current line.'''
        self.__ser.flushOutput()
        self.__ser.write('f' + str(freq) + '\r')
    
    def switch(self, sw):
        '''Turn on/off current line.'''
        self.__ser.flushOutput()
        string = '0'
        if sw:
            string = '1'
        self.__ser.write('o' + string + '\r')
        
    def setPowerRawVal(self, val):
        '''Set the power (in raw value)'''
        self.__ser.flushOutput()
        self.__ser.write('p' + str(val) + '\r')
    
    def setPowerdBm(self, val):
        '''Set the power (in dBm)'''
        self.__ser.flushOutput()
        self.__ser.write('d' + str(val) + '\r')
        
    def setDriverMode(self, mode):
        '''Set the driver mode, 0 for internal, 1 for external.'''
        self.__ser.flushOutput()
        self.__ser.write('i' + str(mode) + '\r')
        
    def save(self):
        '''Save current settings to the EEPROM.'''
        self.__ser.flushOutput()
        self.__ser.write('e')                            
    
