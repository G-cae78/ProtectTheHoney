import json
from datetime import datetime

def handler(event, context):
    timestamp = datetime.utcnow().isoformat()

    # Extract information safely
    request_context = event.get('requestContext', {})
    http_info = request_context.get('http', {})

    source_ip = (
        http_info.get('sourceIp')
        or request_context.get('identity', {}).get('sourceIp')
    )

    headers = event.get('headers', {}) or {}
    user_agent = headers.get('User-Agent') or headers.get('user-agent')

    method = http_info.get('method') or event.get('httpMethod')
    path = event.get('rawPath') or event.get('path')

    request_info = {
        'timestamp': timestamp,
        'source_ip': source_ip,
        'user_agent': user_agent,
        'method': method,
        'path': path,
        'headers': headers,
    }

    print('🐝 Honeypot Access Detected:')
    print(json.dumps(request_info, indent=2))

    # Return a forbidden response
    return {
        'statusCode': 403,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps({'message': 'Forbidden'})
    }
