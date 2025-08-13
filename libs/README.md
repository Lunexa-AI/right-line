# Shared Libraries

Reusable components and utilities shared across services.

## Libraries

### common/

Shared types, configuration, and utility functions.

### database/

Database models, migrations, and connection management.

### telemetry/

Logging, metrics, and distributed tracing utilities.

## Usage

These libraries are imported by the services. Changes here affect multiple services,
so ensure backward compatibility and comprehensive testing.
