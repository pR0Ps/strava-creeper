#!/usr/bin/env python

from flask import Flask, request, session, redirect, url_for, flash
from flask import render_template_string

from stravalib import Client
from stravalib.attributes import LatLon

from geopy.distance import distance, EARTH_RADIUS
import math
import itertools

try:
    from config import SECRET_KEY, STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET, STRAVA_CALLBACK_URL
except ImportError:
    print ("Couldn't get data from the config.py file")
    print ("Create 'config.py' that sets 'SECRET_KEY', 'STRAVA_CLIENT_ID'," \
           "'STRAVA_CLIENT_SECRET', and 'STRAVA_CALLBACK_URL'")
    raise

DEBUG = True

app = Flask(__name__)
app.config.from_object(__name__)

@app.route('/')
def index():
    return "<html><body>index</body></html>"

@app.route('/login')
def login():
    if session.get('access_token', None) is None:
        return redirect(Client().authorization_url(client_id=STRAVA_CLIENT_ID, redirect_uri=STRAVA_CALLBACK_URL, scope="view_private"))
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.pop('access_token', None)
    return redirect(url_for('index'))

@app.route('/auth')
def auth():
    code = request.args.get('code')
    token = Client().exchange_code_for_token(client_id=STRAVA_CLIENT_ID, client_secret=STRAVA_CLIENT_SECRET, code=code)
    if token:
        session['access_token'] = token
    return redirect(url_for('process'))

def point_intercepts(points):
    for x in itertools.combinations(points, 2):
        intercepts = find_overlaps(*x)
        if intercepts:
            yield intercepts

def filter_close_points(pnts):
    num = len(pnts)
    for i in range(num):
        if not pnts[i]:
            continue

        for j in range(i+1, num):
            if not pnts[j]:
                continue

            if points_close(pnts[i], pnts[j]):
                pnts[j] = None

    return list(filter(None, pnts))

def points_close(p1, p2, d=0.05):
    dist = distance(p1, p2).km
    #_, _, dist = to_coords(p1, p2)
    return dist < d

def group_points(pnts):
    """Generate lists of points within a 2 km radius of each other"""

    done = False

    while not done:
        done = True

        num = len(pnts)
        close = None

        for i in range(num):

            if not pnts[i]:
                continue
            elif not close:
                # Starting a new group of points
                close = [pnts[i]]
                pnts[i] = None
            elif points_close(close[0], pnts[i], 2.05):
                # Point is close enough to the starting point
                close.append(pnts[i])
                pnts[i] = None
            else:
                # Signal that there are still more points to group
                done = False
        yield close


@app.route('/process')
def process():
    token = session.get('access_token', None)
    if token is None:
        return redirect(url_for('login'))
    client = Client(token)
    athlete = client.get_athlete()
    activities = client.get_activities()
    points = [pnt for a in activities for pnt in (a.end_latlng, a.start_latlng) if pnt]

    #temp = [pnt for ints in point_intercepts(points) for pnt in ints]

    #temp = filter_close_points(points)

    seg = []
    for grps in group_points(points):

        out = []
        for pnt in grps:
            out.append("<trkpt lat=\"{0.lat}\" lon=\"{0.lon}\"></trkpt>".format(pnt))
        seg.append("<trkseg>{}</trkseg>".format("".join(out)))

    return """<?xml version="1.0" encoding="UTF-8"?>
        <gpx version="1.0">
        <name>TEST</name>
        <trk>{}</trk>
        </gpx>""".format("".join(seg))

    return "<html><body><img src='{}'/>{} {}</body></html>".format(athlete.profile, athlete.firstname, athlete.lastname)

@app.route('/debug')
def debug():
    # 2 points 1.6km apart
    pnt1 = LatLon(lat=38.5655527, lon=-98.5169269)
    pnt2 = LatLon(lat=38.5655023, lon=-98.4984944)

    p1, p2, d = to_coords(pnt1, pnt2)

    overlaps = find_overlaps(pnt1, pnt2)
    if not overlaps:
        return "<html><body>NONE</body></html>"
    return "<html><body>{}{}{}</body></html>".format(pnt1, pnt2, overlaps)

def points_center(pnt1, pnt2):
    """Finds the center between 2 points"""

    lat = (pnt1.lat + pnt2.lat) / 2
    lng = (pnt1.lon + pnt2.lon) / 2

    return LatLon(lat=lat, lon=lng)

def to_latlong(x1, y1, x2, y2):
    """
    Compute latitude/longitude (in degrees) from x/y coordinates
    """
    lat1r = y1/EARTH_RADIUS
    lat2r = y2/EARTH_RADIUS
    avg_latr = (lat1r + lat2r)/2

    lng1 = math.degrees(x1/(EARTH_RADIUS * math.cos(avg_latr)))
    lng2 = math.degrees(x2/(EARTH_RADIUS * math.cos(avg_latr)))

    return LatLon(lat=math.degrees(lat1r), lon=lng1), LatLon(lat=math.degrees(lat2r), lon=lng2)

def to_coords(pnt1, pnt2):
    """
    Compute the x/y coordinates of the points and their distance apart

    Uses the equirectangular projection for simplicity since
    the scale we're working on is pretty small and the data isn't
    super accurate anyway
    """
    avg_lat = math.radians(pnt1.lat + pnt2.lat) / 2
    x1 = EARTH_RADIUS * math.radians(pnt1.lon) * math.cos(avg_lat)
    y1 = EARTH_RADIUS * math.radians(pnt1.lat)

    x2 = EARTH_RADIUS * math.radians(pnt2.lon) * math.cos(avg_lat)
    y2 = EARTH_RADIUS * math.radians(pnt2.lat)

    return (x1, y1), (x2, y2), math.sqrt((x2-x1)*(x2-x1) + (y2-y1)*(y2-y1))

def find_overlaps(pnt1, pnt2, rad=1, e=0.05):
    """Find locations where the points overlap"""
    p1, p2, dist = to_coords(pnt1, pnt2)

    max_dist = rad*2

    if dist < e:
        # Points are the same
        return None

    # Compute the 2 intersections
    a = dist/2

    if (a > rad):
        # Circles don't intersect
        return None

    h = math.sqrt(rad*rad - a*a)

    # Center point
    cx = p1[0] + a * (p2[0] - p1[0])/dist
    cy = p1[1] + a * (p2[1] - p1[1])/dist

    # intersection points
    t1x = cx + h * (p2[1] - p1[1])/dist
    t1y = cy - h * (p2[0] - p1[0])/dist
    t2x = cx - h * (p2[1] - p1[1])/dist
    t2y = cy + h * (p2[0] - p1[0])/dist

    return to_latlong(t1x, t1y, t2x, t2y)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)



