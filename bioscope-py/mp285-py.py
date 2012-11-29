'''
Created on Apr 26, 2012

@author: Zephyre
'''
import serial
import struct
import timeit
import time

class mp285(object):
    '''
    MP285 driver
    '''
    
    def __init__(self, port='COM1', baudrate=9600):
        self.port = port
        self.baudrate = baudrate
        self.mstep = 0.04
        self.isClosed = True
        
    def initialize(self):
        self.ser = serial.Serial(self.port, self.baudrate, timeout=None)
        self.isClosed = False
        self.ser.flushInput()
        self.ser.flushOutput()
        
    def pos(self):
        self.ser.write('c\r\x0a')
        data = self.ser.read(14)        
        print(' '.join(tuple(map(lambda c:hex(ord(c)), data))))
        return tuple(v * self.mstep for v in struct.unpack('lll', data[:-2]))
    
    def mov(self, pos):
        data = 'm' + struct.pack('lll', *tuple(int(v / self.mstep) for v in pos)) + '\r\x0a'
        print(''.join(map(lambda c:hex(ord(c)), data)))
        self.ser.write(data)
        self.ser.read(2)
        
    def movr(self, axis, delta):
        pos = list(self.pos())
        pos[axis] += delta
        self.mov(pos)
        
    def setVel(self, vel, highRes):
        vel = vel | (0x8000 if highRes else 0x0)
        self.ser.write('V' + struct.pack('H', vel) + '\r\x0a')
        self.ser.read(2) 
        
    def refreshVfd(self):
        self.ser.write('n\r\x0a')
        self.ser.read(2)
        
    def close(self):
        if not self.isClosed:
            self.ser.close()
        self.isClosed = True

if __name__ == '__main__':
    m = mp285()
    m.initialize()
    m.setVel(0x7fff, True)
    
    pos = m.pos()
    print('Current @: %.2f, %.2f, %.2f' % pos)
    t1 = time.clock()
    m.movr(2, 1000)
    t2 = time.clock()
    print('Time cost: %f' % (t2 - t1))
    pos = m.pos()
    print('Current @: %.2f, %.2f, %.2f' % pos)
    
    print('Test done.')
