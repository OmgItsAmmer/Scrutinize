# System Tests

**Justification in Pipeline:**
The system test suite provides the ultimate validation of the Scrutinize pipeline by verifying end-to-end functionality in a production-like environment. These tests evaluate the entire application stack—from the API layer down to the deployed infrastructure—as a complete, unified entity. They are essential for ensuring that user flows work flawlessly across all services and that deployment configurations are correct before code reaches end-users.

## Tests Summary

- **test_stack_smoke.py**: Performs a smoke test across the entire deployed application stack. Validates core workflows (like basic query processing) to ensure the system is up, healthy, and capable of handling end-to-end requests without catastrophic failures.
