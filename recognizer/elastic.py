
from datetime import datetime
import pandas as pd
import glob
import os
import json
import re


# %%
def process_all_json_files(directory_path):
    all_dfs = []


    for file_name in os.listdir(directory_path):
        if file_name.endswith('.json'):
            file_path = os.path.join(directory_path, file_name)
            

            with open(file_path, 'r') as file:
                data = json.load(file)


            if isinstance(data, list):
                records = data
            else:
                records = data.get('Records', [])


            df = pd.json_normalize(records)
            all_dfs.append(df)


    combined_df = pd.concat(all_dfs, ignore_index=True)
    return combined_df


directory_path = 'elastic'  
df = process_all_json_files(directory_path)



# %%
df.columns = df.columns.str.replace(r'^_source\.*', '', regex=True)
df.columns = df.columns.str.lstrip('_')

df = df.where(pd.notna(df), None)
elastic = df.copy()

def clean_brackets(value):
    if isinstance(value, list):

        return ', '.join([re.sub(r'[\[\]]', '', str(item)).strip() for item in value])
    elif isinstance(value, str):

        return re.sub(r'[\[\]]', '', value).strip()
    else:

        return value


elastic['event.category'] = elastic['event.category'].apply(clean_brackets)
elastic['host.name'] = elastic['host.name'].apply(clean_brackets)
elastic['user.name'] = elastic['user.name'].apply(clean_brackets)
elastic['source.ip'] = elastic['source.ip'].apply(clean_brackets)
elastic['destination.ip'] = elastic['destination.ip'].apply(clean_brackets)


# %%

def extract_ipv6(ip_list):
    ipv6_pattern = re.compile(
        r"^([0-9a-fA-F]{1,4}:){7,7}[0-9a-fA-F]{1,4}|"
        r"([0-9a-fA-F]{1,4}:){1,7}:|"
        r"([0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}|"
        r"([0-9a-fA-F]{1,4}:){1,5}(:[0-9a-fA-F]{1,4}){1,2}|"
        r"([0-9a-fA-F]{1,4}:){1,4}(:[0-9a-fA-F]{1,4}){1,3}|"
        r"([0-9a-fA-F]{1,4}:){1,3}(:[0-9a-fA-F]{1,4}){1,4}|"
        r"([0-9a-fA-F]{1,4}:){1,2}(:[0-9a-fA-F]{1,4}){1,5}|"
        r"[0-9a-fA-F]{1,4}:((:[0-9a-fA-F]{1,4}){1,6})|"
        r":((:[0-9a-fA-F]{1,4}){1,7}|:)|"
        r"fe80:(:[0-9a-fA-F]{0,4}){0,4}%[0-9a-zA-Z]{1,}|"
        r"::(ffff(:0{1,4}){0,1}:){0,1}"
        r"(([0-9]{1,3}\.){3,3}[0-9]{1,3})|"
        r"([0-9a-fA-F]{1,4}:){1,4}:([0-9]{1,3}\.){3,3}[0-9]{1,3}$"
    )

    
    for ip in ip_list:
        if ipv6_pattern.match(ip):
            return ip
    return None


elastic['ipv6'] = elastic['host.ip'].apply(lambda x: extract_ipv6(x) if isinstance(x, list) else None)
unique_6 = elastic[['ipv6']].drop_duplicates()
print("the following v6 IPs were populated in the ipv6 field:")
print(unique_6)

# %%

def extract_private_ipv4(ip_list):
    private_ip_pattern = re.compile(
        r"^(10\.\d{1,3}\.\d{1,3}\.\d{1,3}|"
        r"172\.(1[6-9]|2[0-9]|3[0-1])\.\d{1,3}\.\d{1,3}|"
        r"192\.168\.\d{1,3}\.\d{1,3})$"
    )
    
    
    for ip in ip_list:
        if private_ip_pattern.match(ip):
            return ip
    return None
pd.set_option('display.max_rows', 5)

elastic['ipv4'] = elastic['host.ip'].apply(lambda x: extract_private_ipv4(x) if isinstance(x, list) else None)
unique_4 = elastic[['ipv4']].drop_duplicates()
print("the following IPs were populated in the ipv4 field:")
print(unique_4)

# %%


def find_private_ipv4(ip_data):
    
    private_ip_pattern = re.compile(
        r"^(10\.\d{1,3}\.\d{1,3}\.\d{1,3}|"
        r"172\.(1[6-9]|2[0-9]|3[0-1])\.\d{1,3}\.\d{1,3}|"
        r"192\.168\.\d{1,3}\.\d{1,3})$"
    )
    
    
    if isinstance(ip_data, list):
        for ip in ip_data:
            if private_ip_pattern.match(ip):
                return ip
    
    elif isinstance(ip_data, str):
        if private_ip_pattern.match(ip_data):
            return ip_data
    return None


elastic['ipv4'] = elastic.apply(
    lambda row: (find_private_ipv4(row['source.ip']) or find_private_ipv4(row['destination.ip']))
    if pd.isna(row['ipv4']) and pd.isna(row['ipv6']) else row['ipv4'],
    axis=1
)
unique_4 = elastic[['ipv4']].drop_duplicates()
print("the following IPs were populated in the ipv4 field:")
print(unique_4)


# %%

elastic['entity'] = None
elastic['entity_type'] = None

elastic.loc[
    elastic['host.name'].notna() & 
    (elastic['host.name'] != 'None') & 
    (elastic['host.name'] != 'nan') & 
    (elastic['host.name'] != ''),
    'entity'
] = elastic['host.name']

elastic.loc[
    elastic['host.name'].notna() & 
    (elastic['host.name'] != 'None') & 
    (elastic['host.name'] != 'nan') & 
    (elastic['host.name'] != ''),
    'entity_type'
] = 'endpoint'

endpoints = elastic[elastic['entity_type'] == 'endpoint'][['entity', 'entity_type']].drop_duplicates()

print("The following entities were created:")
print(endpoints)

# %%

elastic.loc[
    
    (elastic['host.name'].isna() | (elastic['host.name'] == 'None') | (elastic['host.name'] == 'nan')) & 
    elastic['user.name'].notna() & 
    (elastic['user.name'] != 'None') & 
    (elastic['user.name'] != 'nan') & 
    (elastic['user.name'] != ''),
    'entity'
] = elastic['user.name']

elastic.loc[
    
    (elastic['host.name'].isna() | (elastic['host.name'] == 'None') | (elastic['host.name'] == 'nan')) & 
    elastic['user.name'].notna() & 
    (elastic['user.name'] != 'None') & 
    (elastic['user.name'] != 'nan') & 
    (elastic['user.name'] != ''),
    'entity_type'] = 'user'

users = elastic[elastic['entity_type'] == 'user'][['entity', 'entity_type']].drop_duplicates()

print("The following user entities were created:")
print(users)

# %%

elastic.loc[
    elastic['host.name'].isna() & 
    elastic['user.name'].isna() & 
    elastic['ipv4'].notna(), 
    'entity'] = elastic['ipv4']

elastic.loc[
    elastic['host.name'].isna() & 
    elastic['user.name'].isna() & 
    elastic['ipv4'].notna(), 
    'entity_type'] = 'host'

hosts = elastic[elastic['entity_type'] == 'host'][['entity', 'entity_type']].drop_duplicates()

print("The following host entities were created:")
print(hosts)

# %%

pd.set_option('display.max_rows', 50)  

unique_combinations = elastic[['entity', 'entity_type']].drop_duplicates().head(50)
unique_combinations = unique_combinations.sort_values(by='entity')

print("The following entities were created (sorted alphabetically by entity, showing up to 50 rows):")
print(unique_combinations)


# %%

null_elastic = elastic[
    elastic['entity'].isna() | 
    elastic['entity_type'].isna() | 
    (elastic['entity'] == 'None') | 
    (elastic['entity_type'] == 'None') | 
    (elastic['entity'] == 'nan') | 
    (elastic['entity_type'] == 'nan')
]


if null_elastic.empty:
    print("There are no unpopulated entities.")
else:
    print("Rows where either 'entity' or 'entity_type' are null, None, or NaN:")
    print(null_elastic)

# %%

elastic['host.ip'] = elastic['host.ip'].apply(lambda x: str(x) if isinstance(x, list) else x)
elastic['ipv4'] = elastic['ipv4'].apply(lambda x: str(x) if isinstance(x, list) else x)
elastic['ipv6'] = elastic['ipv6'].apply(lambda x: str(x) if isinstance(x, list) else x)

unique_elastic = elastic[['entity', 'entity_type', 'host.ip', 'host.name', 'ipv4', 'ipv6', 'user.name']].drop_duplicates()
unique_elastic.to_csv('entity_table.csv', mode='a', index=False, header=not pd.io.common.file_exists('entity_table.csv'))

print("Unique elastic entities have been written to the entity table")


# %%

elastic = elastic.rename(columns={
    'id': 'guid',
    '@timestamp': 'timestamp',
    'event.kind': 'detection_type',
    'kibana.alert.rule.name': 'name',
    #'id': 'severity',
    'event.category': 'category',
    #'id': 'mitre_tactic',
    'ipv4': 'host_ip',
    'source.ip': 'source_ip',
    'destination.ip': 'dest_ip',
    'destination.port': 'dest_port',
    #'timestamp': 'dst_geo'
    'user.name': 'username',
    'event.category': 'syscall_name',
    'process.executable': 'executable',
    'process.name': 'process'
    #'id': 'message',
    #'timestamp': 'proctitle'
})



# %%

elastic['source'] = 'elastic'
elastic = elastic[['source'] + [col for col in elastic.columns if col != 'source']]


# %%

current_time = datetime.now().strftime("%Y%m%d_%H%M%S")

df_name = f"elastic_{current_time}"

globals()[df_name] = elastic.copy()

output_folder = 'output'
os.makedirs(output_folder, exist_ok=True)

output_file = os.path.join(output_folder, f"{df_name}.json")
globals()[df_name].to_json(output_file, orient='records', lines=True)

print(f"Generated DataFrame name: {df_name}")
print(f"DataFrame has been written to {output_file}")


# %%



