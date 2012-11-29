'''
Created on Mar 21, 2012

@author: Zephyre
'''
import unittest
import AVTCamera
import inspect
import time
import threading

class AVTCameraTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        AVTCamera.AVTCamera.initLibrary()
        nodeList = AVTCamera.AVTCamera.getNodeList()
        assert len(nodeList) == 1
        AVTCameraTestCase.cam = AVTCamera.AVTCamera(nodeList[0])
        
    @classmethod
    def tearDownClass(cls):
        AVTCamera.AVTCamera.releaseLibrary()
        
    def printTarget(self):
        print(''.join(('Testing ', inspect.stack()[1][3], '...')))

    def setUp(self):
        self.cam = AVTCameraTestCase.cam
    
    @unittest.skip('')
    def testParametersDeprec(self):
        self.printTarget()
        
        spPara = (AVTCamera.fg.PVAL.PVAL_AUTO, AVTCamera.fg.PVAL.PVAL_OFF, AVTCamera.fg.PVAL.PVAL_ONESHOT)
        
        def f1(paraName):
            paraIndex = AVTCamera.AVTCamera.parameters[paraName]
            def f2(v2):
                try:
                    self.cam.setParameter(paraIndex, v2)
                    self.assertEqual(v2, self.cam.getParameter(paraIndex)['Value'])
                    return ''
                except:
                    if v2 == AVTCamera.fg.PVAL.PVAL_AUTO:
                        return 'Auto: failed'
                    elif v2 == AVTCamera.fg.PVAL.PVAL_OFF:
                        return 'Off: failed'
                    elif v2 == AVTCamera.fg.PVAL.PVAL_ONESHOT:
                        return 'One-shot: failed'
                    else:
                        return 'Value %d: failed' % v2
            
            try:
                pinfo = self.cam.getParameter(paraIndex)
                result = map(f2, (pinfo['Min'], pinfo['Max']) + spPara)
                return '%s: %d, %s' % (paraName, paraIndex, '\t'.join(result))
            except:
                return '%s: %d, failed' % (paraName, paraIndex)

        self.cam.connect()
        f = open('Parameter Test Result.txt', 'w')
        resultList = map(f1, AVTCamera.AVTCamera.parameters)
        map(lambda line : f.write(line + '\n'), resultList)
        
        self.cam.deviceName
        self.cam.burstCount = 10
        self.assertEqual(self.cam.burstCount['Value'], 10)
        
        f.close()
        self.cam.disconnect()

    def testConnection(self):
        self.printTarget()
        self.cam.connect()
        self.assertTrue(self.cam.isConnected)
        self.cam.disconnect()
        self.assertFalse(self.cam.isConnected)
        
    def testSnapshot(self):
        self.printTarget()
        self.cam.connect()
        
        def getInfo(key):
            if key == 'RawData':
                info = '...'
            else:
                info = data[key]
            return '%s = %s' % (key, info)
        
        self.cam.setImageMode(0)
        self.cam.deinterlace = 1
        h = 64
        self.cam.roi = (0, 0, 768, h)
        self.cam.shutter = 2000
        self.cam.gain = 250
        for i in xrange(1):
            data = self.cam.snapshot()
            print(map(getInfo, data.keys()))
        
        self.cam.disconnect()
        
#        raw = data['RawData']
#        for i in xrange(4):
#            print('#%02d' % i, ', '.join(map(lambda c : '%03d' % ord(c), raw[i * 768 + 00:i * 768 + 768])))
    
    @unittest.skip('')
    def testSequence(self):
        self.printTarget()
        self.cam.connect()
        
        frameLen = 20
        self.cam.burstCount = frameLen
        self.cam.openCapture()
        self.cam.startDevice()
        
        def func():
            def getInfo(key):
                if key == 'RawData':
                    info = '...'
                else:
                    info = data[key]
                return '%s = %s' % (key, info)
            data = self.cam.getImage()
            print(map(getInfo, data.keys()))
            
        map(lambda i:func(), xrange(frameLen))
            
        self.cam.stopDevice()
        self.cam.closeCapture()
        self.cam.disconnect()
        
if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testParameters']
    unittest.main()
