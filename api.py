import os
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import json
import base64
import time

app = Flask(__name__)
CORS(app)

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

def make_api_request(cnpj_contribuinte, id_servico, versao_sistema, dados, headers):
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
            "idSistema": "PGDASD",
            "idServico": id_servico,
            "versaoSistema": versao_sistema,
            "dados": dados
        }
    }
    
    try:
        response = requests.post(
            'https://gateway.apiserpro.serpro.gov.br/integra-contador/v1/Consultar',
            headers=headers,
            json=json_data,
            timeout=30  # Timeout de 30 segundos
        )
        return response
    except requests.RequestException as e:
        return None

@app.route('/api/consultar', methods=['POST'])
def consultar_api():
    """API endpoint to process requests with CNPJ, idServico, versaoSistema, and dados parameters"""
    start_time = time.time()
    
    try:
        # Get request data
        request_data = request.json
        
        if not request_data:
            return jsonify({"error": "No data provided"}), 400
            
        # Extract parameters
        cnpj_contribuinte = request_data.get('cnpj')
        id_servico = request_data.get('idServico')
        versao_sistema = request_data.get('versaoSistema')
        dados = request_data.get('dados')
        
        # Validate required parameters
        if not all([cnpj_contribuinte, id_servico, versao_sistema, dados]):
            missing = []
            if not cnpj_contribuinte: missing.append('cnpj')
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
        response = make_api_request(cnpj_contribuinte, id_servico, versao_sistema, dados, headers)
        
        if response is None:
            return jsonify({"error": "Failed to connect to the API"}), 500
            
        # Process response
        if response.status_code != 200:
            error_message = "Unknown error"
            try:
                error_data = response.json()
                if 'mensagens' in error_data and len(error_data['mensagens']) > 0:
                    error_message = error_data['mensagens'][0]['texto']
            except:
                error_message = f"Status code: {response.status_code}"
                
            return jsonify({
                "success": False,
                "error": error_message,
                "status_code": response.status_code
            }), response.status_code
        
        # Return successful response
        result = response.json()
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        return jsonify({
            "success": True,
            "data": result,
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