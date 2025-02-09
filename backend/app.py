from flask import Flask, request, Response, stream_with_context, jsonify
from flask_cors import CORS
import json
import time
from tools import what_flow, sof_flow, portfolio_flow, what_network, what_token, what_block_numbers, uof_flow
import re

app = Flask(__name__)
CORS(app)

# Global context to store conversation history and state
class ConversationContext:
    def __init__(self):
        self.messages = []
        self.current_state = "WELCOME"
        self.current_flow = None
        self.collected_params = {}
        self.pending_param = None
        self.db_list = []
        self.data_context = {}
        self.visual_context = {}
        
    def add_message(self, role: str, content: str):
        self.messages.append({"role": role, "content": content})
    
    def get_messages(self):
        return self.messages
    
    def reset(self):
        self.current_state = "WELCOME"
        self.current_flow = None
        self.collected_params = {}
        self.pending_param = None

# Define required parameters for each flow type
FLOW_PARAMS = {
    "UOF": {
        "address": "Please provide the address you want to analyze",
        "token": "Which token would you like to track? (e.g., ETH, USDC, USDT)",
        "network": "Which network would you like to use? (Base, Starknet, or ETH Mainnet)",
        "start_block": "Please provide the starting block number for the analysis",
        "end_block": "Please provide the ending block number for the analysis"
    },
    "SOF": {
        "address": "Please provide the address you want to analyze",
        "network": "Which network would you like to use? (Base, Starknet, or ETH Mainnet)"
    },
    "PORTFOLIO": {
        "address": "Please provide the address you want to analyze",
        "network": "Which network would you like to use? (Base, Starknet, or ETH Mainnet)"
    }
}

context = ConversationContext()

def send_response(text: str, stream: bool = True):
    """Helper function to send responses"""
    context.add_message("assistant", text)
    
    if not stream:
        return jsonify({"choices": [{"message": {"content": text}}]})
    
    def generate():
        tokens = text.split()
        for token in tokens:
            payload = {
                "choices": [{"delta": {"content": token + " "}}]
            }
            yield f"data: {json.dumps(payload)}\n\n"
            time.sleep(0.1)
        yield "data: [DONE]\n\n"
    
    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={'Content-Type': 'text/event-stream'}
    )

def extract_address(message: str) -> str:
    """Extract Ethereum address from message if present"""
    words = message.split()
    for word in words:
        if word.startswith("0x") and len(word) >= 40:
            return word
    return None



def get_next_required_param():
    """Get the next parameter we need to collect based on the flow"""
    if not context.current_flow:
        return None
    
    flow_required_params = FLOW_PARAMS.get(context.current_flow, {})
    for param, prompt in flow_required_params.items():
        if param not in context.collected_params:
            return param, prompt
    return None, None

def handle_welcome_state():
    welcome_message = "Hello! I'm here to help you analyze blockchain data. I can help with:\n" \
                     "- Source of Funds (SOF) analysis\n" \
                     "- Usage of Funds (UOF) analysis\n" \
                     "- Portfolio analysis\n" \
                     "What would you like to know about?"
    context.current_state = "IDENTIFY_INTENT"
    return welcome_message

def handle_identify_intent(user_message):
    flow = what_flow(user_message)
    if flow in ["SOF", "UOF", "PORTFOLIO"]:
        context.current_flow = flow
        
        # Try to extract any parameters from the initial message
        if address := extract_address(user_message):
            context.collected_params["address"] = address
        
        if flow == "UOF":
            token_val = what_token(user_message)
            if token_val and token_val.strip().lower() != "none":
                context.collected_params["token"] = token_val.strip()
        
        # Check what parameter we need next
        next_param, prompt = get_next_required_param()
        if next_param:
            context.current_state = "GET_PARAMS"
            context.pending_param = next_param
            return prompt
        else:
            context.current_state = "EXECUTE_FLOW"
            return "Got all parameters. Processing..."
    else:
        context.current_state = "WELCOME"
        return handle_welcome_state()

def handle_get_params(user_message):
    if not context.pending_param:
        next_param, prompt = get_next_required_param()
        if not next_param:
            context.current_state = "EXECUTE_FLOW"
            return "Got all parameters. Processing..."
        context.pending_param = next_param
        return prompt
    
    # Existing handling for address, token, and network
    if context.pending_param == "address":
        if address := extract_address(user_message):
            context.collected_params["address"] = address
            context.pending_param = None
        else:
            return "I need an Base, Starknet, or Ethereum address starting with '0x'. Please provide a valid address."
    
    elif context.pending_param == "token":
        token_val = what_token(user_message)
        if token_val and token_val.strip().lower() != "none":
            context.collected_params["token"] = token_val.strip()
            context.pending_param = None
        else:
            return "Please specify a valid token like ETH, USDC, USDT, or STRK."
    
    elif context.pending_param == "network":
        # Normalize and validate the network input
        network = what_network(user_message)
        allowed_networks = ["base", "starknet", "eth mainnet", "ethereum", "eth"]
        if network in allowed_networks:
            context.collected_params["network"] = network
            context.pending_param = None
        else:
            return "Please specify a valid network: Base, Starknet, or ETH Mainnet."
    
    # New handling for starting block
    elif context.pending_param == "start_block":
        block_range = what_block_numbers(user_message)
        if block_range != "none" and "," in block_range:
            try:
                start_str, end_str = block_range.split(",")
                start_block = int(start_str.strip())
                end_block = int(end_str.strip())
                context.collected_params["start_block"] = start_block
                context.collected_params["end_block"] = end_block
                context.pending_param = None
            except ValueError:
                return "Could not parse block numbers. Please provide them as integers separated by a comma (e.g., 1000,2000)."
        else:
            try:
                start_block = int(user_message.strip())
                context.collected_params["start_block"] = start_block
                context.pending_param = "end_block"
                return "Please provide the ending block number for the analysis."
            except ValueError:
                return "Please provide a valid starting block number."
    
    # New handling for ending block
    elif context.pending_param == "end_block":
        try:
            end_block = int(user_message.strip())
            context.collected_params["end_block"] = end_block
            context.pending_param = None
        except ValueError:
            return "Please provide a valid ending block number."
    
    # Check if we need more parameters
    next_param, prompt = get_next_required_param()
    if next_param:
        context.pending_param = next_param
        return prompt
    else:
        context.current_state = "EXECUTE_FLOW"
        params_summary = ", ".join(f"{k}: {v}" for k, v in context.collected_params.items())
        return f"Got all parameters ({params_summary}), getting tools"

def handle_execute_flow():
    try:
        address = context.collected_params.get("address")
        if context.current_flow == "SOF":
            result = sof_flow(address)
        elif context.current_flow == "UOF":
            token = context.collected_params.get("token", "ETH")
            network = context.collected_params.get("network")
            start_block = context.collected_params.get("start_block")
            end_block = context.collected_params.get("end_block")
            result = uof_flow(address, token, network, start_block, end_block)
        elif context.current_flow == "PORTFOLIO":
            result = portfolio_flow(address)
        else:
            result = "Something went wrong. Let's start over."
            context.reset()
        
        # Reset for next conversation
        context.current_state = "WELCOME"
        return result
    except Exception as e:
        context.reset()
        return f"An error occurred: {str(e)}. Let's start over."

@app.route('/v1/chat/completions', methods=['POST'])
def chat_completions():
    data = request.get_json()
    messages = data.get('messages', [])
    stream = data.get('stream', False)
    
    # Get the latest user message
    user_message = messages[-1]['content'] if messages else ""
    context.add_message("user", user_message)
    if user_message.strip().lower() == '/reset':
        context.reset()
        welcome_message = handle_welcome_state()
        return send_response(welcome_message, stream)
    
    # For first message or after reset, try to identify intent and parameters immediately
    if context.current_state == "WELCOME":
        flow = what_flow(user_message)
        if flow in ["SOF", "UOF", "PORTFOLIO"]:
            context.current_flow = flow
            
            # Try to extract all possible parameters from the first message
            if address := extract_address(user_message):
                context.collected_params["address"] = address
            
            if flow == "UOF":
                token_val = what_token(user_message)
                if token_val and token_val.strip().lower() != "none":
                    context.collected_params["token"] = token_val.strip()
            
            # Check if we have all required parameters
            next_param, prompt = get_next_required_param()
            if next_param:
                context.current_state = "GET_PARAMS"
                context.pending_param = next_param
                response = prompt
            else:
                context.current_state = "EXECUTE_FLOW"
                response = handle_execute_flow()
        else:
            response = handle_welcome_state()
    else:
        if context.current_state == "IDENTIFY_INTENT":
            response = handle_identify_intent(user_message)
        elif context.current_state == "GET_PARAMS":
            response = handle_get_params(user_message)
        elif context.current_state == "EXECUTE_FLOW":
            response = handle_execute_flow()
        else:
            response = "Let's start over. What would you like to know about?"
            context.reset()
    
    return send_response(response, stream)

@app.route('/context', methods=['GET'])
def get_context():
    return jsonify({
        "messages": context.get_messages(),
        "state": context.current_state,
        "flow": context.current_flow,
        "params": context.collected_params,
        "pending_param": context.pending_param
    })

@app.route('/v1/uof/visualization', methods=['POST'])
def uof_visualization():
    data = request.get_json()
    address = data.get('address')
    token = data.get('token')
    network = data.get('network')
    start_block = data.get('start_block')
    end_block = data.get('end_block')
    
    # Call the uof_flow function to generate the visualization
    result = uof_flow(address, token, network, start_block, end_block)
    
    # Extract the base64 image from the markdown string
    match = re.search(r'!\[UOF Graph\]\((data:image\/png;base64,[^)]+)\)', result)
    if match:
        image = match.group(1)
        return jsonify({ "image": image }), 200
    else:
        return jsonify({ "error": "Visualization generation failed" }), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=1234, debug=True) 