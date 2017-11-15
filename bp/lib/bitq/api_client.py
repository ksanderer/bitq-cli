from bravado.requests_client import RequestsClient
from bravado.client import SwaggerClient

config = {
    # === bravado config ===

    # Determines what is returned by the service call.
    'also_return_response': False,

    # === bravado-core config ====

    #  validate incoming responses
    'validate_responses': True,

    # validate outgoing requests
    'validate_requests': True,

    # validate the swagger spec
    'validate_swagger_spec': True,

    # Use models (Python classes) instead of dicts for #/definitions/{models}
    'use_models': True,

    # List of user-defined formats
    # 'formats': [my_super_duper_format],
}

def get_client(host, token, version, port=80):
    http_client = RequestsClient()
    http_client.set_api_key(
        host, "Token %s" % token,
        param_name='Authorization', param_in='header'
    )

    return SwaggerClient.from_url(
        'http://%s:%d/api/schema' % (host, port),
        http_client=http_client,
        config=config
    )