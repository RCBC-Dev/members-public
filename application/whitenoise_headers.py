def add_cors_headers(headers, path, url):
    """
    Add CORS headers to static files for allowed origins only.
    """
    import os
    
    # Determine domain based on environment
    environment = os.environ.get('ENVIRONMENT', '').strip().lower()
    if environment == 'production':
        headers['Access-Control-Allow-Origin'] = 'https://membersenquiries.redclev.net'
    elif environment == 'test':
        headers['Access-Control-Allow-Origin'] = 'https://membersenquiries-test.redclev.net'
    else:
        # Fallback for test environment
        headers['Access-Control-Allow-Origin'] = 'https://membersenquiries-test.redclev.net'
    
    headers['Vary'] = 'Origin'