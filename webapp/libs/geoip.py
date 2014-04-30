import socket

from urllib import urlopen
from csv import reader

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
        return {
            "latitude": "35",
            "longitude": "-110"
        }
