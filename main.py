from flask import Flask, request, jsonify
import os
import logging
from landairsea_pipeline import LandAirSeaToBigQuery

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Project ID from environment variable
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "landairsea-rrs")

@app.route('/', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({"status": "healthy"}), 200

@app.route('/', methods=['POST'])
def run_pipeline():
    """Pipeline endpoint"""
    logger.info("RRS Pipeline endpoint called")
    
    try:
        # Initialize pipeline
        pipeline = LandAirSeaToBigQuery(
            client_token=os.environ.get("CLIENT_TOKEN"),
            username=os.environ.get("USERNAME"),
            password=os.environ.get("PASSWORD"),
            project_id=PROJECT_ID,
            dataset_id="LAS_RRS_deviceLocations",
            table_id="rrs_device_locations"
        )

        # Get API data
        logger.info("Fetching data from RRS API...")
        api_data = pipeline.get_device_data()
        
        # Check for devices
        devices = api_data.get('devicedetails', [])
        device_count = len(devices)
        logger.info(f"Found {device_count} RRS devices")

        # Prepare and load data
        if device_count > 0:
            rows = pipeline.prepare_rows_for_bigquery(api_data)
            if rows:
                pipeline.load_data_to_bigquery(rows)
                logger.info(f"Successfully loaded {len(rows)} rows to BigQuery")
                return jsonify({
                    "status": "success",
                    "message": f"Loaded {len(rows)} records",
                    "device_count": device_count
                }), 200
        
        return jsonify({
            "status": "success",
            "message": "No new data to load",
            "device_count": device_count
        }), 200
        
    except Exception as e:
        logger.error(f"RRS Pipeline error: {str(e)}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
