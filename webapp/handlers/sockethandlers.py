from flask import Blueprint
from flask.ext.socketio import emit
from webapp import socketio

mod = Blueprint('sockets', __name__)

@socketio.on('my event', namespace='/messages')
def test_message(message):
    emit('my response', {'data': message['data']})

@socketio.on('connect', namespace='/messages')
def test_connect():
    emit('events', {'data': 'Connected'})
