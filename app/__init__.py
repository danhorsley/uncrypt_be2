from flask import Flask, jsonify
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from config import Config
from app.models import db
import logging
from flask_jwt_extended import exceptions as jwt_exceptions

jwt = JWTManager()
# Store revoked tokens in memory
jwt_blocklist = set()


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Set up logging
    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger(__name__)
    logger.info("Starting application initialization")

    # Configure CORS
    CORS(
        app,
        resources={
            r"/*": {  # Apply CORS to all routes
                "origins": "*",  # Allow all origins during development
                "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
                "allow_headers": ["Content-Type", "Authorization", "Accept"],
                "expose_headers": ["Content-Type", "Authorization"],
                "supports_credentials": True
            }
        })

    # JWT Configuration
    app.config['JWT_TOKEN_LOCATION'] = ['headers']
    app.config['JWT_HEADER_NAME'] = 'Authorization'
    app.config['JWT_HEADER_TYPE'] = 'Bearer'

    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return jsonify({"error": "Token has expired"}), 401

    @jwt.invalid_token_loader
    def invalid_token_callback(error):
        return jsonify({"error": "Invalid token"}), 401

    @jwt.unauthorized_loader
    def missing_token_callback(error):
        return jsonify({"error": "Authorization token is missing"}), 401

    @jwt.revoked_token_loader
    def revoked_token_callback(jwt_header, jwt_payload):
        return jsonify({"error": "Token has been revoked"}), 401

    # Configure SQLAlchemy
    try:
        logger.info(
            f"Configuring database with URL: {app.config['DATABASE_URL']}")
        app.config['SQLALCHEMY_DATABASE_URI'] = app.config['DATABASE_URL']
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            "pool_recycle": 300,
            "pool_pre_ping": True,
        }

        # Initialize extensions
        jwt.init_app(app)
        db.init_app(app)
        logger.info("Successfully initialized Flask extensions")

        # Register token blocklist loader
        @jwt.token_in_blocklist_loader
        def check_if_token_in_blocklist(jwt_header, jwt_payload):
            jti = jwt_payload["jti"]
            return jti in jwt_blocklist

        # Create database tables
        with app.app_context():
            db.create_all()
            logger.info("Database tables created successfully")

        # Register blueprints without API prefixes
        from app.routes import auth, game, stats, main
        app.register_blueprint(main.bp)  # Main routes
        app.register_blueprint(
            auth.bp)  # Auth routes (/login, /register, etc.)
        app.register_blueprint(game.bp, url_prefix='/api')
        app.register_blueprint(stats.bp, url_prefix='/api')  # Stats routes
        logger.info("Successfully registered all blueprints")

    except Exception as e:
        logger.error(f"Error during application initialization: {str(e)}")
        raise

    logger.info("Application initialization completed successfully")
    return app
