import json
import os

import boto3
import psycopg2
from flask import Flask, jsonify

app = Flask(__name__)

REGION = os.getenv("AWS_REGION", "eu-central-1")

ssm = boto3.client("ssm", region_name=REGION)
secrets = boto3.client("secretsmanager", region_name=REGION)


def get_parameter(name):
    response = ssm.get_parameter(Name=name, WithDecryption=True)
    return response["Parameter"]["Value"]


def get_database_config():
    endpoint = get_parameter("/ziyad-project/database/endpoint")
    port = get_parameter("/ziyad-project/database/port")
    database = get_parameter("/ziyad-project/database/name")
    secret_arn = get_parameter("/ziyad-project/database/secret-arn")

    response = secrets.get_secret_value(SecretId=secret_arn)
    credentials = json.loads(response["SecretString"])

    return {
        "host": endpoint,
        "port": int(port),
        "dbname": database,
        "user": credentials["username"],
        "password": credentials["password"],
        "sslmode": "require"
    }


@app.route("/")
def home():
    return jsonify({
        "message": "Ziyad AWS Cloud Project",
        "status": "running",
        "architecture": "CloudFront -> ALB -> EC2 Auto Scaling -> RDS"
    })


@app.route("/health")
def health():
    return jsonify({"status": "healthy"}), 200


@app.route("/db-check")
def database_check():
    try:
        config = get_database_config()

        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]

        cursor.close()
        connection.close()

        return jsonify({
            "database": "connected",
            "version": version
        }), 200

    except Exception as error:
        return jsonify({
            "database": "connection failed",
            "error": str(error)
        }), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80)