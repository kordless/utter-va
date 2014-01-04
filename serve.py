import os
from webapp import app
from webapp import settings
from werkzeug import SharedDataMiddleware

# add static directory to be served by development server
app.wsgi_app = SharedDataMiddleware(app.wsgi_app, {
  '/': os.path.join(os.path.dirname(__file__), './webapp/static')
})
app.run(debug=True, host="0.0.0.0")
