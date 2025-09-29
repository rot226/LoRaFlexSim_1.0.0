from loraflexsim.launcher.crypto import cmac


def test_cmac_empty_message_matches_rfc4493_vector():
    """La RFC 4493 Section 4 fournit la valeur de référence du CMAC pour un message vide."""
    key = bytes.fromhex("2b7e151628aed2a6abf7158809cf4f3c")
    expected = bytes.fromhex("bb1d6929e95937287fa37d129b756746")

    assert cmac(key, b"") == expected
