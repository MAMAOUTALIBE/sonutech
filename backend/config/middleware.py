class PrivateNoStoreMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
    def __call__(self, request):
        response = self.get_response(request)
        if request.path.startswith(('/api/v1/manage/', '/api/v1/auth/', '/api/v1/crm/', '/crm/')) or request.method != 'GET':
            response['Cache-Control'] = 'no-store'
        if request.path.startswith(('/crm/', '/api/v1/crm/')):
            response['X-Robots-Tag'] = 'noindex, nofollow'
            response['Referrer-Policy'] = 'same-origin'
        return response
