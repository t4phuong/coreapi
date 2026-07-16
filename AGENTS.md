# Critical Rules
All implements must be accepted by developer.

# Projects
## Name
T4 Core API

## Target
- Support non-code or low-code user making or managing restful api.

## Scope 
- Include managing service, version, route, api action.
- Service include version, version include route, route include api action.
- 3 Default Service: login, AuthN, AuthZ, must be installed automatically.

## Project Structure
- **`controllers/`**: Entry point for HTTP requests.
  - `proxy.py`: Defines the universal gateway route (`/api/<service_code>/<version>/<path:subpath>`) and triggers the dispatcher.
  - `base.py`: Prepares the `request.service_info` context and initializes the `CoreApiDispatcher`.
- **`models/`**: Odoo ORM models representing the core entities.
  - `core_api_service.py`: `t4.coreapi.service` (Manages API services and their required actions).
  - `core_api_version.py`: `t4.coreapi.version` (Manages service versions, e.g., 'v1').
  - `core_api_route.py`: `t4.coreapi.route` (Manages endpoints/routes and HTTP methods).
  - `core_api_actions.py`: `t4.coreapi.action` (Stores and executes Python code via `safe_eval`) & `t4.coreapi.action.manager` (Auto-generates endpoints).
- **`utils/`**: Utilities and core processing logic.
  - `dispatcher.py`: Contains `CoreApiDispatcher`, which handles request routing, sequential execution, payload context injection, and response formatting.
- **`exceptions/`**: Custom API exceptions.
  - `api_exceptions.py`: Defines exceptions like `APIException`, `APINotFound`, `APIBadRequest` which are caught and formatted into standard JSON responses by the dispatcher.
- **`views/`**: Backend UI definitions (XML) for administrators to manage API components without coding.

## Execute Flow
- **Gateway Interception**: Request arrives at `/api/{service_code}/{version}/{subpath}` (handled in `controllers/proxy.py`).
- **Context Preparation**: `request.service_info` is built, and `CoreApiDispatcher` is instantiated.
- **Dispatching** (`dispatcher.dispatch()`):
  1. Sets a default response.
  2. **Required Actions**: Resolves the Service by code and runs all required actions sequentially (acts as middleware/interceptors).
  3. **Route Action**: Resolves the Version and Route, validates HTTP method, and executes the target API Action (injecting HTTP context like params, body, headers into `safe_eval`'s `eval_context`).
  4. **Exception Handling**: If any `APIException` occurs, it's caught and mapped to an appropriate JSON response format with the correct HTTP status code.
  5. **Response**: Formats and returns the final `Response` in JSON.
