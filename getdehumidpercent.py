#!/usr/bin/python
import operator
import os
import sys
import time

rrdfile = '/var/lib/munin/hoopycat.com/arrogant-bastard-dehumid_hoopydehumid-hoopydehumid-g.rrd'

def relativedate(ts):
    # produces a nice relative date given a timestamp
    plural = lambda x: 's' if (x < 1 or x > 2) else ''
    delta = time.time() - ts
    if delta < 0:
        return 'in the future'
    elif delta < 60*60:
        return '%i minute%s ago' % (delta/60, plural(delta/60))
    elif delta < 4*60*60:
        return '%i hour%s ago' % (delta/60/60, plural(delta/60/60))
    elif delta < 7*24*60*60:
        if time.localtime(time.time()).tm_yday == time.localtime(ts).tm_yday:
            return time.strftime('today at %H:%M %Z', time.localtime(ts))
        elif time.localtime(time.time()).tm_yday == time.localtime(ts).tm_yday+1:
            return time.strftime('yesterday at %H:%M %Z', time.localtime(ts))
        else:
            return time.strftime('%A at %H:%M %Z', time.localtime(ts))
    elif delta < 30*24*60*60:
        return time.strftime('%A, %B %d', time.localtime(ts))
    else:
        return time.strftime('%B %d, %Y', time.localtime(ts))

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
        outdict['emptied'] = relativedate(lastempty)
    else:
        outdict['emptied'] = '<i>at some point</i>'

    if lastfull > 0:
        outdict['filled'] = relativedate(lastfull)
    else:
        outdict['filled'] = '<i>recently</i>'

    if prevempty > 0:
        outdict['prevempty'] = relativedate(prevempty)
    else:
        outdict['prevempty'] = '<i>awhile back</i>'

    if (prevempty > 0) and (lastfull > 0):
        duration = float(lastfull - prevempty)
        outdict['duration_sec'] = duration
        plural = lambda x: 's' if (x < 1 or x > 2) else ''
        if duration > 1.5*7*24*60*60:
            outdict['duration'] = '%.1f week%s' % (duration/(7*24*60*60), plural(duration/(7*24*60*60)))
        elif duration > 2*24*60*60:
            outdict['duration'] = '%.1f day%s' % (duration/(24*60*60), plural(duration/(24*60*60)))
        else:
            outdict['duration'] = '%.1f hour%s' % (duration/(60*60), plural(duration/(60*60)))
    else:
        outdict['duration'] = '<i>unknown</i>'
        outdict['duration_sec'] = -1

    return outdict

def printhtml(statsdict):
    sys.stdout.write("""Content-type: text/html

        <html>
            <title>Now %(percent)i%% full.  Last emptied %(emptied)s, last full %(filled)s after running for %(duration)s.</title>
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
    document.write("emptied %(emptied)s, ");
    document.write("and was last reported full %(filled)s. ");
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

