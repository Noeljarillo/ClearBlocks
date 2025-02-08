import networkx as nx

# Create a directed graph for blockchain transfers
G = nx.DiGraph()

def add_transfer(from_address, to_address, amount, token, transaction_hash, block_number):
    # Ensure nodes exist
    if not G.has_node(from_address):
        G.add_node(from_address, address=from_address)
    if not G.has_node(to_address):
        G.add_node(to_address, address=to_address)
    # Add an edge representing the transfer
    G.add_edge(
        from_address,
        to_address,
        amount=amount,
        token=token,
        transaction_hash=transaction_hash,
        block_number=block_number
    )

# Sample data: add a couple of transfers
add_transfer("0xABCDEF123", "0x123456789", 1.5, "ETH", "0xTXHASH001", 1500000)
add_transfer("0x123456789", "0xFEDCBA987", 0.75, "ETH", "0xTXHASH002", 1500010)

def check_address_exists(address):
    return G.has_node(address)

def query_address_transfers(address):
    # Returns all outgoing transfers for the address
    if not check_address_exists(address):
        return None
    return list(G.out_edges(address, data=True))

# Example usage:
address = "0xABCDEF123"
if check_address_exists(address):
    transfers = query_address_transfers(address)
    print(f"Transfers from {address}:")
    for from_addr, to_addr, data in transfers:
        print(f"  -> To: {to_addr}, Amount: {data['amount']} {data['token']}, TX: {data['transaction_hash']}")
else:
    print(f"Address {address} not found in the graph. Please provide additional data to add it.")