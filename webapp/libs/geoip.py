import socket
import json

from urllib import urlopen

from webapp import app

# simple geoip lookup to get appliance latitude/longitude
def get_geodata():
    socket.setdefaulttimeout(5)
    url = "http://freegeoip.net/json/"
    try:

        response = json.loads(urlopen(url).read())

        return {
            "latitude": response['latitude'],
            "longitude": response['longitude']
        }
    
    # timeout!
    except Exception as ex:
        app.logger.error("Error getting geolocation.  Using Old Faithful.  %s" % ex)
        return {
            "latitude": "44.4605",
            "longitude": "-110.8282"
        }
