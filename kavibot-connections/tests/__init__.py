"""Tests for the KaviBOT connections layer.

Covers the declarative connection registry, the shared OAuth2 PKCE flow
(including the Login-with-Amazon style variant), the vault-backed secret
store, the per-connection modules, and the Apple Music library importer.
All network access is mocked; no test touches the real internet.
"""
