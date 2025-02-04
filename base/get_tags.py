import requests
import json

base_url = 'https://eth-labels-production.up.railway.app'

def fetch_data(endpoint):
    url = f'{base_url}{endpoint}'
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    else:
        print(f'Failed to fetch data from {endpoint}. Status code: {response.status_code}')
        return None

tokens_data = fetch_data('/tokens')
if tokens_data:
    with open('tokens.json', 'w') as tokens_file:
        json.dump(tokens_data, tokens_file, indent=4)
    print('Tokens data saved to tokens.json')

accounts_data = fetch_data('/accounts')
if accounts_data:
    with open('accounts.json', 'w') as accounts_file:
        json.dump(accounts_data, accounts_file, indent=4)
    print('Accounts data saved to accounts.json')