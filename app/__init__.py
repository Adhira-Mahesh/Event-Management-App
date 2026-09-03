from flask import Flask, render_template, redirect
from config import Config
from app.extensions import db


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)

    from app.routes.auth import auth_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.events import events_bp
    from app.routes.resources import resources_bp
    from app.routes.requests import requests_bp
    from app.routes.admin_users import admin_users_bp
    from app.routes.calendar import calendar_bp
    from app.utils import get_current_user

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(events_bp, url_prefix="/events")
    app.register_blueprint(resources_bp, url_prefix="/resources")
    app.register_blueprint(requests_bp, url_prefix="/requests")
    app.register_blueprint(admin_users_bp)
    app.register_blueprint(calendar_bp)

    @app.route("/")
    def index():
        return redirect("/auth/login")


    @app.context_processor
    def inject_auth_context():
        return {
            "current_user": get_current_user()
        }

    register_error_handlers(app)

    with app.app_context():
        db.create_all()

    return app



def register_error_handlers(app):
    # These make sure users NEVER see a raw Python traceback: every
    # unhandled exception is caught here and rendered as a friendly page.

    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        db.session.rollback()
        return render_template("errors/500.html"), 500

    @app.errorhandler(Exception)
    def unhandled_exception(e):
        # Let HTTP exceptions (404, etc.) already handled above pass through
        # unchanged; anything else becomes a generic 500 for the user while
        # the real error still goes to the server log for debugging.
        from werkzeug.exceptions import HTTPException

        if isinstance(e, HTTPException):
            return e
        app.logger.exception("Unhandled exception")
        db.session.rollback()
        return render_template("errors/500.html"), 500
