from urllib import urlopen
from csv import reader
import sys
import re

def get_geodata():

    URL = "http://freegeoip.net/csv/"
    response_csv = reader(urlopen(URL))
    csv_data = response_csv.next()

    return {
        "ip":csv_data[0],
        "countrycode":csv_data[1],
        "countryname":csv_data[2],
        "regioncode":csv_data[3],
        "regionname":csv_data[4],
        "city":csv_data[5],
        "zipcode":csv_data[6],
        "latitude":csv_data[7],
        "longitude":csv_data[8]
    }