# Changelog — AI Security Agent

## v1.0.0 (2026-07-05)

### Added
- AI Security Agent with journald monitoring, detection pipeline, rule engine, threat scoring, reputation engine, ban engine, and firewall abstraction
- SSH Security Pack with 9 pre-built detectors and 11 YAML rules
- Correlation Engine for multi-event attack chain detection
- Management Server with certificate authority, machine registry, secure pairing, and heartbeat protocol
- Policy Engine with YAML-based policies and single inheritance
- Routing Engine with fnmatch rule matching and priority levels
- Notification Engine with async priority queues and formatter framework
- Immutable Audit Engine with SHA-256 hash chaining
- Discord Integration via hosted Relay Bot
- Remote Command Framework with 12 typed commands and 4-stage authorization
- Configuration Synchronization Framework with version tracking
- Comprehensive test suite: 468 tests across all subsystems

### Security
- Ed25519 signatures for all certificates
- SHA-256 hash chaining for audit integrity
- Replay protection via sequence numbers and single-use tokens
- Sensitive information masking in logs
- 4-stage command authorization pipeline
- Constant-time token verification
