from flask import jsonify

def handler(request):
    """Health check endpoint for Vercel"""
    return {
        'statusCode': 200,
        'headers': {'Access-Control-Allow-Origin': '*'},
        'body': jsonify({"status": "healthy", "service": "write-aid-backend"}).data
    }
