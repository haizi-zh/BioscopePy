'''
Created on Mar 19, 2012

@author: Zephyre
'''
import unittest
import E7XX
import time
import inspect

allTests = True
class E7XXTestCase(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        E7XXTestCase.stage = E7XX.PiezoStage(1)
        E7XXTestCase.stage.connect(1, True)
        E7XXTestCase.stage.configStatuses = (True,) * 3
        E7XXTestCase.stage.svoStatus = (True,) * 3
        E7XXTestCase.moveInterval = 0.3
        E7XXTestCase.delta = 0.005
        E7XXTestCase.stage.lowerLimit = (0,) * 3
        E7XXTestCase.stage.upperLimit = (99, 99, 9.9)

    @classmethod
    def tearDownClass(cls):
        E7XXTestCase.stage.disconnect()
    
    def __printTestTarget(self):
        print(''.join(('Testing ', inspect.stack()[1][3], '...')))
        
    def setUp(self):
        self.stage = E7XXTestCase.stage
    
    def tearDown(self):
        pass
    
    @unittest.skipUnless(allTests and False, 'All tests will be run.')
    def testConnect(self):
        self.__printTestTarget()
        self.stage.reboot()
        
        self.stage.disconnect()
            
        self.stage.connect()
        self.assertTrue(self.stage.isConnected)
        self.stage.disconnect()
        self.assertFalse(self.stage.isConnected)
        
    @unittest.skipUnless(allTests, 'All tests will be run.')
    def testMoveR(self):
        self.__printTestTarget()
        self.stage.svoStatus = (True,) * self.stage.numTotalAxes
        def assertion(index):
            pos1 = positionsNew[index - 1]
            delta = posDict[index]
            pos0 = pos[index - 1]
            self.assertAlmostEqual(pos0 + delta, pos1, delta=self.delta)
        # dictionary usage
        pos = self.stage.position
        delta = (1, 2, 3)
        posDict = dict(zip((2, 3, 1), delta))
        self.stage.moveRelative(posDict)
        time.sleep(self.moveInterval)
        positionsNew = self.stage.position
        map(assertion, (2, 3, 1))

    @unittest.skipUnless(allTests, 'All tests will be run.')
    def testMove(self):
        self.__printTestTarget()
        self.stage.svoStatus = (True,) * self.stage.numTotalAxes
        def assertion(index):
            pos1 = positionsNew[index - 1]
            pos2 = posDict[index]
            self.assertAlmostEqual(pos1, pos2, delta=self.delta)
            
        # dictionary usage
        positions = (8, 2, 5)
        posDict = dict(zip((2, 3, 1), positions))
        self.stage.position = posDict
        time.sleep(self.moveInterval)
        positionsNew = self.stage.position
        map(assertion, (2, 3, 1))
        
        positions = (7, 3)
        posDict = dict(zip((2, 1), positions))
        self.stage.position = posDict
        time.sleep(self.moveInterval)
        positionsNew = self.stage.position
        map(assertion, (2, 1))
        
        # list usage
        positions = (2, 2, 2)
        self.stage.position = positions
        time.sleep(self.moveInterval)
        positionsNew = self.stage.position
        map(lambda i :
            self.assertAlmostEqual(positions[i], positionsNew[i], delta=self.delta),
            xrange(len(positions)))
        
        positions = (1, 7)
        self.stage.position = positions
        time.sleep(self.moveInterval)
        positionsNew = self.stage.position
        map(lambda i :
            self.assertAlmostEqual(positions[i], positionsNew[i], delta=self.delta),
            xrange(len(positions)))
    
    @unittest.skipUnless(allTests, 'All tests will be run.')
    def testHome(self):
        self.__printTestTarget()
        self.stage.svoStatus = (True,) * self.stage.numTotalAxes
        # Test if setHome == getHome
        positions = (2, 2, 2)
        self.stage.position = positions
        time.sleep(self.moveInterval)
        self.stage.setHome()
        posHome = self.stage.getHome()
        map(lambda i :
            self.assertAlmostEqual(positions[i], posHome[i], delta=self.delta),
            xrange(len(posHome)))
    
    @unittest.skipUnless(allTests, 'All tests will be run.')    
    def testSoftLimits(self):
        self.__printTestTarget()
        upperO = self.stage.upperLimit
        upper = tuple(v - 1 for v in upperO)
        self.stage.upperLimit = upper
        upperNow = self.stage.upperLimit
        map(lambda x, y: self.assertAlmostEqual(x, y, delta=self.delta), upper, upperNow)
        self.stage.upperLimit = upperO
        
        lowerO = self.stage.lowerLimit
        lower = tuple(v + 1 for v in lowerO)
        self.stage.lowerLimit = lower
        lowerNow = self.stage.lowerLimit
        map(lambda x, y:self.assertAlmostEqual(x, y, delta=self.delta), lower, lowerNow)
        self.stage.lowerLimit = lowerO
        
    @unittest.skipUnless(allTests and False, 'All tests will be run.')
    def testHalt(self):
        self.stage.halt()
        self.stage.halt((1, 2, 3))
    
    @unittest.skipUnless(allTests, 'All tests will be run.')
    def testIsMoving(self):
        self.__printTestTarget()
        im = self.stage.isMoving
    
    @unittest.skipUnless(allTests, 'All tests will be run.')
    def testSVO(self):
        self.__printTestTarget()
        def f1(setStatus):
            # list
            self.stage.svoStatus = setStatus
            newStatus = self.stage.svoStatus[:len(setStatus)]
            map(lambda x, y: self.assertEqual(x, y), setStatus, newStatus)
        map(f1, ((True, False), (False, True), (False,) * 3, (True,) * 3))
        
        def f2(setStatus):
            # dictionary
            self.stage.svoStatus = setStatus
            newStatus = self.stage.svoStatus
            map(lambda key : self.assertEqual(setStatus[key], newStatus[key - 1]),
                setStatus.keys())
        map(f2, ({1:True, 2:False}, {2:True, 1:False}, {1:True, 2:True, 3:True}))
        
        self.stage.svoStatus = (True,) * 3
    
    @unittest.skipUnless(allTests, 'All tests will be run.')    
    def testConfig(self):
        self.__printTestTarget()
        def f1(cfg):
            self.stage.configStatuses = cfg
            cfgNew = self.stage.configStatuses
            map(lambda x, y:self.assertEqual(x, y), cfg, cfgNew)
        def f2(cfg):
            self.stage.configStatuses = cfg
            cfgNew = self.stage.configStatuses
            map(lambda key: self.assertEqual(cfgNew[key - 1], cfg[key]),
                cfg.keys())
        
        map(f1, ((x, y, z) for x in (True, False) for y in (True, False) for z in (True, False)))
        map(f2, ({1:True, 2:False}, {2:True, 3:False}, {3:True, 1:False}, {1:True, 2:True, 3:True}))
        self.stage.configStatuses = (True,) * self.stage.numTotalAxes
    
    @unittest.skipUnless(allTests, 'All tests will be run.')    
    def testOpenLoopValue(self):
        self.__printTestTarget()
        self.stage.svoStatus = (False,) * self.stage.numTotalAxes
        ol0 = self.stage.openLoopValue
        ol1 = tuple(v + 1 for v in ol0)
        self.stage.openLoopValue = ol1
        time.sleep(self.moveInterval)
        ol2 = self.stage.openLoopValue
        self.stage.svoStatus = (True,) * self.stage.numTotalAxes
        map(lambda x, y:self.assertAlmostEqual(x, y, delta=0.01), ol1, ol2)
    
    @unittest.skipUnless(allTests, 'All tests will be run.')    
    def testIsOnTarget(self):
        self.__printTestTarget()

    @unittest.skipUnless(allTests, 'All tests will be run.')        
    def testTravelRange(self):
        self.__printTestTarget()
        r = self.stage.travelRanges
        self.assertEqual(len(r), len(self.stage.axisNames))
    
    @unittest.skipUnless(allTests, 'All tests will be run.')    
    def testAxisNames(self):
        self.__printTestTarget()
        n0 = self.stage.axisNames
        n1 = 'ABC'
        self.stage.axisNames = n1
        n2 = self.stage.axisNames
        self.assertEqual(n1, n2)
        self.stage.axisNames = n0
        
    @unittest.skipUnless(allTests, 'All tests will be run.')    
    def testVelocity(self):
        self.__printTestTarget()
        v0 = self.stage.velocity
        v1 = tuple(v + 1 for v in v0)
        self.stage.velocity = v1
        v2 = self.stage.velocity
        map(lambda x, y:self.assertAlmostEqual(x, y, delta=0.001),
            v1, v2)
        self.stage.velocity = v0
    
    @unittest.skipUnless(allTests, 'All tests will be run.')    
    def testVer(self):
        print(self.stage.firmwareVer)
        
    @unittest.skipUnless(allTests, 'All tests will be run.')
    def testWaitForAxis(self):
        self.stage.waitForAxis()
        self.stage.waitForAxis((1, 2, 3))
        
    @unittest.skipUnless(allTests, 'All tests will be run.')
    def testPiezo(self):
        self.assertEqual(self.stage.numPiezoChannels, 4)
    
    @unittest.skipUnless(allTests, 'All tests will be run.')
    def testSensor(self):
        self.assertEqual(self.stage.numSensorChannels, 3)
        self.stage.sensorPositions
        
     
if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    allTests = False
    unittest.main()
