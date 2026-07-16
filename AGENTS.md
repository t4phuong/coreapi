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

## Execute Flow
- Each service have a 'Required actions', before run api action, it must run all required actions, like middleware.
- Service run like a chain from required actions -> api action in route -> catch error -> response.

