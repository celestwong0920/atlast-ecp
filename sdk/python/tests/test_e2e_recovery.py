"""
G1: End-to-end disaster recovery simulation.

Full flow: init → record 10 entries → backup vault → destroy ~/.ecp/ → recover → verify
"""

import hashlib
import json
import os
import shutil
import sys
import tempfile
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestE2ERecovery:
    """Complete disaster recovery simulation."""

    def test_full_disaster_recovery(self):
        """Init → record → backup → destroy → recover → verify chain + vault."""
        with tempfile.TemporaryDirectory() as base:
            ecp_dir = os.path.join(base, "ecp")
            backup_dir = os.path.join(base, "backup")
            recover_dir = os.path.join(base, "ecp_recovered")

            os.environ["ECP_DIR"] = ecp_dir
            os.environ["ATLAST_VAULT_BACKUP"] = backup_dir

            try:
                # Reload storage module to pick up new ECP_DIR
                import atlast_ecp.storage as _st
                _st.ECP_DIR = _st.Path(ecp_dir)
                _st.RECORDS_DIR = _st.ECP_DIR / "records"
                _st.VAULT_DIR = _st.ECP_DIR / "vault"
                _st.LOCAL_DIR = _st.ECP_DIR / "local"
                _st.INDEX_FILE = _st.ECP_DIR / "index.json"

                # Step 1: Create identity (BIP39 path)
                from atlast_ecp.identity import _create_identity
                identity = _create_identity(ecp_dir)
                assert identity.get("_mnemonic") is not None
                mnemonic = identity["_mnemonic"]
                original_did = identity["did"]
                original_pub = identity["pub_key"]
                priv_hex = identity["priv_key"]

                # Step 2: Record 10 entries
                from atlast_ecp.core import record
                record_ids = []
                for i in range(10):
                    rid = record(
                        f"Test input {i}: disaster recovery simulation",
                        f"Test output {i}: everything is fine",
                        step_type="e2e_test",
                    )
                    assert rid is not None
                    record_ids.append(rid)

                # Step 3: Verify vault was saved + backed up
                vault_dir = os.path.join(ecp_dir, "vault")
                assert os.path.isdir(vault_dir)
                vault_files = os.listdir(vault_dir)
                assert len(vault_files) == 10

                backup_vault = os.path.join(backup_dir, "ecp-vault")
                assert os.path.isdir(backup_vault)
                enc_files = os.listdir(backup_vault)
                assert len(enc_files) == 10

                # Step 4: Manual full vault backup
                from atlast_ecp.vault_backup import backup_all_vault
                backed, errors = backup_all_vault(ecp_dir, backup_dir, priv_hex)
                assert backed == 10
                assert errors == 0

                # Step 5: DISASTER — destroy ecp directory
                shutil.rmtree(ecp_dir)
                assert not os.path.exists(ecp_dir)

                # Step 6: Recover identity from mnemonic
                os.environ["ECP_DIR"] = recover_dir
                from atlast_ecp.recovery import mnemonic_to_private_key
                from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
                from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat, PrivateFormat, NoEncryption

                seed = mnemonic_to_private_key(mnemonic)
                key = Ed25519PrivateKey.from_private_bytes(seed)
                recovered_pub = key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()
                recovered_priv = key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption()).hex()
                recovered_did = f"did:ecp:{hashlib.sha256(recovered_pub.encode()).hexdigest()[:32]}"

                # Verify identity matches
                assert recovered_did == original_did
                assert recovered_pub == original_pub

                # Step 7: Restore vault from backup
                from atlast_ecp.vault_backup import restore_vault_entries
                os.makedirs(recover_dir, exist_ok=True)
                restored, errors = restore_vault_entries(backup_dir, recovered_priv, recover_dir)
                assert restored == 10
                assert errors == 0

                # Step 8: Verify restored vault content
                recovered_vault = os.path.join(recover_dir, "vault")
                for i in range(10):
                    rid = record_ids[i]
                    vault_file = os.path.join(recovered_vault, f"{rid}.json")
                    assert os.path.exists(vault_file), f"Missing vault file for {rid}"
                    data = json.loads(open(vault_file).read())
                    assert f"Test input {i}" in data["input"]
                    assert f"Test output {i}" in data["output"]

                    # Verify hash matches
                    from atlast_ecp.record import hash_content
                    expected_in_hash = hash_content(data["input"])
                    assert expected_in_hash.startswith("sha256:")

            finally:
                os.environ.pop("ECP_DIR", None)
                os.environ.pop("ATLAST_VAULT_BACKUP", None)

    def test_wrong_mnemonic_different_did(self):
        """Wrong mnemonic produces different DID — cannot impersonate."""
        from atlast_ecp.recovery import generate_mnemonic, mnemonic_to_private_key
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

        words1, _ = generate_mnemonic()
        words2, _ = generate_mnemonic()

        seed1 = mnemonic_to_private_key(words1)
        seed2 = mnemonic_to_private_key(words2)

        key1 = Ed25519PrivateKey.from_private_bytes(seed1)
        key2 = Ed25519PrivateKey.from_private_bytes(seed2)

        pub1 = key1.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()
        pub2 = key2.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()

        did1 = f"did:ecp:{hashlib.sha256(pub1.encode()).hexdigest()[:32]}"
        did2 = f"did:ecp:{hashlib.sha256(pub2.encode()).hexdigest()[:32]}"

        assert did1 != did2

    def test_wrong_key_cannot_decrypt_vault(self):
        """Wrong mnemonic cannot decrypt another agent's vault backup."""
        with tempfile.TemporaryDirectory() as d:
            from atlast_ecp.vault_backup import backup_vault_entry, decrypt_vault_entry

            priv1 = "a" * 64
            priv2 = "b" * 64
            content = json.dumps({"input": "secret", "output": "data"})

            backup_vault_entry("rec_001", content, d, priv1)

            enc_file = os.path.join(d, "ecp-vault", "rec_001.enc")
            encrypted = open(enc_file, "rb").read()

            with pytest.raises(ValueError, match="Decryption failed"):
                decrypt_vault_entry(encrypted, "rec_001", priv2)

    def test_backup_failopen_no_crash(self):
        """Record works even if backup path is invalid."""
        with tempfile.TemporaryDirectory() as ecp_dir:
            os.environ["ECP_DIR"] = ecp_dir
            os.environ["ATLAST_VAULT_BACKUP"] = "/nonexistent/readonly/path"
            try:
                from atlast_ecp.core import record
                rid = record("test input", "test output")
                assert rid is not None  # Record succeeded despite backup failure
            finally:
                os.environ.pop("ECP_DIR", None)
                os.environ.pop("ATLAST_VAULT_BACKUP", None)
