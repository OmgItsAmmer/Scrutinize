# Integration Tests

**Justification in Pipeline:**
This integration test suite is critical for verifying that the independently developed components of the Scrutinize pipeline function correctly when combined. It bridges the gap between isolated unit tests and full system tests by testing interactions between the application logic and external services (like the actual database, Redis, or mock APIs). This ensures data flows correctly across boundaries and catches issues related to database schemas, service configurations, and API contracts.

## Tests Summary

- **test_health_integration.py**: Verifies the health check endpoints interact correctly with underlying infrastructure. Ensures the API can successfully report the live status of the database and other critical dependencies.
