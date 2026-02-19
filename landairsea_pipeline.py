import requests
import json
from google.cloud import bigquery
from datetime import datetime
import logging
import uuid
import os

class LandAirSeaToBigQuery:
    def __init__(self, client_token, username, password, project_id, dataset_id, table_id):
        self.api_url = "https://gateway.landairsea.com/Track/MyDevices"
        self.client_token = client_token
        self.username = username
        self.password = password
        self.project_id = project_id
        self.dataset_id = dataset_id
        self.table_id = table_id
        
        # Enhanced logging
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)

    def get_device_data(self):
        """Fetch data from LandAirSea API"""
        self.logger.info(f"Starting API request to: {self.api_url}")
        
        # Log redacted credentials for verification
        self.logger.info(f"Using client token ending in: ...{self.client_token[-4:]}")
        self.logger.info(f"Using username: {self.username}")
        
        headers = {
            "Content-Type": "application/json",
            "ClientId": "rrs-pipeline-client"
        }
        
        payload = {
            "clientToken": self.client_token,
            "username": self.username,
            "password": self.password
        }
        
        try:
            self.logger.info("Sending API request...")
            response = requests.post(self.api_url, headers=headers, json=payload)
            self.logger.info(f"API response status code: {response.status_code}")
            
            # Log response headers
            self.logger.info(f"Response headers: {dict(response.headers)}")
            
            response.raise_for_status()
            data = response.json()
            
            # Log full response structure (without sensitive data)
            self.logger.info(f"Response keys: {list(data.keys())}")
            
            devices = data.get('devicedetails', [])
            self.logger.info(f"Found {len(devices)} devices in response")
            
            if devices:
                # Log summary of each device
                for device in devices:
                    self.logger.info(
                        f"Device ID: {device.get('deviceid')}, "
                        f"Location: {device.get('lastlocation')}, "
                        f"Last Updated: {device.get('lastlocationtimestamp')}"
                    )
            else:
                self.logger.warning("No devices found in API response")
                
            return data
            
        except Exception as e:
            self.logger.error(f"API request failed: {str(e)}")
            if hasattr(response, 'text'):
                self.logger.error(f"Error response content: {response.text}")
            raise

    def prepare_rows_for_bigquery(self, api_data):
        """Transform API response into BigQuery compatible format"""
        self.logger.info("Starting data preparation for BigQuery")
        
        devices = api_data.get('devicedetails', [])
        self.logger.info(f"Processing {len(devices)} devices")
        
        rows = []
        current_timestamp = datetime.utcnow()
        self.logger.info(f"Current timestamp: {current_timestamp.isoformat()}")
        
        for device in devices:
            try:
                # Log raw device data
                self.logger.debug(f"Processing device data: {json.dumps(device)}")
                
                # Convert all keys to lowercase
                device = {k.lower(): v for k, v in device.items()}
                
                # Extract last location timestamp
                last_location_ts = device.get('lastlocationtimestamp', current_timestamp.isoformat())
                
                row = {
                    'record_id': str(uuid.uuid4()),
                    'data_timestamp': current_timestamp.isoformat(),
                    'device_id': device.get('deviceid'),
                    'latitude': float(device.get('latitude', 0)),
                    'longitude': float(device.get('longitude', 0)),
                    'last_location': device.get('lastlocation', ''),
                    'speed_kmh': float(device.get('speed_kmh', 0)),
                    'heading': float(device.get('heading', 0)),
                    'elevation': float(device.get('elevation', 0)),
                    'voltage': float(device.get('voltage', 0)),
                    'is_stopped': bool(device.get('isstopped', False)),
                    'cellular_strength': int(device.get('cellularstrength', 0)),
                    'satellite_strength': int(device.get('satellitestrength', 0)),
                    'interval': int(device.get('interval', 0)),
                    'last_location_timestamp': last_location_ts
                }
                
                # Log prepared row
                self.logger.debug(f"Prepared row: {json.dumps(row)}")
                rows.append(row)
                
            except Exception as e:
                self.logger.error(f"Error preparing row for device {device.get('deviceid', 'unknown')}: {str(e)}")
                continue
        
        self.logger.info(f"Successfully prepared {len(rows)} rows for BigQuery")
        return rows

    def load_data_to_bigquery(self, rows):
        """Load data into BigQuery table"""
        if not rows:
            self.logger.warning("No rows to load into BigQuery")
            return
        
        table_id = f"{self.project_id}.{self.dataset_id}.{self.table_id}"
        self.logger.info(f"Starting BigQuery load to table: {table_id}")
        self.logger.info(f"Number of rows to load: {len(rows)}")
        
        try:
            client = bigquery.Client(project=self.project_id)
            
            # Check if table exists
            try:
                client.get_table(table_id)
            except Exception as e:
                self.logger.error(f"Error accessing table {table_id}: {str(e)}")
                raise
            
            # Insert rows
            errors = client.insert_rows_json(table_id, rows)
            
            if errors:
                self.logger.error(f"Errors inserting rows: {errors}")
                raise Exception(f"BigQuery insert errors: {errors}")
            
            self.logger.info(f"Successfully loaded {len(rows)} rows to BigQuery")
            
            # Verify the insert with a count
            query = f"""
            SELECT COUNT(*) as count
            FROM `{table_id}`
            WHERE data_timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 5 MINUTE)
            """
            query_job = client.query(query)
            results = query_job.result()
            for row in results:
                self.logger.info(f"Verified {row.count} new records in the last 5 minutes")
                
        except Exception as e:
            self.logger.error(f"Error loading data to BigQuery: {str(e)}")
            raise

    def run_pipeline(self):
        """Run the complete pipeline"""
        self.logger.info("Starting pipeline execution")
        try:
            # Get API data
            api_data = self.get_device_data()
            
            if not api_data or 'devicedetails' not in api_data:
                self.logger.error("No valid data received from API")
                return False
            
            # Prepare rows
            rows = self.prepare_rows_for_bigquery(api_data)
            
            if not rows:
                self.logger.error("No rows prepared for BigQuery")
                return False
            
            # Load to BigQuery
            self.load_data_to_bigquery(rows)
            return True
            
        except Exception as e:
            self.logger.error(f"Pipeline failed: {str(e)}")
            return False
