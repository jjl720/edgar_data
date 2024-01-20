import os
from datetime import datetime,timezone
from dotenv import load_dotenv

load_dotenv()

sec_bucket = 'clai-symbology-test'

sec_prefix_path = 'clai-edgar/'

sec_prefix_path_by_cik = 'type=edgar_mappings_by_cik/'

#choose which sections or items to extract
#dictionanry with form types and list
items_extract = {'10-K': ['1','1A','3','7','7A'],
                 '10-Q' : ['part1item2','part1item3','part2item1','part2item1a'],
                 '8-K' : ['2-2','2-6','8-1']
                 }

step_size = 500 # how many document items to download per lambda.

run_id = f'{datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")}'
run_date = f'{datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")}'
class SecApi:
    sec_api_key = os.environ.get('SEC_API_KEY')
    sec_api_root = "https://api.sec-api.io/extractor?"

class Aws:
    S3_REGION_NAME = 'us-west-2'
    S3_OBJECT_ROOT = 'https://s3.console.aws.amazon.com/s3/object'
    
    AWS_KEY = os.environ.get('AWS_KEY')
    AWS_SECRET = os.environ.get('AWS_SECRET')

