# %%
import pandas as pd
import glob
import os
import json
from io import StringIO
from datetime import datetime
import re

# %%

folder_path = 'suricata'  


start_time = datetime.now()
print("Start Time:", start_time)


chunks = []
alert_count = 0
max_alerts = 50000  


for file_name in os.listdir(folder_path):
    if file_name.endswith('.json'):
        file_path = os.path.join(folder_path, file_name)
        
        
        with open(file_path, 'r', encoding='utf-8') as file:
            for line in file:
                if alert_count >= max_alerts:
                    break  
                
                try:
                    
                    data = json.loads(line.strip())
                    
                    
                    if data.get('event_type') == 'alert':
                        
                        chunks.append(pd.json_normalize(data))
                        alert_count += 1
                except json.JSONDecodeError:
                    
                    continue


if chunks:
    suricata = pd.concat(chunks, ignore_index=True)
else:
    df = pd.DataFrame()  


print(f"Number of rows: {suricata.shape[0]}")
print(f"Number of columns: {suricata.shape[1]}")


end_time = datetime.now()
print("End Time:", end_time)


elapsed_time = end_time - start_time
print(f"Elapsed Time: {elapsed_time}")


# %%

columns_to_delete = [
    'dns.query', 'alert.metadata.confidence', 'files', 'alert.metadata.former_category',
    'alert.metadata.performance_impact', 'icmp_type', 'icmp_code', 
    'metadata.flowints.http.anomaly.count', 'alert.metadata.cve', 
    'metadata.flowints.tcp.retransmission.count'
]


suricata = suricata.drop(columns=columns_to_delete, errors='ignore')
suricata = suricata.where(pd.notna(suricata), None)


# %%

def remove_emojis(text):
    if isinstance(text, str):
        
        return re.sub(r'[^\w\s-]', '', text)
    else:
        return text  

suricata['alert.signature'] = suricata['alert.signature'].apply(remove_emojis)


# %%

prefixes_to_delete =  ['app', 'http', 'ike', 'ssh', 'smb', 'sip', 'snmp', 'stats', 'tls', 'tcp']

columns_to_delete = [col for col in suricata.columns if any(col.startswith(prefix) for prefix in prefixes_to_delete)]

suricata = suricata.drop(columns=columns_to_delete)


# %%

suricata.loc[:, suricata.dtypes == 'object'] = suricata.loc[:, suricata.dtypes == 'object'].where(pd.notnull(suricata), None)

#print(suricata.isna().sum())  

# %%

def clean_brackets(value):
    if isinstance(value, list):
        
        return ', '.join([re.sub(r'[\[\]]', '', str(item)).strip() for item in value])
    elif isinstance(value, str):
        
        return re.sub(r'[\[\]]', '', value).strip()
    else:
        
        return value


suricata = suricata.apply(lambda col: col.map(clean_brackets) if col.dtypes == 'object' else col)


# %%
import ipaddress


def is_private_ip(ip):
    try:
        
        return ipaddress.ip_address(ip).is_private
    except ValueError:
        return False  


def find_private_ip(row):
    
    if is_private_ip(row['src_ip']):
        return row['src_ip']
    elif is_private_ip(row['dest_ip']):
        return row['dest_ip']
    else:
        return None  


suricata['ipv4'] = suricata.apply(find_private_ip, axis=1)


#print(suricata[['src_ip', 'dest_ip', 'ipv4']])

# %%

suricata['source'] = 'suricata'

suricata = suricata[['source'] + [col for col in suricata.columns if col != 'source']]


# %%



suricata = suricata.copy()


suricata.loc[:, 'entity'] = None
suricata.loc[:, 'entity_type'] = None



suricata.loc[
    suricata['ipv4'].notna() & 
    (suricata['ipv4'] != 'None') & 
    (suricata['ipv4'] != 'nan') & 
    (suricata['ipv4'] != ''),
    'entity'
] = suricata['ipv4']

suricata.loc[
    suricata['ipv4'].notna() & 
    (suricata['ipv4'] != 'None') & 
    (suricata['ipv4'] != 'nan') & 
    (suricata['ipv4'] != ''),
    'entity_type'
] = 'host'



hosts = suricata[suricata['entity_type'] == 'host'][['entity', 'entity_type']].drop_duplicates()


print("The following entities were created:")
print(hosts)



# %%
pd.set_option('display.max_rows', 50)  

unique_combinations = suricata[['entity', 'entity_type']].drop_duplicates().head(50)
unique_combinations = unique_combinations.sort_values(by='entity')

print("The following entities were created (sorted alphabetically by entity, showing up to 50 rows):")
print(unique_combinations)


# %%

null_suricata = suricata[
    suricata['entity'].isna() | 
    suricata['entity_type'].isna() | 
    (suricata['entity'] == 'None') | 
    (suricata['entity_type'] == 'None') | 
    (suricata['entity'] == 'nan') | 
    (suricata['entity_type'] == 'nan')
]


if null_suricata.empty:
    print("There are no unpopulated entities.")
else:
    print("Rows where either 'entity' or 'entity_type' are null, None, or NaN:")
    print(null_suricata)

# %%
unique_suricata = suricata[['entity', 'entity_type', 'ipv4']].drop_duplicates()
unique_suricata.to_csv('entity_table.csv', mode='a', index=False, header=not pd.io.common.file_exists('entity_table.csv'))

print("Unique suricata entities have been written to 'entity_table.csv'.")

# %%

suricata = suricata.rename(columns={
    'flow_id': 'guid',
    'timestamp': 'timestamp',
    'event.kind': 'detection_type',
    'alert.signature': 'name',
    'alert.severity': 'severity',
    'alert.category': 'category',
    'id': 'mitre_tactic',
    'ipv4': 'host_ip',
    'src_ip': 'source_ip',
    'dest_ip': 'dest_ip',
    'dest_port': 'dest_port'
})


# %%

severity_mapping = {1: 'high', 2: 'medium', 3: 'low'}
suricata['severity'] = suricata['severity'].replace(severity_mapping)


# %%

current_time = datetime.now().strftime("%Y%m%d_%H%M%S")

suricata_name = f"suricata_{current_time}"
globals()[suricata_name] = suricata.copy()

output_folder = 'output'
os.makedirs(output_folder, exist_ok=True)

output_file = os.path.join(output_folder, f"{suricata_name}.json")
globals()[suricata_name].to_json(output_file, orient='records', lines=True)

print(f"Generated DataFrame name: {suricata_name}")
print(f"DataFrame has been written to {output_file}")

# %%



