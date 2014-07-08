import socket

from urllib import urlopen
from csv import reader

from webapp import app

# simple geoip lookup to get appliance latitude/longitude
def get_geodata():
    socket.setdefaulttimeout(5)
    URL = "http://freegeoip.net/csv/"
    try:
        response_csv = reader(urlopen(URL))
        csv_data = response_csv.next()
        return {
            "latitude":csv_data[7],
            "longitude":csv_data[8]
        }
    
    # timeout!
    except:
        app.logger.error("Error getting geolocation.  Using Old Faithful.")
        return {
            "latitude": "44.4605",
            "longitude": "-110.8282"
        }
