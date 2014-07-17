from webapp.libs.twitter import *

t = Twitter(auth=OAuth("7718322-iYWHXzw50yLuhf7juvwrGhx4JN512sqvToRdNJlSM9", "rFp1aVsSuqa24Wuhf2zufw34taGC2IVA8tWcm5kXfuaeF", "sJUxn3o0qVBaFviJXIAArrLj0", "WmU2c0v78zGqjYXpVEWcNwi4uCE3wdp4p5xnjuuLP6zXkVxq6c"))
print t.statuses.home_timeline(count=5)
