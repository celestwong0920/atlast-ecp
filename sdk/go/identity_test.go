package ecp

import (
	"crypto/ed25519"
	"encoding/hex"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestGenerateIdentity(t *testing.T) {
	id, err := GenerateIdentity()
	if err != nil {
		t.Fatalf("GenerateIdentity error: %v", err)
	}

	// DID format
	if !strings.HasPrefix(id.DID, "did:ecp:") {
		t.Errorf("DID should start with 'did:ecp:', got %q", id.DID)
	}
	didSuffix := strings.TrimPrefix(id.DID, "did:ecp:")
	if len(didSuffix) != 32 {
		t.Errorf("DID suffix should be 32 hex chars, got %d", len(didSuffix))
	}

	// PubKey is 64 hex chars (32 bytes)
	if len(id.PubKey) != 64 {
		t.Errorf("PubKey should be 64 hex chars, got %d", len(id.PubKey))
	}

	// PrivKey is 64 hex chars (32-byte seed)
	if len(id.PrivKey) != 64 {
		t.Errorf("PrivKey should be 64 hex chars (32-byte seed), got %d", len(id.PrivKey))
	}

	if !id.Verified {
		t.Error("Verified should be true for generated identity")
	}
	if id.CreatedAt == 0 {
		t.Error("CreatedAt should be set")
	}
}

func TestGenerateIdentityUnique(t *testing.T) {
	id1, _ := GenerateIdentity()
	id2, _ := GenerateIdentity()
	if id1.DID == id2.DID {
		t.Error("Two generated identities should have different DIDs")
	}
	if id1.PubKey == id2.PubKey {
		t.Error("Two generated identities should have different public keys")
	}
}

func TestSaveLoadIdentity(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "identity.json")

	id, err := GenerateIdentity()
	if err != nil {
		t.Fatal(err)
	}

	if err := SaveIdentity(path, id); err != nil {
		t.Fatalf("SaveIdentity error: %v", err)
	}

	// File should have restricted permissions
	info, err := os.Stat(path)
	if err != nil {
		t.Fatal(err)
	}
	if info.Mode().Perm() != 0600 {
		t.Errorf("identity file permissions: want 0600, got %04o", info.Mode().Perm())
	}

	loaded, err := LoadIdentity(path)
	if err != nil {
		t.Fatalf("LoadIdentity error: %v", err)
	}

	if loaded.DID != id.DID {
		t.Errorf("DID mismatch: want %q, got %q", id.DID, loaded.DID)
	}
	if loaded.PubKey != id.PubKey {
		t.Errorf("PubKey mismatch")
	}
	if loaded.PrivKey != id.PrivKey {
		t.Errorf("PrivKey mismatch")
	}
	if loaded.CreatedAt != id.CreatedAt {
		t.Errorf("CreatedAt mismatch")
	}
}

func TestSaveIdentityCreatesDir(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "subdir", "identity.json")

	id, _ := GenerateIdentity()
	if err := SaveIdentity(path, id); err != nil {
		t.Fatalf("SaveIdentity should create parent dir: %v", err)
	}
	if _, err := os.Stat(path); err != nil {
		t.Error("identity file should exist")
	}
}

func TestLoadIdentityNotFound(t *testing.T) {
	_, err := LoadIdentity("/nonexistent/path/identity.json")
	if err == nil {
		t.Error("LoadIdentity should return error for missing file")
	}
}

func TestGetOrCreateIdentity(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "identity.json")

	// Redirect default path for test — create, save, then load via CreateAndSaveIdentity
	id1, err := CreateAndSaveIdentity(path)
	if err != nil {
		t.Fatalf("CreateAndSaveIdentity error: %v", err)
	}

	// Load again — should return same identity
	id2, err := LoadIdentity(path)
	if err != nil {
		t.Fatalf("LoadIdentity error: %v", err)
	}
	if id1.DID != id2.DID {
		t.Error("Should load same identity on second call")
	}
}

func TestDIDFormat(t *testing.T) {
	id, _ := GenerateIdentity()
	// DID suffix must be valid hex
	suffix := strings.TrimPrefix(id.DID, "did:ecp:")
	if _, err := hex.DecodeString(suffix); err != nil {
		t.Errorf("DID suffix should be valid hex: %v", err)
	}
}

func TestSignData(t *testing.T) {
	id, err := GenerateIdentity()
	if err != nil {
		t.Fatal(err)
	}

	sig := SignData(id, "test message")
	if !strings.HasPrefix(sig, "ed25519:") {
		t.Errorf("Signature should start with 'ed25519:', got %q", sig)
	}

	sigHex := strings.TrimPrefix(sig, "ed25519:")
	sigBytes, err := hex.DecodeString(sigHex)
	if err != nil {
		t.Fatalf("Signature should be valid hex: %v", err)
	}
	if len(sigBytes) != 64 {
		t.Errorf("Ed25519 signature should be 64 bytes, got %d", len(sigBytes))
	}

	// Verify the signature
	pubBytes, _ := hex.DecodeString(id.PubKey)
	pub := ed25519.PublicKey(pubBytes)
	if !ed25519.Verify(pub, []byte("test message"), sigBytes) {
		t.Error("Signature verification failed")
	}
}

func TestSignDataInvalidKey(t *testing.T) {
	id := Identity{PrivKey: "notvalidhex"}
	sig := SignData(id, "test")
	if sig != "unverified" {
		t.Errorf("Expected 'unverified' for invalid key, got %q", sig)
	}
}

func TestSignDataDeterministicForSameKey(t *testing.T) {
	id, _ := GenerateIdentity()
	// Ed25519 is deterministic
	sig1 := SignData(id, "hello")
	sig2 := SignData(id, "hello")
	if sig1 != sig2 {
		t.Error("Ed25519 signing should be deterministic")
	}
}
