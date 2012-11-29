'''
Created on Apr 24, 2012

@author: Zephyre
'''
import sys
import re
import json

def procMd():
    args = sys.argv[2:]
    i = iter(args)
    ifile = 'metadata.txt'
    ofile = 'metadata-dump.txt'
    keys = []
    # operation mode, 0 for dumping, 1 for inspecting, -1 for help
    mode = 0
    while True:
        try:
            s = i.next()
            if s == '-o':
                # Output file
                ofile = i.next()
                continue
            elif s == '-i':
                # input file
                ifile = i.next()
                continue
            elif s == '-v':
                # inspecting mode
                mode = 1
                continue
            elif s == '-h':
                # help mode
                mode = -1
                break
            else:
                while True:
                    keys.append(s)
                    s = i.next()
        except StopIteration:
            break
    
    if mode == -1:
        print('Usage:\n\nInspecting: bioscope-util -v -i <filename>')
        print('Dumping: bioscope-util -i <input_file> -o <output_file> key1 key2 key3...')
    else:
        try:
            with open(ifile, 'r') as ifile:
                mdstr = ''.join(ifile.readlines())
            if mdstr[:3] == '\xef\xbb\xbf':
                # utf-8
                udata = mdstr[3:]
            else:
                # latin-1
                udata = mdstr.decode('latin-1')
            # the last two characters should be }}
            s1 = udata[-100:].rstrip()
            s2 = s1[:-1].rstrip()
            if s1[-1] == '}' and s2[-1] == '}':
                # ok
                pass
            else:
                udata = ''.join((udata, '}'))
            mdj = json.loads(udata)
#            mdj = json.load(ifile)
        except IOError:
            print('Failed to read file: %s' % ifile)
            return
            
        if mode == 0:
            # dumping
            p = re.compile('FrameKey-(\d+)-0-0')
            def getFrameMD(s):
                r = p.match(s)
                if r is not None:
                    n = (int)(r.groups()[0])
                    item = mdj[s]
                    data = dict(map(lambda dumpedKey:(dumpedKey, item[dumpedKey]), keys))
                    return (n, data)
            del mdj['Summary']
            dumpedData = dict(map(getFrameMD, mdj.keys()))
            fn = dumpedData.keys()
            fn.sort()
            with open(ofile, 'w') as df:
                dkList = keys
                df.write(',\t'.join(['Frame', ] + dkList) + '\n')
                def func1(i):
                    dumpItem = (i,) + tuple(map(lambda dk:dumpedData[i][dk], dkList))
                    df.write(('%d,\t' + '%s,\t' * len(dkList) + '\n') % dumpItem)
                map(func1, fn)
        elif mode == 1:
            # inspecting
            summary = mdj['Summary']
            i = iter(mdj)
            while True:            
                k = i.next()
                if k != 'Summary':
                    content = mdj[k]
                    del content['Summary']
                    break
                else:
                    continue
    #        print('Summary:\n')
    #        for k in summary:
    #            print('%s : %s' % (k, summary[k]))
    #        print('\n================\n')
            print('Content:\n')
            for k in content:
                try:
                    print('%s : %s' % (k, content[k]))
                except UnicodeEncodeError:
                    pass
            
if __name__ == '__main__':
    if len(sys.argv) <= 1:
        print('Supported commands: md. \n\nExample: bioscope-util md -v')
        exit()
    cmd = sys.argv[1]
    
    if cmd == 'md':
        procMd()
    else:
        print('Unknown command: %s' % cmd)
