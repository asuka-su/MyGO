from flask import Flask

from models import DatabaseManager
from routers import main_blueprint, user_blueprint, trip_blueprint

def create_app():
    app = Flask(__name__)

    db_manager = DatabaseManager(initial=True)
    db_manager.insert_fake_data()

    app.register_blueprint(main_blueprint)
    app.register_blueprint(user_blueprint, url_prefix='/user')
    app.register_blueprint(trip_blueprint, url_prefix='/trip')

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)

