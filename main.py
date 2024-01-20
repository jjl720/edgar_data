import config
from secApi_extractor import  secApi_extract
import traceback
import sys
from json import loads
import json
from claiutils.aws import S3 as s3_utils
from datetime import datetime
import pandas as pd
import claiutils.aws as clai
import boto3

def save_to_s3_sec_url_by_date(json_data,form_type,filing_date,accesion_no,source='sec_api'):

    # Location to save mapped polygon: Bucket + location prefix path all inside the config file
    bucket = config.sec_bucket
    prefix_path = config.sec_prefix_path

    try:
        # filing_date is in timestamp form changing into YYYY-MM-DD
        datetime_obj = datetime.fromisoformat(filing_date)
        date = datetime_obj.strftime('%Y-%m-%d')
    except:
        date = '0000-00-00' # Missing Date

    # Constructs the S3 location structure based on the item filling date
    # Source=edgar/formtype=10-k/filingdate=YYYY-MM-DD/accessionno= cik - year - form court location id
    path = prefix_path+f'source={source}/formtype={form_type}/filingdate={date}/accessionno={accesion_no}'

    # Names the df file based on the batch_id
    key = path+'/'+f'item={json_data["item"]}.json.gz'

    print(f'Saved sec_response in bucket:{bucket} -- file_path:{key}')
    # saves the item as a zip file
    
    s3_utils.zip_and_save_object_s3(key=key, bucket=bucket, object=json.dumps(json_data).encode('utf-8'))
    
    return

def lambda_sec_extractor_queue_batch_requests(event, context):
    """
        Input Variables:
        event = None 
        contect = None

        Required Variables:(config file)
            - config.step_size = How many items to be processed per lambda
            - config.sec_bucket = The bucket the previous processed data for the items documents is located (e.g. clai-symbology-test)
            - config.sec_prefix_path = The prefix of where the files for the document items are located (e.g. type=edgar_mappings/clai-edgar/)
    """

    try:
        # Gets the list all the directory in the Symbology Bucket with the polygon prefix
        # e.g. ['clai-edgar/source=sec_api/formtype=10-K/filingdate=2022-09-01/accessionno=0001185185-22-001052/item=1.json.gz' , ... ]
        processed_items=clai.S3.s3_list_files(config.sec_bucket, directory=config.sec_prefix_path)

        # Parsing processed_items string into a dictionary
        """ 
        The final parsed_data is a dictionary with the forms as keys and another dictionary with the of accession_no as keys and a list of items for each accession_no for each date
        form_type -> accession_no -> [list of items]
        parsed_data = {'10-K': {'0001185185-22-001052': ['1'],
                                '0000896878-22-000028': ['1'],
                                '0000950170-22-018068': ['1'],
                                '0001628280-22-024271': ['1'],
                                '0001327567-22-000028': ['1'],...} ,
                       '10-Q': {...},
                       '8-K': {...}
        """
        parsed_data = {}
        for item in processed_items:
            # Split the string by '/' and then by '=' in the next loop
            """
            Example:
            item = 'clai-edgar/source=sec_api/formtype=10-K/filingdate=2022-12-29/accessionno=0001091818-22-000187/item=1.json.gz'
            key_value_pairs = ['clai-edgar',
                                'source=sec_api',
                                'formtype=10-K',
                                'filingdate=2022-12-29',
                                'accessionno=0001091818-22-000187',
                                'item=1.json.gz']
            """
            key_value_pairs = item.split('/')
            for key_value in key_value_pairs:

                if '=' in key_value: #checks we are in correct portion of the directory with key value pairs
                    if key_value.split('=')[0] == 'formtype': # First dictionary begins with the form_type
                        if key_value.split('=')[1] not in parsed_data.keys(): 
                            # checks if the form_type is a key in the dictionary if not it will create a new key
                            parsed_data[key_value.split('=')[1]] = {} 
                        form = key_value.split('=')[1] #stores the form_type to keep track which form_type directory the iteration is parsing

                    if key_value.split('=')[0] == 'accessionno' and form in parsed_data.keys(): 
                        # the next dictionary with in the form_type is the accession no
                        if key_value.split('=')[1] not in parsed_data[form].keys(): # creates a key for accession no if not in dictionary form already
                            parsed_data[form][key_value.split('=')[1]] = [] # this key pair is an accession no and a list of items for each accession no document
                        accessionno= key_value.split('=')[1]# stores the accession no to keep track which accession no directory the iteration is parsing
                    
                    if key_value.split('=')[0] == 'item' and form in parsed_data.keys() and accessionno in parsed_data[form].keys(): 
                        # This process double checks there the is a key path to the item we are appending to the accession no list
                        if key_value.split('=')[1].replace('.json.gz', '') not in parsed_data[form][accessionno]: 
                            # checks if this item has already processed this incase we processed this multiple times at different run dt
                            parsed_data[form][accessionno].append(key_value.split('=')[1].replace('.json.gz', '')) # the items are stored as json compressed objects but we dont need this information so strip 'json.gz'

        # SQL query to get the url links fillings documents, this data comes from the edgar_mapping process
        sql_query_string = "SELECT DISTINCT(sec.linktotxt) , sec.formtype, sec.accessionno, filedat FROM polygon_edgar AS sec;"

        # Gets a dataframe of the list of edgar mappings: the url link, form_type, accession no, filling date
        df_secApiUrls = clai.query(sql_string=sql_query_string, database="clai") 

        # Initialize the queue_list results to be appended later
        queue_list = []

        def diff_items(row):
            # This function will be used to check what items have been processed for each form and accession_no
            # and which forms need to be processed from the config.items_extract
            if row["formtype"] in config.items_extract.keys(): # Checks if the form_type in the dataframe is a key in the items to be extracted
                if row["formtype"] in parsed_data.keys() and row['accessionno'] in parsed_data[row["formtype"]].keys():
                    # This boolean checks if the accession no matches any accession no that has been processed
                    # If the accession no matches the processed accession no then we can check which items have been processed from the items_extract
                    return tuple(set(config.items_extract[row["formtype"]]) - set(parsed_data[row["formtype"]][row['accessionno']]))
                else:
                    # If accession no has not been processed before we process all the items from the items_extract
                    return tuple(config.items_extract[row["formtype"]])
            else:
                # No items to be processed for this form type
                return ()


        df_secApiUrls['item']=df_secApiUrls.apply(diff_items, axis=1) # runs the diff_items to find what needs to be processed
        df_secApiUrls=df_secApiUrls[df_secApiUrls['item'] != ()] # Filters the dataframe to keep only documents rows that require to be processed
        df_secApiUrls = df_secApiUrls.explode('item').reset_index(drop=True) # Expands the dataframe to keep each document as their own individual row and reset the index
        
        # Reorient the df results for map state in step function
        queue_list.extend(json.loads(df_secApiUrls.to_json(orient='records')))

        step_size = config.step_size 
        # Batch of 500 URL per lambda function, this is the batch size preprocessing step
        nested_queue_list = [queue_list[i:i+step_size] for i in range(0, len(queue_list), step_size)]
        #output result
        """
        {'batch_requests': [ [{'linktotxt': 'https://www.sec.gov/Archives/edgar/data/1616788/000149315222027230/0001493152-22-027230.txt',
                              'formtype': '10-K',
                              'item':"1",
                              'accessionno': '0001493152-22-027230',
                              'filedat': '2022-09-30T13:18:02-04:00'
                              response: '},
                            ... ,
                              {'linktotxt': 'https://www.sec.gov/Archives/edgar/data/23197/000002319722000068/0000023197-22-000068.txt',
                               'formtype': '10-K',
                               'item':"1",
                               'accessionno': '0000023197-22-000068',
                               'filedat': '2022-09-29T16:12:36-04:00'}],
                             [{'linktotxt': 'https://www.sec.gov/Archives/edgar/data/1687065/000147793222007306/0001477932-22-007306.txt',
                               'formtype': '10-K',
                               'item':"1",
                               'accessionno': '0001477932-22-007306',
                               'filedat': '2022-09-29T06:02:18-04:00'},
                            ... ,
                             {'linktotxt': 'https://www.sec.gov/Archives/edgar/data/1021096/000162828022025641/0001628280-22-025641.txt',
                              'formtype': '10-K',
                              'item':"1",
                              'accessionno': '0001628280-22-025641',
                              'filedat': '2022-09-28T17:16:13-04:00'} ] ,
                            ...
        """
        
        output = {'batch_requests': nested_queue_list}

        print('Number of URLs to process:', len(nested_queue_list),
              'Number of Batches:', len(nested_queue_list))
        
        return output
    
    except:     
        # Catch errors and prints into cloudwatch
        output = {'batch_requests': []}
        print('Error no lambda monthly queue builder failed', output)
        return output

def  lambda_sec_extractor_batch_requests(event, context):
    try:
        while len(event) != 0:
            current_event = event.pop() # pop one item of the queue
            try:
                # This variable will change value and make the stack smaller saving space
                print (f'extractor_item1 - processing request -- formType:{current_event["formtype"]} -- section:{current_event["item"]} -- accessionno:{current_event["accessionno"]} --  url_link:{current_event["linktotxt"]} ')

                # extracts item1 from 10k using the link
                current_event['item'] = secApi_extract(filling_url=current_event['linktotxt'],section=current_event['item'])
            
                # save to s3 using the save function:
                save_to_s3_sec_url_by_date(current_event,
                                            current_event['formtype'],
                                            current_event['filedat'],
                                        current_event['accessionno'])

                out_msg = {
                            'statusCode': 200,
                            'accession_no':current_event['accessionno'],
                            'response_len':len(current_event['item1']),
                            'form_type': current_event['formtype'],
                            'form_link':current_event['linktotxt']
                        }
            except:
                out_msg = {
                            'statusCode': 'failed',
                            'accession_no':current_event['accessionno'],
                            'response_len':len(current_event['item1']),
                            'form_type': current_event['formtype'],
                            'form_link':current_event['linktotxt']
                        }
                
            print(out_msg)
            
        return 'Completed batch request'

    except Exception as e:
     
        additional_information = f'error processing event: {event}\n'
        output = f'{additional_information} -- traceback:{str(traceback.format_exc())} \n error:{str(e)}'
        print(f"Lambda function encountered an error: {output}")
        return "Failed to run batch"




