package ecp

import (
	"crypto/ed25519"
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"os"
	"path/filepath"
	"time"
)

// Identity represents a local agent identity with an Ed25519 keypair.
// Stored at ~/.atlast/identity.json. Format is cross-SDK compatible with Python/TS SDKs.
type Identity struct {
	DID       string `json:"did"`
	PubKey    string `json:"pub_key"`
	PrivKey   string `json:"priv_key"` // 32-byte seed, hex-encoded. Local only, never transmitted.
	CreatedAt int64  `json:"created_at"`
	Verified  bool   `json:"verified"`
}

// defaultIdentityPath returns the default path for the identity file.
func defaultIdentityPath() string {
	home, _ := os.UserHomeDir()
	return filepath.Join(home, ".atlast", "identity.json")
}

// GetOrCreateIdentity loads the identity from ~/.atlast/identity.json, creating it if absent.
func GetOrCreateIdentity() (Identity, error) {
	path := defaultIdentityPath()
	id, err := LoadIdentity(path)
	if err == nil {
		return id, nil
	}
	return CreateAndSaveIdentity(path)
}

// GenerateIdentity creates a new Ed25519 keypair and derives a DID.
// DID format: did:ecp:{sha256(pub_key_hex)[:32]}
// This matches the Python SDK identity generation exactly.
func GenerateIdentity() (Identity, error) {
	pub, priv, err := ed25519.GenerateKey(rand.Reader)
	if err != nil {
		return Identity{}, err
	}
	pubHex := hex.EncodeToString(pub)
	// Store only the 32-byte seed (matches Python cryptography library Raw format).
	privHex := hex.EncodeToString(priv.Seed())

	// DID = first 32 hex chars of sha256(pubkey_hex_string) — matches Python SDK.
	h := sha256.Sum256([]byte(pubHex))
	agentID := hex.EncodeToString(h[:])[:32]

	return Identity{
		DID:       "did:ecp:" + agentID,
		PubKey:    pubHex,
		PrivKey:   privHex,
		CreatedAt: time.Now().UnixMilli(),
		Verified:  true,
	}, nil
}

// LoadIdentity reads an identity from disk.
func LoadIdentity(path string) (Identity, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return Identity{}, err
	}
	var id Identity
	if err := json.Unmarshal(data, &id); err != nil {
		return Identity{}, err
	}
	return id, nil
}

// SaveIdentity writes an identity to disk (0600 permissions).
func SaveIdentity(path string, id Identity) error {
	if err := os.MkdirAll(filepath.Dir(path), 0700); err != nil {
		return err
	}
	data, err := json.MarshalIndent(id, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, data, 0600)
}

// CreateAndSaveIdentity generates a new identity and saves it to path.
func CreateAndSaveIdentity(path string) (Identity, error) {
	id, err := GenerateIdentity()
	if err != nil {
		return Identity{}, err
	}
	if err := SaveIdentity(path, id); err != nil {
		return Identity{}, err
	}
	return id, nil
}

// SignData signs data with the identity's private key.
// Returns "ed25519:{hex}" or "unverified" on error.
func SignData(id Identity, data string) string {
	seed, err := hex.DecodeString(id.PrivKey)
	if err != nil || len(seed) != ed25519.SeedSize {
		return "unverified"
	}
	priv := ed25519.NewKeyFromSeed(seed)
	sig := ed25519.Sign(priv, []byte(data))
	return "ed25519:" + hex.EncodeToString(sig)
}
