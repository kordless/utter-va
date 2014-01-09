# manage.py
# -*- encoding:utf-8 -*-

from flask import Flask
from flaskext.actions import Manager
from webapp import app

app.config.from_object('config.DebugConfiguration') # configuration
manager = Manager(app, default_help_actions=False)

def hello(app):
    def action(user=('u','world')):
        """
        test command
        """
        print "hello %s!"%user
    return action
manager.add_action('hello',hello)

if __name__ == "__main__":
    manager.run()


