import sys
import os

# Ensure project root is on sys.path when running this script directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from services.forecast_service import decode_csv, preprocess, train_and_forecast
    print('IMPORT_OK')
except Exception as e:
    print('IMPORT_FAIL', e)
    sys.exit(1)
