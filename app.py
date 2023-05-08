import requests, json, sys, yaml
import pandas as pd

config = yaml.safe_load(open('config.yml', mode='r'))

def main(prod_run=False):
    # Determine to use test or production collection for Data Lake
    if prod_run:
        collection = config['prod_collection']
    else:
        collection = config['test_collection']
        
    # Get data as a Python obj to be converted to json
    data_items = get_data_items(config['data_source'])
    
    token = auth(config['url'], config['user'], config['pass'])
    
    default_head = get_default_header(collection, token)
    
    populate_data(config['url'], default_head, data_items['data'])
    
def auth(url, user, pwd):
    data = { 'Grant': 'password', 'Username': user, 'Password': pwd }

    # Send a post request to get an access token
    auth_response = requests.post(f"{url}/authenticate", data=data)

    return auth_response.json()['accesstoken']

# Returns Python obj for default header
def get_default_header(collection, token):
    header = { 
        'headers': {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {token}'
        }, 
        'data': {
            "CollectionName": collection,
            "Items": []
        } 
    }
    
    return header

# Iterate through data items to post 100 at a time
def populate_data(url, default_header, data_list): #
    for i in range(0, len(data_list), 100):
        # Get current chunk from data list
        to_submit = data_list[i:i+99]
        
        # Add data items to header data
        default_header['data']['Items'] = to_submit
        
        # Convert headers and data to JSON
        headers = json.dumps(default_header['headers'])
        data = json.dumps(default_header['data'])
        
        # Post data
        requests.post(f"{url}/additems", headers=headers, data=data)
        
def validate_population(url, token, collection, data_items):
    response = requests.post(f"{url}/getcollectiondetails", data={'CollectionName': collection})
    
    # Load collection details response to python object
    collection_details = json.loads(response.json())
    
    # Ensure row counts match
    if collection_details['Count'] != len(data_items['data']):
        return f"Collection Item Count ({collection_details['Count']}) does not match Data Row Count ({len(data_items['data'])})"
    
    # Ensure all fields are present
    for item_field in data_items['fields']:
        match = False
        
        for coll_field in collection_details['Fields']:
            if item_field['Name'] == coll_field['Name']:
                if item_field['Type'] == coll_field['Type']:
                    match = True
                    break
        
        if match != True:
            return f"Not all Item Fields ({item_field}) populated into Collection Fields"
    
    first_row = data_items['data'][0]
    last_row = data_items['data'][len(data_items['data'])-1]
    
    
        
        

            
# Reads excel file, adds unique key, then converts to Python object that can be converted to Data Lake JSON
def get_data_items(file_path):
    df = pd.read_excel(file_path, sheet_name=0)
    
    # Add unique row number key
    df.index = [i for i in range(1, len(df.values)+1)]
    
    # Convert Discounts to float
    df['Discounts'] = df['Discounts'].replace(' $-   ', '0.0', regex=False).astype(float)

    # Convert table to JSON then to Python object
    df_data = json.loads(df.to_json(orient='table'))
    
    # Get primary key from dataframe
    primary_key = df_data['schema']['primaryKey'][0]

    items_list = []
    
    # Iterate through each row of data
    for row in df_data['data']:
        item = { 'Key': '', 'Attributes': [] }
        
        # Iterates through each of the column fields
        for field in df_data['schema']['fields']:
            cell_value = row[field['name']]
            
            # If primary key is the field, populate it in the key portion instead of attributes
            if field['name'] == primary_key:
                item['Key'] = str(cell_value)
                
            else:
                row_data = {
                    'Name': field['name'], 
                    'Type': field['type'],
                    'Value': cell_value
                }
                
                item['Attributes'].append(row_data)
                
        items_list.append(item)
        
    return { 'data': items_list, 'fields': df_data['schema']['fields'] }
    
if __name__ == "__main__":
    prod_run = False 
    
    # Checks if "prod" is in console run arguments, if yes sets prod_run to True
    if len(sys.argv) > 1:
        if sys.argv[1] == 'prod':
            prod_run = True

    main(prod_run)