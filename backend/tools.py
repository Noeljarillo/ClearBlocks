import requests
from dotenv import load_dotenv
import os
from psycopg2 import sql
import psycopg2

import pandas as pd
load_dotenv()

etherscan_api_key = os.getenv("ETHERSCAN_API_KEY")
api_key = os.getenv("OPENAI_API_KEY")

classifier_promt = """You are an assistant that only returns one of this words as input and nothing else [SOF, UOF, PORTFOLIO, NONE]

Your task is to classify the user intention into one of the categories

SOF Source of funds, the users wants to understand the source of the funds of an address, for example to understand risk, or compliance.

UOF usage of funds, for example to understand how one address or more used an airdrop, or how a hacker that stole funds is using them now, or the usage of grants 

PORTFOLIO information about an address, balance of native token, erc 20 tokens, positions like providing liquidity, or doing lending.

if it does not much one and only one of the categories return none


Input message:"""

get_token_prompt = """You are a helpful asitant your task is to extract the token from the user request,
if the user does not provide a token return none, the token can be STRK, BASE, ETH, USDC, or none nothing else"""

metrics_prompt = """
You are an assistant, you are given a data request you should suggest metrics that would be useful to answer the request

metrcics can only be from the following list:

- name:transactionsOutGraphByAddress -exaplanation: a graph of the transactions out of an address
- name:transactionsOutValueByAddressBytoken -explanattion: a list of the transactions out values of an address by token
- name:transactionsInValueByAddressBytoken -explanattion: a list of the transactions in values of an address by token
- name:averageTransactionSize -explanattion: the average size of the transactions of an address
- name:mostUsedDestinationAddress -explanattion: the most used destination address of an address

you can only return the metric name, nothing else
"""
get_address = """Your task is to get the eth or stark address from the user request, 
if the user does not provide an address return none, eth address starts with 0x and stark address starts with
 0x too, only return the address, or none nothing else"""

get_network = """Your task is to get the network of the chain from the user request,
 if the user does not provide a network return none,eth can be refered as eth mainnet,
   or similar, be sure to not confuse token names with the network, 
   the network can be base, starknet, or eth, only return the network, or none nothing else"""

# New prompt for extracting block numbers
block_numbers_prompt = """Your task is to extract the starting and ending block numbers from the user request. If the user provides block numbers, return them separated by a comma with no spaces (e.g., "1000,2000"). If not provided, return "none"."""

def what_token(input):
    entry = gpt4miniCall(api_key, get_token_prompt, input, max_tokens=5)
    return entry

def what_flow(input):
    entry = gpt4miniCall(api_key, classifier_promt, input, max_tokens=5)

    # Normalize the entry for comparison
    normalized_entry = entry.strip().upper() if entry else ""
    print("Debug: Normalized entry:", normalized_entry)  # Debug log

    if normalized_entry == "SOF":
        return "SOF"
    elif entry == "UOF":
        return "UOF"
    elif entry == "PORTFOLIO":
        return "PORTFOLIO"
    else:
        return None

def what_network(input):
    network = gpt4miniCall(api_key, get_network, input, max_tokens=5)
    return network

def uof_flow(address, token, network, start_block, end_block):
    # Added guard: ensure block numbers are provided
    if start_block is None or end_block is None:
        raise ValueError("start_block and end_block must be provided for UOF analysis.")
    
    # Ensure block range is in correct order
    if start_block > end_block:
        start_block, end_block = end_block, start_block
    
    # For starknet, map token name to actual contract address
    if network.lower() == "starknet":
        stark_token_mapping = {
            "STRK": "0x04718f5a0fc34cc1af16a1cdee98ffb20c31f5cd61d6ab07201858f4287c938d" 
        }
        token_address = stark_token_mapping.get(token.upper(), token)
        df = get_transfers_stark(token_address, address, start_block, end_block)
    else:
        df = get_transfers_stark(token, address, start_block, end_block)
    
    if df.empty:
        return "No transfer events found in the specified block range."
    
    import matplotlib
    matplotlib.use('Agg')  # Set the backend before importing pyplot
    import matplotlib.pyplot as plt
    import networkx as nx
    import io, base64
    
    # Filter transfers to only include those where target address is sender or receiver
    df_filtered = df[
        (df['from_address'] == address) | 
        (df['to_address'] == address)
    ].copy()
    
    # Build a directed graph from the filtered transfer events
    G = nx.DiGraph()
    
    # Create a mapping for node labels
    def get_node_label(addr):
        return 'TARGET' if addr == address else (addr[:10] + '...')
    
    node_labels = {}  # Store consistent labels for nodes
    
    # Add edges with weights (amounts)
    for _, row in df_filtered.iterrows():
        from_addr = row['from_address']
        to_addr = row['to_address']
        amount = float(row['size'])
        
        # Get consistent labels for nodes
        from_label = get_node_label(from_addr)
        to_label = get_node_label(to_addr)
        
        # Store the labels
        node_labels[from_addr] = from_label
        node_labels[to_addr] = to_label
        
        if G.has_edge(from_label, to_label):
            G[from_label][to_label]['weight'] += amount
        else:
            G.add_edge(from_label, to_label, weight=amount)
    
    # Create the figure using Agg backend
    plt.figure(figsize=(12, 8))
    pos = nx.spring_layout(G, k=2, iterations=50)
    
    # Draw the graph with improved aesthetics
    node_colors = ['red' if node == 'TARGET' else 'lightblue' for node in G.nodes()]
    nx.draw_networkx_nodes(G, pos, 
                          node_color=node_colors,
                          node_size=2000,
                          alpha=0.7)
    nx.draw_networkx_edges(G, pos,
                          edge_color='gray',
                          width=2,
                          arrowsize=20)
    
    # Add labels with better formatting
    nx.draw_networkx_labels(G, pos, font_size=8)
    edge_labels = nx.get_edge_attributes(G, 'weight')
    edge_labels = {k: f'{v:.4f}' for k, v in edge_labels.items()}
    nx.draw_networkx_edge_labels(G, pos, edge_labels, font_size=8)
    
    plt.title(f'Token Transfers ({token}) - Blocks {start_block} to {end_block}')
    
    # Save the plot to a PNG image in memory and encode as base64
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=300, bbox_inches='tight')
    plt.close()
    buf.seek(0)
    img_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')
    md_image = f"![UOF Graph](data:image/png;base64,{img_base64})"
    
    return (f"Usage of Funds analysis complete for address {address} using token {token} on {network} network from block {start_block} to {end_block}.\n" + md_image)

def sof_flow(context):
    pass

def portfolio_flow(address):
    try:
        df_normal, df_erc20, balance = get_eth_address_info(address)
        normal_transactions = []
        if not df_normal.empty:
            normal_transactions = df_normal.head(5).to_dict(orient='records')
        erc20_transfers = []
        if not df_erc20.empty:
            erc20_transfers = df_erc20.head(5).to_dict(orient='records')
        
        return {
            "ethBalance": round(balance, 4),
            "normalTransactions": normal_transactions,
            "erc20Transfers": erc20_transfers
        }
    except Exception as e:
        return {"error": str(e)}



def gpt4miniCall(api_key, system_prompt, user_message, max_tokens=10):
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "gpt-4-turbo-preview",
        "messages": [
            {"role": "system", "content": system_prompt},  # Preprompt
            {"role": "user", "content": user_message}  # User message
        ],
        "temperature": 0.7,
        "max_tokens": max_tokens
    }

    response = requests.post(url, json=payload, headers=headers)

    if response.status_code == 200:
        return response.json()["choices"][0]["message"]["content"]
    else:
        return f"Error {response.status_code}: {response.text}"






###get functions and db
def get_uof_graph(token_address, addres, network, start_block, end_block):
    if network == "starknet":
        get_transfers_stark(token_address, address, start_block, end_block)

    return df2




def get_address_transactions(schema, table_name, address, inout):


    conn = get_connection()
    
    query = sql.SQL(f"""
        SELECT block, to_address, from_address, size, hash
        FROM {schema}."{table_name}"
        WHERE {inout}_address = %s
        ORDER BY block ASC;
    """)

    df = pd.read_sql_query(query.as_string(conn), conn, params=(address,))

    conn.close()

    return df
        
DB_PARAMS = {
    "dbname": "mydatabase",    
    "user": "myuser",          
    "password": "mypassword",  
    "host": "localhost",       
    "port": 5432               
}
def get_connection():
    """Establish and return a new database connection."""
    return psycopg2.connect(**DB_PARAMS)

def create_schema(schema):

    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                query = sql.SQL("CREATE SCHEMA IF NOT EXISTS {schema}")
                cur.execute(query.format(schema=sql.Identifier(schema)))
                print(f"Schema '{schema}' created or already exists.")
    finally:
        conn.close()

def create_token_table(schema, token):

    conn = get_connection()
    table_name = token.lower()  # For example, "ETH" becomes "eth"
    try:
        with conn:
            with conn.cursor() as cur:
                query = sql.SQL("""
                    CREATE TABLE IF NOT EXISTS {schema}.{table} (
                        block INTEGER NOT NULL,
                        to_address TEXT NOT NULL,
                        from_address TEXT NOT NULL,
                        size NUMERIC,
                        hash TEXT NOT NULL UNIQUE
                    );
                """).format(
                    schema=sql.Identifier(schema),
                    table=sql.Identifier(table_name)
                )
                cur.execute(query)
                print(f"Table '{table_name}' created in schema '{schema}'.")
    finally:
        conn.close()

def insert_token_event(schema, token, block, to_address, from_address, size, hash_val):


    conn = get_connection()
    table_name = token.lower()
    try:
        with conn:
            with conn.cursor() as cur:
                query = sql.SQL("""
                    INSERT INTO {schema}.{table} (block, to_address, from_address, size, hash)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (hash) DO NOTHING;
                """).format(
                    schema=sql.Identifier(schema),
                    table=sql.Identifier(table_name)
                )
                cur.execute(query, (block, to_address, from_address, size, hash_val))
                print(f"Inserted event into table '{table_name}' in schema '{schema}'.")
    finally:
        conn.close()


def exists_blocks(schema, token, start_block, end_block):

    conn = get_connection()
    table_name = token.lower()
    try:
        with conn.cursor() as cur:
            query = sql.SQL("""
                SELECT DISTINCT block
                FROM {schema}.{table}
                WHERE block BETWEEN %s AND %s;
            """).format(
                schema=sql.Identifier(schema),
                table=sql.Identifier(table_name)
            )
            cur.execute(query, (start_block, end_block))
            # Get the set of block numbers that exist in the DB.
            existing_blocks = {row[0] for row in cur.fetchall()}
            
            # Create the set of all expected block numbers.
            expected_blocks = set(range(start_block, end_block + 1))
            missing = sorted(list(expected_blocks - existing_blocks))
            return len(missing) == 0, missing
    finally:
        conn.close()


def get_transfers_stark(token_address, address, start_block, end_block):
    host = "https://starknet-mainnet.public.blastapi.io/rpc/v0_7"
    JUNO_RPC_URL = host
    
    payload = {
        "jsonrpc": "2.0",
        "method": "starknet_getEvents",
        "params": {
            "filter": {
                "from_block": {"block_number": start_block},
                "to_block": {"block_number": end_block},
                "address": token_address,
                "keys": [
                    ["0x99cd8bde557814842a3121e8ddfd433a539b8c9f14bf31ebf108d12e6196e9"]
                ],
                "chunk_size": 500
            }
        },
        "id": 1
    }
    
    all_events = []
    response = requests.post(JUNO_RPC_URL, json=payload)
    data = response.json()
    
    # Debug print
    print("API Response:", data)
    
    result = data.get("result", {})
    all_events.extend(result.get("events", []))
    continuation_token = result.get("continuation_token")
    
    while continuation_token:
        payload["params"]["filter"]["continuation_token"] = continuation_token
        payload["id"] += 1
        response = requests.post(JUNO_RPC_URL, json=payload)
        data = response.json()
        result = data.get("result", {})
        all_events.extend(result.get("events", []))
        continuation_token = result.get("continuation_token")

    # Debug print
    if all_events:
        print("Sample event:", all_events[0])

    formatted_events = []
    for event in all_events:
        d = event.get("data", [])
        if len(d) >= 3:
            event_dict = {
                "from_address": d[0],
                "to_address": d[1],
                "size": float(int(d[2], 16) / (10 ** 18)),
                "block": int(event.get("block_number", 0)),
                "hash": event.get("transaction_hash")
            }
            formatted_events.append(event_dict)
    
    # Debug print
    if formatted_events:
        print("Sample formatted event:", formatted_events[0])
    
    df = pd.DataFrame(formatted_events)
    
    # Debug print
    print("DataFrame columns:", df.columns.tolist())
    print("DataFrame head:", df.head())
    
    return df

def get_and_insert_transfers(token_address, network, start_block, end_block):
    if network == "starknet":
        create_schema(network)
        create_token_table(network, token_address)
        table_name = token_address.lower()
        
        df = get_transfers_stark(token_address, "address", start_block, end_block)
        
        if df.empty:
            print("No events found in the specified block range")
            return
            
        # Make sure all required columns exist
        required_columns = ['block', 'to_address', 'from_address', 'size', 'hash']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise ValueError(f"Missing required columns: {missing_columns}")
        
        df = df.sort_values(by='block')
        
        for _, row in df.iterrows():
            try:
                insert_token_event(
                    network,
                    table_name,
                    row['block'],
                    row['to_address'],
                    row['from_address'],
                    row['size'],
                    row['hash']
                )
            except Exception as e:
                print(f"Error inserting row: {row}")
                print(f"Error message: {str(e)}")
    else:
        pass

def format_graph_for_frontend(G):
    nodes = []
    links = []
    
    # Calculate node sizes based on total transaction value
    node_total_value = {}
    for node in G.nodes():
        total = sum(data['value'] for _, _, data in G.out_edges(node, data=True))
        node_total_value[node] = total
        nodes.append({
            "id": node,
            "size": 300 + 1000 * total  # Base size + scale factor * total ETH
        })
    
    # Format edges/links
    for u, v, data in G.edges(data=True):
        if data['value'] >= 0.001:  # Filter small transactions
            links.append({
                "source": u,
                "target": v,
                "value": data['value'],
                "timestamp": data.get('timestamp', 0)
            })
    
    return {
        "nodes": nodes,
        "links": links
    }

def what_block_numbers(input):
    entry = gpt4miniCall(api_key, block_numbers_prompt, input, max_tokens=20)
    return entry


def get_balance_eth(address):
    url = f"https://api.etherscan.io/api?module=account&action=balance&address={address}&tag=latest&apikey={etherscan_api_key}"

    eth = requests.get(url).json()["result"]
    eth = float(eth) / (10 ** 18)
    return eth
def get_tx_by_address(address):
    url = f"https://api.etherscan.io/api?module=account&action=txlist&address={address}&startblock=0&endblock=99999999&page=1&offset=5&sort=desc&apikey={etherscan_api_key}"
    return pd.DataFrame(requests.get(url).json()["result"])[['timeStamp', 'from', 'to', 'value', 'hash']]

def erc20_transfers(address):
    url = f"https://api.etherscan.io/api?module=account&action=tokentx&address={address}&startblock=0&endblock=99999999&page=1&offset=5&sort=desc&apikey={etherscan_api_key}"
    return pd.DataFrame(requests.get(url).json()["result"])[['timeStamp', 'from', 'to', 'tokenName', 'value', 'tokenSymbol']]


def get_eth_address_info(address):
    df1 = get_tx_by_address(address)
    df2 = erc20_transfers(address)
    balance = get_balance_eth(address)
    return df1, df2, balance