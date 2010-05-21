#!/usr/bin/python
import operator
import os
import sys
import time

rrdfile = '/var/lib/munin/hoopycat.com/hennepin.hoopycat.com-dehumid_hoopydehumid-hoopydehumid-g.rrd'

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
    points = {}
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
        elif percent > 80 and lastfull and not lastempty and mostrecent[1] > 80 and mostrecent[1] < 95:
            # we're bouncing
            lastfull = 0
        elif lastempty and percent > 60 and not lastfull and not prevempty:
            # it was >60% full, then someone emptied it "early"
            lastfull = i[0]
        elif percent > 95 and not prevempty:
            # full
            lastfull = i[0]
        elif percent < 20 and lastfull:
            # previous empty
            prevempty = i[0]
        elif percent > 60 and prevempty:
            # we're back to the full before the empty
            stop = True

        # store some points
        if not prevempty:
            for step in [90,80,70,60,50,40,30,20,10]:
                if (percent > step) and (step-10 not in points.keys()):
                    points[step] = i[0]
                    break

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

    # compute slope of last run
    if outdict['duration_sec'] > 0:
        outdict['oldslope'] = 100/float(outdict['duration_sec'])
    else:
        outdict['oldslope'] = 0

    # compute slope of this tank
    if len(points.keys()) > 3:
        keys = points.keys()
        keys.sort()
        max_y = keys[-2:-1][0]
        min_y = keys[1]
        delta_y = max_y-min_y
        delta_x = points[max_y]-points[min_y]
        outdict['newslope'] = delta_y/float(delta_x)
        outdict['debug_slope'] = []
        for i in keys:
             outdict['debug_slope'].append('%i%% at %s' % (
                i, time.strftime('%Y-%m-%d %H:%M', time.localtime(points[i]))))
        outdict['debug_slope'].append('(%i, %i) to (%i, %i) => (%i, %i)' % (
            points[min_y], min_y, points[max_y], max_y, delta_x, delta_y))
    else:
        outdict['newslope'] = 0
        outdict['debug_slope'] = ['Only %i points, no new slope' % len(points.keys())]

    if outdict['newslope'] > 0:
        workingslope = outdict['newslope']
    elif outdict['oldslope'] > 0:
        workingslope = outdict['oldslope']
        outdict['debug_slope'].append('Using old slope')
    else:
        workingslope = -1

    # consider how long we might have left on this tank
    if lastempty and workingslope > 0:
        elapsed_time = time.time() - lastempty
        estimated_time = 1/(.01*workingslope)
        remaining_time = estimated_time - elapsed_time
        predicted_full_ts = time.time() + remaining_time
    else:
        elapsed_time = estimated_time = remaining_time = predicted_full_ts = 0

    outdict['remaining_time'] = remaining_time
    outdict['predicted_full_ts'] = predicted_full_ts

    if predicted_full_ts > 0:
        plural = lambda x: 's' if (x < 1 or x > 2) else ''
        if remaining_time > 1.5*7*24*60*60:
            outdict['predicted_full'] = 'about %i week%s' % (remaining_time/(7*24*60*60), plural(remaining_time/(7*24*60*60)))
        elif remaining_time > 2*24*60*60:
            outdict['predicted_full'] = 'about %i day%s' % (remaining_time/(24*60*60), plural(remaining_time/(24*60*60)))
        elif remaining_time > 60*60:
            outdict['predicted_full'] = 'about %i hour%s' % (remaining_time/(60*60), plural(remaining_time/(60*60)))
        elif remaining_time > 0:
            outdict['predicted_full'] = 'about %i minute%s' % (remaining_time/(60), plural(remaining_time/(60)))
        else:
            outdict['predicted_full'] = 'mere moments'
    elif mostrecent[1] > 95:
        outdict['predicted_full'] = 'no time'
    elif mostrecent[1] > 80:
        outdict['predicted_full'] = '<i>very little time</i>'
    else:
        outdict['predicted_full'] = '<i>some time</i>'

    outdict['debug_slope_str'] = ''.join(['%s\n' % i for i in outdict['debug_slope']])

    return outdict

def printhtml(statsdict):
    sys.stdout.write("""Content-type: text/html

        <html>
            <title>Now %(percent)i%% full (%(predicted_full)s remaining).  Last emptied %(emptied)s, last full %(filled)s after running for %(duration)s.</title>
        <body>
            <ul>
                <li>Percent full: %(percent)i%% (%(predicted_full)s remaining)</li>
                <li>Last emptied: %(emptied)s</li>
                <li>Last full: %(filled)s</li>
                <li>Last cycle took %(duration)s (since %(prevempty)s)</li>
            </ul>
            <pre>Old slope: %(oldslope)f, new slope: %(newslope)f, predicted full ts: %(predicted_full_ts)i</pre>
            <pre>%(debug_slope_str)s</pre>
        </body>
    </html>\n""" % statsdict)

def printjs(statsdict):
    #statsdict['fortune'] = ''.join(os.popen('/usr/games/fortune -s')\
    #    .readlines()).replace('"','\\"').strip().replace('\n',' ')

    statsdict['expires'] = time.strftime('%a, %d %b %Y %H:%M:%S GMT',
        time.gmtime(time.time()+(20*60)))

    if statsdict['percent'] > 95:
        statsdict['freakout'] = '<p><center><blink><b>ZOMG THE DEHUMIDIFIER IS FULL EMPTY IT NOW</b></blink></center></p>'
    else:
        statsdict['freakout'] = ''

    sys.stdout.write("""Content-type: text/javascript\nExpires: %(expires)s

    document.write("%(freakout)s");
    document.write("<div id='progressbar'></div>");
    document.write("<ul>");
    document.write("<li>Tank last emptied %(emptied)s</li>");
    document.write("<li>Last run took %(duration)s ");
    document.write("(from %(prevempty)s to %(filled)s)</li>");
    document.write("<li>Estimated time to full: %(predicted_full)s</li>")
    document.write("</ul>");
    jQuery("#progressbar").reportprogress(%(percent)i);
    \n""" % statsdict)

if __name__ == '__main__':
    if os.environ.has_key('QUERY_STRING'):
        if os.environ['QUERY_STRING'] == 'js':
            printjs(getstats())
            sys.exit(0)

    printhtml(getstats())

