import pandas as pd
import requests
import json
import time
from datetime import datetime
import config
import calendar


def secApi_extract(filling_url,section=None, attempt=1, max_attempt=5):
    if attempt > max_attempt:
        return ''
    
    secApi_key = config.SecApi.sec_api_key
    secApi_root_url = config.SecApi.sec_api_root

    secApi_api_endpoint = secApi_root_url + f'url={filling_url}&item={section}&type=text&token={secApi_key}'
  
    response = requests.get(secApi_api_endpoint)

    print(f'response code {response.status_code} -- attempt:{attempt} -- filling_url: {filling_url}')

    if response.status_code !=200:
        time.sleep(2**attempt)
        response_text = secApi_extract(filling_url,section=section, attempt=attempt+1, max_attempt=5)
    else:
        response_text = response.text

    return response_text

"""
filling_url = "https://www.sec.gov/Archives/edgar/data/1822792/000121390022060673/0001213900-22-060673.txt"
section="1"
result =secApi_extract(filling_url,section=section, attempt=1, max_attempt=5)
print("print: ",result)

filling_url_fail = "fail_fail_fail_url.txt"
section="1A"
result =secApi_extract(filling_url_fail,section=section, attempt=1, max_attempt=5)
print("print: ",result)
"""