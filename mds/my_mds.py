'''
Created on Nov 22, 2011

@author: Zephyre
'''

import mds        
if __name__ == '__main__':
    dev = mds.MDS('COM3')
    dev.setDriverMode(0)
    dev.setLine(2)
    dev.switch(True)
    dev.setPowerdBm(22.5)
    print(dev.getStatus())
