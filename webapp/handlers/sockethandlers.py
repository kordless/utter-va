from flask import Blueprint
from flask.ext.socketio import emit, send
from webapp import socketio

mod = Blueprint('sockets', __name__)

@socketio.on('connect', namespace='/utterio')
def connect():
	# build the response
	# response = {"response": "success", "result": {"message": "Sockets online.", "reload": False}}
  # emit response
	emit('message', {"data": "connected"})