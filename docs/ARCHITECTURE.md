# Weam architecture baseline

## Product principle
The system supports multiple child conditions and support needs. It must not hard-code the product around hearing impairment or any single diagnosis.

## Layers
1. Responsive React client
2. FastAPI application API
3. PostgreSQL structured data
4. Object storage for reports/audio/images
5. Realtime communication layer
6. AI Gateway
7. RAG retrieval layer
8. Care Coordination Agent with human approval
9. Audit and permission enforcement

## Core permission rule
Access is evaluated using:

`role + child + guardian consent + resource permission + expiration`

AI and agent tools must use the same permission boundary as the UI/API.

## AI principle
AI may summarize, extract, retrieve, compare, and suggest. Sensitive actions require explicit human approval.

## Demo principle
Competition/demo environments use synthetic data only.
