class APIException(Exception):
    status_code: int = 500
    default_message: str = "Internal Server Error"

    def __init__(self, message=None):
        if message:
            self.message = f"{self.default_message}: {message}"
        else:
            self.message = self.default_message
        super().__init__(self.message)


# 4xx Client Error
class APIBadRequest(APIException):
    status_code = 400
    default_message = "Bad Request"


class APIUnauthorized(APIException):
    status_code = 401
    default_message = "Unauthorized"


class APIForbidden(APIException):
    status_code = 403
    default_message = "Forbidden"


class APINotFound(APIException):
    status_code = 404
    default_message = "Not Found"


class APIMethodNotAllowed(APIException):
    status_code = 405
    default_message = "Method Not Allowed"


class APIRequestTimeout(APIException):
    status_code = 408
    default_message = "Request Timeout"


class APIConflict(APIException):
    status_code = 409
    default_message = "Conflict"


class APIPayloadTooLarge(APIException):
    status_code = 413
    default_message = "Payload Too Large"


class APIUnsupportedMediaType(APIException):
    status_code = 415
    default_message = "Unsupported Media Type"


class APIUnprocessableEntity(APIException):
    status_code = 422
    default_message = "Unprocessable Entity"


class APITooManyRequests(APIException):
    status_code = 429
    default_message = "Too Many Requests"


# 5xx Server Error
class APIInternalServerError(APIException):
    status_code = 500
    default_message = "Internal Server Error"


class APINotImplemented(APIException):
    status_code = 501
    default_message = "Not Implemented"


class APIBadGateway(APIException):
    status_code = 502
    default_message = "Bad Gateway"


class APIServiceUnavailable(APIException):
    status_code = 503
    default_message = "Service Unavailable"


class APIGatewayTimeout(APIException):
    status_code = 504
    default_message = "Gateway Timeout"
