# Changelog — AI Security Management Server

## v1.0.0 (2026-07-05)

### Added
- Certificate Authority with Ed25519 root CA and X.509 machine certificates
- Machine Registry with registration workflow, state machine, and approval
- Secure Pairing Protocol with SHA-256 token hashing and replay protection
- Heartbeat Protocol with version negotiation and capability tracking
- Policy Engine with YAML-based policies, single inheritance, and validation
- Routing Engine with wildcard matching, priority, and immutable decisions
- Notification Engine with async priority queues and formatter framework
- Immutable Audit Engine with SHA-256 hash chaining
- Discord Adapter as a separate process (presentation layer only)
- Remote Command Framework with 12 typed commands and 4-stage authorization
- Configuration Synchronization Framework with version tracking
- Logging & Reporting Framework with human-readable and JSONL formats
- Production hardening: health supervisor, worker supervision, emergency mode
- Comprehensive test suite: 468 tests across all subsystems

### Security
- Ed25519 signatures for all certificates
- SHA-256 hash chaining for audit integrity
- Replay protection via sequence numbers and single-use tokens
- Sensitive information masking in logs
- 4-stage command authorization pipeline
- Constant-time token verification

### Documentation
- Installation and operations guides

## v0.14.0
- Logging & Reporting Framework

## v0.13.0
- Configuration Synchronization Framework

## v0.12.0
- Remote Command Framework

## v0.11.0
- Discord Adapter

## v0.10.0
- Audit Engine

## v0.9.0
- Notification Engine

## v0.8.0
- Routing Engine

## v0.7.0
- Policy Engine

## v0.6.0
- Heartbeat & Management Protocol

## v0.5.0
- Secure Pairing Protocol

## v0.4.0
- Machine Registry & Registration

## v0.3.0
- Certificate Authority & Machine Identity

## v0.2.0
- Database Foundation

## v0.1.0
- Project Foundation
