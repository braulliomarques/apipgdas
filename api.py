import os
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import json
import base64
import time

app = Flask(__name__)
CORS(app)

# Token de acesso fixo
API_TOKEN = "F0EHbyjo2eo3ZL9TDaimKZRR9Zl43epwBZKCgKARY2f8Dw0Z7eQDeshL3fE0FrPE"

def validate_token():
    """Validate the API token from request headers"""
    auth_header = request.headers.get('Authorization')
    
    if not auth_header:
        return False, "Authorization header is missing"
        
    try:
        # Format esperado: "Bearer <token>"
        scheme, token = auth_header.split()
        if scheme.lower() != 'bearer':
            return False, "Invalid authentication scheme"
        if token != API_TOKEN:
            return False, "Invalid token"
            
        return True, None
    except Exception:
        return False, "Invalid authorization header format"

def load_config():
    """Load configuration from config.json file"""
    try:
        with open('config.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {
            "api_key": "",
            "client_id": "",
            "client_secret": "",
            "cnpj_contratante": ""
        }

def save_config(config_data):
    """Save configuration to config.json file"""
    with open('config.json', 'w') as f:
        json.dump(config_data, f, indent=4)

def get_auth_token(client_id, client_secret, cert_crt_file, cert_key_file):
    """Get authentication token from SERPRO API"""
    auth_string = f"{client_id}:{client_secret}"
    auth_base64 = base64.b64encode(auth_string.encode()).decode()

    headers = {
        'Authorization': f'Basic {auth_base64}',
        'Role-Type': 'TERCEIROS',
        'Content-Type': 'application/x-www-form-urlencoded',
    }

    cert = (cert_crt_file, cert_key_file)

    data = {
        'grant_type': 'client_credentials',
    }

    try:
        response = requests.post(
            'https://autenticacao.sapi.serpro.gov.br/authenticate',
            headers=headers,
            data=data,
            cert=cert,
            timeout=10  # Timeout de 10 segundos
        )
        
        if response.status_code != 200:
            return None, f"Authentication failed with status code: {response.status_code}"
            
        result = response.json()
        return {
            'access_token': result['access_token'],
            'jwt_token': result['jwt_token']
        }, None
    except Exception as e:
        return None, str(e)

def make_api_request(tipo, cnpj_contribuinte, id_sistema, id_servico, versao_sistema, dados, headers):
    """Make request to SERPRO API with the provided parameters"""
    config = load_config()
    cnpj_contratante = config['cnpj_contratante']
    
    json_data = {
        "contratante": {
            "numero": cnpj_contratante,
            "tipo": 2
        },
        "autorPedidoDados": {
            "numero": cnpj_contratante,
            "tipo": 2
        },
        "contribuinte": {
            "numero": cnpj_contribuinte,
            "tipo": 2
        },
        "pedidoDados": {
            "idSistema": id_sistema,
            "idServico": id_servico,
            "versaoSistema": versao_sistema,
            "dados": dados
        }
    }
    
    # Determine the URL based on the tipo
    url_map = {
        'consultar': 'https://gateway.apiserpro.serpro.gov.br/integra-contador/v1/Consultar',
        'emitir': 'https://gateway.apiserpro.serpro.gov.br/integra-contador/v1/Emitir',
        'declarar': 'https://gateway.apiserpro.serpro.gov.br/integra-contador/v1/Declarar'
    }
    
    url = url_map.get(tipo)
    if not url:
        return None, f"Invalid operation type: {tipo}"
    
    try:
        response = requests.post(
            url,
            headers=headers,
            json=json_data,
            timeout=30  # Timeout de 30 segundos
        )
        return response, None
    except requests.RequestException as e:
        return None, str(e)

@app.route('/api', methods=['POST'])
def api_handler():
    """API endpoint to handle different operation types"""
    start_time = time.time()
    
    try:
        # Validate token
        is_valid, error = validate_token()
        if not is_valid:
            return jsonify({"error": f"Authentication failed: {error}"}), 401
            
        # Get request data
        request_data = request.json
        
        if not request_data:
            return jsonify({"error": "No data provided"}), 400
            
        # Extract parameters
        tipo = request_data.get('tipo')
        cnpj_contribuinte = request_data.get('cnpj')
        id_sistema = request_data.get('idSistema')
        id_servico = request_data.get('idServico')
        versao_sistema = request_data.get('versaoSistema')
        dados = request_data.get('dados')
        
        # Validate required parameters
        if not all([tipo, cnpj_contribuinte, id_sistema, id_servico, versao_sistema, dados]):
            missing = []
            if not tipo: missing.append('tipo')
            if not cnpj_contribuinte: missing.append('cnpj')
            if not id_sistema: missing.append('idSistema')
            if not id_servico: missing.append('idServico')
            if not versao_sistema: missing.append('versaoSistema')
            if not dados: missing.append('dados')
            
            return jsonify({"error": f"Missing required parameters: {', '.join(missing)}"}), 400
        
        # Load configuration
        config = load_config()
        client_id = config['client_id']
        client_secret = config['client_secret']
        
        # Certificate paths
        cert_crt_file = 'certificado.crt'
        cert_key_file = 'chave.key'
        
        # Get authentication token
        auth_result, error = get_auth_token(client_id, client_secret, cert_crt_file, cert_key_file)
        
        if error:
            return jsonify({"error": f"Authentication failed: {error}"}), 500
            
        # Set headers for API request
        headers = {
            'Authorization': f'Bearer {auth_result["access_token"]}',
            'Content-Type': 'application/json',
            'jwt_token': auth_result["jwt_token"],
        }
        
        # Make API request
        response, error = make_api_request(tipo, cnpj_contribuinte, id_sistema, id_servico, versao_sistema, dados, headers)
        
        if error:
            return jsonify({"error": error}), 400
            
        if response is None:
            return jsonify({"error": "Failed to connect to the API"}), 500
            
        # Return successful response
        end_time = time.time()
        execution_time = end_time - start_time
        
        return jsonify({
            "success": True,
            "data": response.json(),
            "execution_time": execution_time
        })
        
    except Exception as e:
        end_time = time.time()
        execution_time = end_time - start_time
        print(f"Error occurred. Total execution time: {execution_time} seconds")
        return jsonify({
            "success": False,
            "error": str(e),
            "execution_time": execution_time
        }), 500

@app.route('/', methods=['GET'])
def index():
    """Root endpoint to check if the API is running"""
    return jsonify({
        "status": "online",
        "message": "API Integra Contador is running"
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, port=port, host='0.0.0.0')
