import os
import confuse
import yaml
from google.cloud import storage

def load_config_from_gcs():
    bucket_name = os.environ.get('CONFIG_BUCKET_NAME')
    config_file_name = 'config.yaml'

    if not bucket_name:
        raise ValueError("CRITICAL ERROR: The 'CONFIG_BUCKET_NAME' environment variable is not set. The function cannot start.")

    try:
        print(f"Loading configuration from bucket")
        storage_client = storage.Client()
        bucket = storage_client.get_bucket(bucket_name)
        blob = bucket.blob(config_file_name)
        
        config_content = blob.download_as_string()
        
        print("Configuration loaded successfully from GCS.")
        return yaml.safe_load(config_content)
    except Exception as e:
        
        raise RuntimeError(f"CRITICAL ERROR: Failed to load config.yaml from bucket. Error: {e}")


appName = 'ZombieProjectsWatcher'
os.environ[appName.upper() + 'DIR'] = '.'

app_config_data = load_config_from_gcs()
CONFIG = confuse.Configuration(appName, __name__)
CONFIG.set(app_config_data)

