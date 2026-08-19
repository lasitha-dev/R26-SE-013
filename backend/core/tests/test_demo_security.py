"""
Unit tests for safe demo security utilities: Argon2 password hashing and PyJWT access token handling.
"""

import unittest
from datetime import datetime, timezone, timedelta
import jwt

from backend.core.demo_auth_config import DemoAuthConfig
from backend.core.demo_security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
    DemoSecurityError,
    DecodedDemoToken,
    DEMO_JWT_ISSUER,
    DEMO_JWT_AUDIENCE,
    DEMO_TOKEN_TYPE,
)


class TestDemoSecurity(unittest.TestCase):
    VALID_SECRET = "a_super_secret_jwt_signing_key_32_chars"

    def setUp(self):
        self.enabled_config = DemoAuthConfig(
            enabled=True,
            jwt_secret=self.VALID_SECRET,
            jwt_algorithm="HS256",
            expire_minutes=30,
        )
        self.disabled_config = DemoAuthConfig(enabled=False)

    # --- Password Tests ---

    def test_1_hash_differs_from_plaintext(self):
        password = "MySecurePassword123!"
        hashed = hash_password(password)
        self.assertNotEqual(password, hashed)
        self.assertTrue(hashed.startswith("$argon2"))

    def test_2_correct_password_verifies(self):
        password = "MySecurePassword123!"
        hashed = hash_password(password)
        self.assertTrue(verify_password(password, hashed))

    def test_3_wrong_password_fails(self):
        password = "MySecurePassword123!"
        hashed = hash_password(password)
        self.assertFalse(verify_password("WrongPassword123!", hashed))

    def test_4_two_hashes_differ_because_of_salts(self):
        password = "MySecurePassword123!"
        hash1 = hash_password(password)
        hash2 = hash_password(password)
        self.assertNotEqual(hash1, hash2)
        self.assertTrue(verify_password(password, hash1))
        self.assertTrue(verify_password(password, hash2))

    def test_5_malformed_hash_fails_safely(self):
        password = "MySecurePassword123!"
        malformed_hashes = [
            "invalid_hash_string",
            "$argon2id$v=19$m=65536,t=3,p=4$invalidpayload",
            "",
            "   ",
            "12345",
        ]
        for mal_hash in malformed_hashes:
            self.assertFalse(verify_password(password, mal_hash))

    def test_6_no_plaintext_or_hash_in_errors_or_repr(self):
        password = "SecretPasswordToHide"
        try:
            hash_password("")
        except DemoSecurityError as e:
            self.assertNotIn(password, str(e))

        hashed = hash_password(password)
        try:
            # Trigger potential verify error safely
            verify_password(password, "malformed")
        except Exception as e:
            self.assertNotIn(password, str(e))
            self.assertNotIn(hashed, str(e))

    # --- JWT Tests ---

    def test_7_valid_access_token_decodes_successfully(self):
        user_id = "usr_demo_12345"
        token = create_access_token(user_id, self.enabled_config)
        decoded = decode_access_token(token, self.enabled_config)

        self.assertIsInstance(decoded, DecodedDemoToken)
        self.assertEqual(decoded.user_id, user_id)
        self.assertIsNotNone(decoded.token_id)
        self.assertIsInstance(decoded.issued_at, datetime)
        self.assertIsInstance(decoded.expires_at, datetime)

    def test_8_subject_is_preserved(self):
        user_id = "veterinarian_user_99"
        token = create_access_token(user_id, self.enabled_config)
        decoded = decode_access_token(token, self.enabled_config)
        self.assertEqual(decoded.user_id, user_id)

    def test_9_token_ids_are_unique(self):
        user_id = "usr_demo_12345"
        token1 = create_access_token(user_id, self.enabled_config)
        token2 = create_access_token(user_id, self.enabled_config)

        decoded1 = decode_access_token(token1, self.enabled_config)
        decoded2 = decode_access_token(token2, self.enabled_config)

        self.assertNotEqual(decoded1.token_id, decoded2.token_id)

    def test_10_expiration_matches_configured_lifetime(self):
        fixed_now = datetime(2026, 8, 19, 12, 0, 0, tzinfo=timezone.utc)
        token = create_access_token("usr_123", self.enabled_config, now=fixed_now)
        decoded = decode_access_token(token, self.enabled_config, now=fixed_now)

        expected_exp = fixed_now + timedelta(minutes=30)
        self.assertEqual(int(decoded.expires_at.timestamp()), int(expected_exp.timestamp()))

    def test_11_expired_token_is_rejected(self):
        start_time = datetime(2026, 8, 19, 12, 0, 0, tzinfo=timezone.utc)
        token = create_access_token("usr_123", self.enabled_config, now=start_time)

        future_time = start_time + timedelta(minutes=31)
        with self.assertRaises(DemoSecurityError) as ctx:
            decode_access_token(token, self.enabled_config, now=future_time)
        self.assertIn("invalid, expired, or malformed", str(ctx.exception).lower())

    def test_12_wrong_signing_secret_is_rejected(self):
        token = create_access_token("usr_123", self.enabled_config)
        other_config = DemoAuthConfig(
            enabled=True,
            jwt_secret="a_different_secret_key_32_chars_long",
            jwt_algorithm="HS256",
            expire_minutes=30,
        )
        with self.assertRaises(DemoSecurityError):
            decode_access_token(token, other_config)

    def test_13_malformed_token_is_rejected(self):
        malformed_tokens = [
            "invalid.token.str",
            "not_a_jwt",
            "",
            "   ",
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.invalidpayload.signature",
        ]
        for bad_token in malformed_tokens:
            with self.assertRaises(DemoSecurityError):
                decode_access_token(bad_token, self.enabled_config)

    def test_14_missing_sub_is_rejected(self):
        now = datetime.now(timezone.utc)
        payload = {
            "type": DEMO_TOKEN_TYPE,
            "iat": int(now.timestamp()),
            "nbf": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=30)).timestamp()),
            "jti": "some_uuid",
            "iss": DEMO_JWT_ISSUER,
            "aud": DEMO_JWT_AUDIENCE,
        }
        raw_token = jwt.encode(payload, self.VALID_SECRET, algorithm="HS256")
        with self.assertRaises(DemoSecurityError):
            decode_access_token(raw_token, self.enabled_config)

    def test_15_empty_sub_is_rejected(self):
        for empty_sub in ["", "   "]:
            with self.assertRaises(DemoSecurityError):
                create_access_token(empty_sub, self.enabled_config)

        # Direct token crafting with empty sub
        now = datetime.now(timezone.utc)
        payload = {
            "sub": "   ",
            "type": DEMO_TOKEN_TYPE,
            "iat": int(now.timestamp()),
            "nbf": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=30)).timestamp()),
            "jti": "some_uuid",
            "iss": DEMO_JWT_ISSUER,
            "aud": DEMO_JWT_AUDIENCE,
        }
        raw_token = jwt.encode(payload, self.VALID_SECRET, algorithm="HS256")
        with self.assertRaises(DemoSecurityError):
            decode_access_token(raw_token, self.enabled_config)

    def test_16_missing_exp_is_rejected(self):
        now = datetime.now(timezone.utc)
        payload = {
            "sub": "usr_123",
            "type": DEMO_TOKEN_TYPE,
            "iat": int(now.timestamp()),
            "nbf": int(now.timestamp()),
            "jti": "some_uuid",
            "iss": DEMO_JWT_ISSUER,
            "aud": DEMO_JWT_AUDIENCE,
        }
        raw_token = jwt.encode(payload, self.VALID_SECRET, algorithm="HS256")
        with self.assertRaises(DemoSecurityError):
            decode_access_token(raw_token, self.enabled_config)

    def test_17_missing_jti_is_rejected(self):
        now = datetime.now(timezone.utc)
        payload = {
            "sub": "usr_123",
            "type": DEMO_TOKEN_TYPE,
            "iat": int(now.timestamp()),
            "nbf": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=30)).timestamp()),
            "iss": DEMO_JWT_ISSUER,
            "aud": DEMO_JWT_AUDIENCE,
        }
        raw_token = jwt.encode(payload, self.VALID_SECRET, algorithm="HS256")
        with self.assertRaises(DemoSecurityError):
            decode_access_token(raw_token, self.enabled_config)

    def test_18_wrong_issuer_is_rejected(self):
        now = datetime.now(timezone.utc)
        payload = {
            "sub": "usr_123",
            "type": DEMO_TOKEN_TYPE,
            "iat": int(now.timestamp()),
            "nbf": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=30)).timestamp()),
            "jti": "some_uuid",
            "iss": "wrong_issuer",
            "aud": DEMO_JWT_AUDIENCE,
        }
        raw_token = jwt.encode(payload, self.VALID_SECRET, algorithm="HS256")
        with self.assertRaises(DemoSecurityError):
            decode_access_token(raw_token, self.enabled_config)

    def test_19_wrong_audience_is_rejected(self):
        now = datetime.now(timezone.utc)
        payload = {
            "sub": "usr_123",
            "type": DEMO_TOKEN_TYPE,
            "iat": int(now.timestamp()),
            "nbf": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=30)).timestamp()),
            "jti": "some_uuid",
            "iss": DEMO_JWT_ISSUER,
            "aud": "wrong_audience",
        }
        raw_token = jwt.encode(payload, self.VALID_SECRET, algorithm="HS256")
        with self.assertRaises(DemoSecurityError):
            decode_access_token(raw_token, self.enabled_config)

    def test_20_wrong_type_is_rejected(self):
        now = datetime.now(timezone.utc)
        payload = {
            "sub": "usr_123",
            "type": "refresh",
            "iat": int(now.timestamp()),
            "nbf": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=30)).timestamp()),
            "jti": "some_uuid",
            "iss": DEMO_JWT_ISSUER,
            "aud": DEMO_JWT_AUDIENCE,
        }
        raw_token = jwt.encode(payload, self.VALID_SECRET, algorithm="HS256")
        with self.assertRaises(DemoSecurityError):
            decode_access_token(raw_token, self.enabled_config)

    def test_21_future_nbf_is_rejected(self):
        start_time = datetime(2026, 8, 19, 12, 0, 0, tzinfo=timezone.utc)
        future_nbf = start_time + timedelta(minutes=5)

        payload = {
            "sub": "usr_123",
            "type": DEMO_TOKEN_TYPE,
            "iat": int(start_time.timestamp()),
            "nbf": int(future_nbf.timestamp()),
            "exp": int((start_time + timedelta(minutes=30)).timestamp()),
            "jti": "some_uuid",
            "iss": DEMO_JWT_ISSUER,
            "aud": DEMO_JWT_AUDIENCE,
        }
        raw_token = jwt.encode(payload, self.VALID_SECRET, algorithm="HS256")
        with self.assertRaises(DemoSecurityError):
            decode_access_token(raw_token, self.enabled_config, now=start_time)

    def test_22_algorithm_none_is_rejected(self):
        now = datetime.now(timezone.utc)
        payload = {
            "sub": "usr_123",
            "type": DEMO_TOKEN_TYPE,
            "iat": int(now.timestamp()),
            "nbf": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=30)).timestamp()),
            "jti": "some_uuid",
            "iss": DEMO_JWT_ISSUER,
            "aud": DEMO_JWT_AUDIENCE,
        }
        raw_none_token = jwt.encode(payload, key="", algorithm="none")
        with self.assertRaises(DemoSecurityError):
            decode_access_token(raw_none_token, self.enabled_config)

    def test_23_role_scope_permissions_absent_from_generated_token_payload(self):
        token = create_access_token("usr_123", self.enabled_config)
        unverified_payload = jwt.decode(token, options={"verify_signature": False})

        forbidden_keys = [
            "password",
            "password_hash",
            "mongodb_uri",
            "role",
            "authorized_districts",
            "assigned_farms",
            "permissions",
            "scope",
        ]
        for key in forbidden_keys:
            self.assertNotIn(key, unverified_payload)

    def test_24_token_and_signing_secret_never_appear_in_errors_or_repr(self):
        token = create_access_token("usr_123", self.enabled_config)
        decoded = decode_access_token(token, self.enabled_config)

        repr_str = repr(decoded)
        self.assertNotIn(self.VALID_SECRET, repr_str)
        self.assertNotIn(token, repr_str)

        try:
            decode_access_token("invalid_token_string", self.enabled_config)
        except DemoSecurityError as e:
            err_msg = str(e)
            self.assertNotIn(self.VALID_SECRET, err_msg)
            self.assertNotIn("invalid_token_string", err_msg)

    def test_25_disabled_auth_configuration_cannot_create_or_decode_tokens(self):
        with self.assertRaises(DemoSecurityError):
            create_access_token("usr_123", self.disabled_config)

        token = create_access_token("usr_123", self.enabled_config)
        with self.assertRaises(DemoSecurityError):
            decode_access_token(token, self.disabled_config)


if __name__ == "__main__":
    unittest.main()
