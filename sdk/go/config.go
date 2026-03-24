package ecp

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
)

const defaultAPIURL = "https://api.weba0.com/v1"

// Config holds the local ATLAST configuration from ~/.atlast/config.json.
type Config struct {
	Endpoint    string `json:"endpoint,omitempty"`
	AgentAPIKey string `json:"agent_api_key,omitempty"`
	AgentDID    string `json:"agent_did,omitempty"`
}

// defaultConfigPath returns ~/.atlast/config.json.
func defaultConfigPath() string {
	home, _ := os.UserHomeDir()
	return filepath.Join(home, ".atlast", "config.json")
}

// LoadConfig reads ~/.atlast/config.json. Returns empty Config on any error.
func LoadConfig() Config {
	data, err := os.ReadFile(defaultConfigPath())
	if err != nil {
		return Config{}
	}
	var cfg Config
	_ = json.Unmarshal(data, &cfg)
	return cfg
}

// GetAPIURL returns the API URL with priority: ATLAST_API_URL env > config endpoint > default.
// Always returns a URL ending with /v1.
func GetAPIURL() string {
	if v := os.Getenv("ATLAST_API_URL"); v != "" {
		return normalizeURL(v)
	}
	if ep := LoadConfig().Endpoint; ep != "" {
		return normalizeURL(ep)
	}
	return defaultAPIURL
}

// GetAPIKey returns the API key with priority: ATLAST_API_KEY env > config agent_api_key.
func GetAPIKey() string {
	if v := os.Getenv("ATLAST_API_KEY"); v != "" {
		return v
	}
	return LoadConfig().AgentAPIKey
}

// normalizeURL trims trailing slashes and appends /v1 if not already present.
func normalizeURL(url string) string {
	url = strings.TrimRight(url, "/")
	if !strings.HasSuffix(url, "/v1") {
		url += "/v1"
	}
	return url
}
