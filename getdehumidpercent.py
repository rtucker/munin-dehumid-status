#!/usr/bin/python
import operator
import os
import sys
import time

timeformat = '%A at %H:%M %Z'
rrdfile = '/var/lib/munin/hoopycat.com/arrogant-bastard-dehumid_hoopydehumid-hoopydehumid-g.rrd'

def getstats():
    fd0 = os.popen('rrdtool fetch %s MAX -s -30days -e -9days' % rrdfile)
    fd1 = os.popen('rrdtool fetch %s MAX -s -9days -e -2days' % rrdfile)
    fd2 = os.popen('rrdtool fetch %s MAX -s -2days' % rrdfile)

    content = fd0.readlines() + fd1.readlines() + fd2.readlines()

    prevempty = 0
    lastfull = 0
    lastempty = 0
    stop = False
    cache = []
    mostrecent = None

    for i in content:
        data = i.strip().split()
        if len(data) == 2:
            if data[1] != 'nan':
                mostrecent = (int(data[0].replace(':','')), float(data[1]))
                ts = int(data[0].replace(':',''))
                percent = float(data[1])
                cache.append((ts, percent))

    # go backwards through time
    for i in sorted(cache, key=operator.itemgetter(0), reverse=True):
        if stop:
            break

        ts, percent = i

        # states:
        # is filling: no last full yet, percent < 100
        # is full: percent is 100
        # is empty: percent is 0 (or at least suddenly unfull)

        if percent < 20 and not lastfull and not prevempty:
            # pretty much empty
            lastempty = i[0]
        elif percent > 95 and not prevempty:
            # full
            lastfull = i[0]
        elif percent < 20 and lastfull:
            # previous empty
            prevempty = i[0]
        elif percent > 95 and prevempty:
            # we're back to the full before the empty
            stop = True

    outdict = {'percent': mostrecent[1],
               'emptied_ts': lastempty,
               'filled_ts': lastfull,
               'prevempty_ts': prevempty}

    if lastempty > 0:
        outdict['emptied'] = time.strftime(timeformat, time.localtime(lastempty))
    else:
        outdict['emptied'] = '<i>unknown</i>'

    if lastfull > 0:
        outdict['filled'] = time.strftime(timeformat, time.localtime(lastfull))
    else:
        outdict['filled'] = '<i>unknown</i>'

    if prevempty > 0:
        outdict['prevempty'] = time.strftime(timeformat, time.localtime(prevempty))
    else:
        outdict['prevempty'] = '<i>unknown</i>'

    if (prevempty > 0) and (lastfull > 0):
        duration = float(lastfull - prevempty)
        outdict['duration_sec'] = duration
        if duration > 1.5*7*24*60*60:
            outdict['duration'] = '%.1f weeks' % (duration/(7*24*60*60))
        elif duration > 2*24*60*60:
            outdict['duration'] = '%.1f days' % (duration/(24*60*60))
        else:
            outdict['duration'] = '%.1f hours' % (duration/(60*60))
    else:
        outdict['duration'] = '<i>unknown</i>'
        outdict['duration_sec'] = -1

    return outdict

def printhtml(statsdict):
    sys.stdout.write("""Content-type: text/html

        <html>
            <title>Now %(percent)i%% full.  Last emptied %(emptied)s, last full on %(filled)s after running for %(duration)s.</title>
        <body>
            <ul>
                <li>Percent full: %(percent)i%%</li>
                <li>Last emptied: %(emptied)s</li>
                <li>Last full: %(filled)s</li>
                <li>Last cycle took %(duration)s (since %(prevempty)s)</li>
            </ul>
        </body>
    </html>\n""" % statsdict)

def printjs(statsdict):
    statsdict['fortune'] = ''.join(os.popen('/usr/games/fortune -s')\
        .readlines()).replace('"','\\"').strip().replace('\n',' ')

    statsdict['expires'] = time.strftime('%a, %d %b %Y %H:%M:%S GMT',
        time.gmtime(time.time()+(20*60)))

    if statsdict['percent'] > 95:
        statsdict['freakout'] = '<p><center><blink><b>ZOMG THE DEHUMIDIFIER IS FULL EMPTY IT NOW</b></blink></center></p>'
    else:
        statsdict['freakout'] = ''

    sys.stdout.write("""Content-type: text/javascript\nExpires: %(expires)s

    document.write("%(freakout)s");
    document.write("<div id='progressbar'></div>");
    document.write("<p style='text-align:justify;'>The dehumidifier was last ");
    document.write("emptied on %(emptied)s, ");
    document.write("and was last reported full on %(filled)s. ");
    document.write("The last cycle took %(duration)s, starting ");
    document.write("%(prevempty)s. ");
    document.write("<i>%(fortune)s</i></p>");
    jQuery("#progressbar").reportprogress(%(percent)i);
    \n""" % statsdict)

if __name__ == '__main__':
    if os.environ.has_key('QUERY_STRING'):
        if os.environ['QUERY_STRING'] == 'js':
            printjs(getstats())
            sys.exit(0)

    printhtml(getstats())

