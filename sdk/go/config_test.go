package ecp

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

// writeTestConfig writes a config JSON to a temp file and returns the path.
// It patches defaultConfigPath by temporarily pointing the env var.
// Since defaultConfigPath is not injectable, we test via LoadConfig indirectly
// by writing to a known path and reading it.

func TestLoadConfigMissing(t *testing.T) {
	// Point config to a non-existent file via HOME override
	dir := t.TempDir()
	old := os.Getenv("HOME")
	os.Setenv("HOME", dir)
	defer os.Setenv("HOME", old)

	cfg := LoadConfig()
	if cfg.Endpoint != "" || cfg.AgentAPIKey != "" {
		t.Error("LoadConfig should return empty Config when file missing")
	}
}

func TestLoadConfigValid(t *testing.T) {
	dir := t.TempDir()
	old := os.Getenv("HOME")
	os.Setenv("HOME", dir)
	defer os.Setenv("HOME", old)

	atlastDir := filepath.Join(dir, ".atlast")
	os.MkdirAll(atlastDir, 0700)
	cfgFile := filepath.Join(atlastDir, "config.json")

	data, _ := json.Marshal(Config{
		Endpoint:    "https://custom.example.com",
		AgentAPIKey: "test-key-123",
	})
	os.WriteFile(cfgFile, data, 0600)

	cfg := LoadConfig()
	if cfg.Endpoint != "https://custom.example.com" {
		t.Errorf("Endpoint: want %q, got %q", "https://custom.example.com", cfg.Endpoint)
	}
	if cfg.AgentAPIKey != "test-key-123" {
		t.Errorf("AgentAPIKey: want %q, got %q", "test-key-123", cfg.AgentAPIKey)
	}
}

func TestGetAPIURLDefault(t *testing.T) {
	os.Unsetenv("ATLAST_API_URL")
	dir := t.TempDir()
	old := os.Getenv("HOME")
	os.Setenv("HOME", dir)
	defer os.Setenv("HOME", old)

	url := GetAPIURL()
	if url != defaultAPIURL {
		t.Errorf("default API URL: want %q, got %q", defaultAPIURL, url)
	}
}

func TestGetAPIURLFromEnv(t *testing.T) {
	os.Setenv("ATLAST_API_URL", "https://env.example.com/v1")
	defer os.Unsetenv("ATLAST_API_URL")

	url := GetAPIURL()
	if url != "https://env.example.com/v1" {
		t.Errorf("env API URL: want %q, got %q", "https://env.example.com/v1", url)
	}
}

func TestGetAPIURLEnvWithoutV1Suffix(t *testing.T) {
	os.Setenv("ATLAST_API_URL", "https://env.example.com")
	defer os.Unsetenv("ATLAST_API_URL")

	url := GetAPIURL()
	if url != "https://env.example.com/v1" {
		t.Errorf("should append /v1: want %q, got %q", "https://env.example.com/v1", url)
	}
}

func TestGetAPIURLEnvWithTrailingSlash(t *testing.T) {
	os.Setenv("ATLAST_API_URL", "https://env.example.com/")
	defer os.Unsetenv("ATLAST_API_URL")

	url := GetAPIURL()
	if url != "https://env.example.com/v1" {
		t.Errorf("should strip trailing slash and append /v1: want %q, got %q", "https://env.example.com/v1", url)
	}
}

func TestGetAPIURLFromConfig(t *testing.T) {
	os.Unsetenv("ATLAST_API_URL")
	dir := t.TempDir()
	old := os.Getenv("HOME")
	os.Setenv("HOME", dir)
	defer os.Setenv("HOME", old)

	atlastDir := filepath.Join(dir, ".atlast")
	os.MkdirAll(atlastDir, 0700)
	cfgFile := filepath.Join(atlastDir, "config.json")
	data, _ := json.Marshal(Config{Endpoint: "https://config.example.com"})
	os.WriteFile(cfgFile, data, 0600)

	url := GetAPIURL()
	if url != "https://config.example.com/v1" {
		t.Errorf("config API URL: want %q, got %q", "https://config.example.com/v1", url)
	}
}

func TestGetAPIURLEnvTakesPriorityOverConfig(t *testing.T) {
	os.Setenv("ATLAST_API_URL", "https://env.example.com/v1")
	defer os.Unsetenv("ATLAST_API_URL")

	dir := t.TempDir()
	old := os.Getenv("HOME")
	os.Setenv("HOME", dir)
	defer os.Setenv("HOME", old)

	atlastDir := filepath.Join(dir, ".atlast")
	os.MkdirAll(atlastDir, 0700)
	cfgFile := filepath.Join(atlastDir, "config.json")
	data, _ := json.Marshal(Config{Endpoint: "https://config.example.com"})
	os.WriteFile(cfgFile, data, 0600)

	url := GetAPIURL()
	if url != "https://env.example.com/v1" {
		t.Errorf("env should take priority: want %q, got %q", "https://env.example.com/v1", url)
	}
}

func TestGetAPIKeyDefault(t *testing.T) {
	os.Unsetenv("ATLAST_API_KEY")
	dir := t.TempDir()
	old := os.Getenv("HOME")
	os.Setenv("HOME", dir)
	defer os.Setenv("HOME", old)

	key := GetAPIKey()
	if key != "" {
		t.Errorf("default API key should be empty, got %q", key)
	}
}

func TestGetAPIKeyFromEnv(t *testing.T) {
	os.Setenv("ATLAST_API_KEY", "env-secret-key")
	defer os.Unsetenv("ATLAST_API_KEY")

	key := GetAPIKey()
	if key != "env-secret-key" {
		t.Errorf("env API key: want %q, got %q", "env-secret-key", key)
	}
}

func TestGetAPIKeyFromConfig(t *testing.T) {
	os.Unsetenv("ATLAST_API_KEY")
	dir := t.TempDir()
	old := os.Getenv("HOME")
	os.Setenv("HOME", dir)
	defer os.Setenv("HOME", old)

	atlastDir := filepath.Join(dir, ".atlast")
	os.MkdirAll(atlastDir, 0700)
	cfgFile := filepath.Join(atlastDir, "config.json")
	data, _ := json.Marshal(Config{AgentAPIKey: "config-key-xyz"})
	os.WriteFile(cfgFile, data, 0600)

	key := GetAPIKey()
	if key != "config-key-xyz" {
		t.Errorf("config API key: want %q, got %q", "config-key-xyz", key)
	}
}

func TestGetAPIKeyEnvTakesPriority(t *testing.T) {
	os.Setenv("ATLAST_API_KEY", "env-key")
	defer os.Unsetenv("ATLAST_API_KEY")

	dir := t.TempDir()
	old := os.Getenv("HOME")
	os.Setenv("HOME", dir)
	defer os.Setenv("HOME", old)

	atlastDir := filepath.Join(dir, ".atlast")
	os.MkdirAll(atlastDir, 0700)
	cfgFile := filepath.Join(atlastDir, "config.json")
	data, _ := json.Marshal(Config{AgentAPIKey: "config-key"})
	os.WriteFile(cfgFile, data, 0600)

	key := GetAPIKey()
	if key != "env-key" {
		t.Errorf("env should take priority: want %q, got %q", "env-key", key)
	}
}

func TestNormalizeURL(t *testing.T) {
	cases := []struct{ in, want string }{
		{"https://api.example.com", "https://api.example.com/v1"},
		{"https://api.example.com/", "https://api.example.com/v1"},
		{"https://api.example.com/v1", "https://api.example.com/v1"},
		{"https://api.example.com/v1/", "https://api.example.com/v1"},
	}
	for _, tc := range cases {
		got := normalizeURL(tc.in)
		if got != tc.want {
			t.Errorf("normalizeURL(%q): want %q, got %q", tc.in, tc.want, got)
		}
	}
}
