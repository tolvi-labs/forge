import pytest
from forge.profiles import Profile, load_profile, list_profiles, ProfileError


def test_list_profiles_includes_the_five():
    names = set(list_profiles())
    assert {"react-node", "nextjs", "python-backend", "java-backend",
            "fullstack-firebase"} <= names


def test_load_profile_parses_fields():
    p = load_profile("react-node")
    assert isinstance(p, Profile)
    assert "package.json" in p.static_files
    assert p.rag_top_k == 6
    assert p.vault_enabled is True
    assert p.vault_max_tokens == 6000
    assert p.max_context_tokens == 65536


def test_fullstack_firebase_has_gcp_files_and_wider_topk():
    p = load_profile("fullstack-firebase")
    assert "firestore.rules" in p.static_gcp_files
    assert p.rag_top_k == 8


def test_load_unknown_profile_raises():
    with pytest.raises(ProfileError):
        load_profile("no-such-profile")
