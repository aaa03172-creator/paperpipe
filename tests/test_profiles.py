import unittest
import shutil
from pathlib import Path
from src.profiles.profile_schema import Profile, QuerySpec, Limits, ProfileConfig
from src.profiles.patch_schema import PatchRequest, PatchOp
from src.profiles.patch_apply import apply_patch
from src.profiles.risk_rules import validate_profile
from src.profiles.profile_store import save_profiles_snapshot, load_profiles

class TestProfileSystem(unittest.TestCase):
    def setUp(self):
        self.profile = Profile(
            id="neuro_test",
            title="Neuroscience Test",
            query=QuerySpec(
                must=["brain", "synapse"],
                should=["mouse"],
                must_not=["cancer"]
            ),
            limits=Limits(max_results_per_run=10)
        )
        self.test_yaml = Path("test_profiles.yaml")

    def tearDown(self):
        if self.test_yaml.exists():
            self.test_yaml.unlink()

    def test_patch_apply_add(self):
        """Test adding a term to query.must."""
        patch = PatchRequest(
            target_profile_id="neuro_test",
            ops=[
                PatchOp(op="add", path="query.must", value="neuron", rationale="Testing add")
            ]
        )
        new_profile = apply_patch(self.profile, patch)
        self.assertIn("neuron", new_profile.query.must)
        self.assertIn("brain", new_profile.query.must) # Original kept
        self.assertNotIn("neuron", self.profile.query.must) # Original immutable

    def test_patch_apply_remove(self):
        """Test removing a term."""
        patch = PatchRequest(
             target_profile_id="neuro_test",
             ops=[
                 PatchOp(op="remove", path="query.should", value="mouse", rationale="Testing remove")
             ]
        )
        new_profile = apply_patch(self.profile, patch)
        self.assertNotIn("mouse", new_profile.query.should)

    def test_patch_apply_replace(self):
        """Test replacing a scalar value (limit)."""
        patch = PatchRequest(
            target_profile_id="neuro_test",
            ops=[
                PatchOp(op="replace", path="limits.max_results_per_run", value=50, rationale="Bumping limit")
            ]
        )
        new_profile = apply_patch(self.profile, patch)
        self.assertEqual(new_profile.limits.max_results_per_run, 50)

    def test_risk_rules_valid(self):
        """Test a safe query."""
        errors = validate_profile(self.profile)
        self.assertEqual(len(errors), 0)

    def test_risk_rules_invalid(self):
        """Test a risky query (broad term 'mouse' without anchors)."""
        risky = Profile(
            id="risky",
            title="Risky",
            query=QuerySpec(
                must=["mouse", "model"] # Broad terms only
            )
        )
        errors = validate_profile(risky)
        self.assertEqual(len(errors), 1)
        self.assertIn("RISK", errors[0])
        self.assertIn("fibrosis", errors[0])
        self.assertNotIn("microglia", errors[0])

    def test_risk_rules_accepts_oncology_anchor(self):
        oncology = Profile(
            id="oncology_test",
            title="Oncology Test",
            query=QuerySpec(
                must=["mouse", "tumor"]
            )
        )
        self.assertEqual(validate_profile(oncology), [])

    def test_risk_rules_accepts_immunology_anchor(self):
        immunology = Profile(
            id="immunology_test",
            title="Immunology Test",
            query=QuerySpec(
                must=["therapy", "t cell"]
            )
        )
        self.assertEqual(validate_profile(immunology), [])

    def test_risk_rules_accepts_biomaterials_anchor(self):
        biomaterials = Profile(
            id="biomaterials_test",
            title="Biomaterials Test",
            query=QuerySpec(
                must=["drug", "biomaterial"]
            )
        )
        self.assertEqual(validate_profile(biomaterials), [])

    def test_store_io(self):
        """Test save and load."""
        config = ProfileConfig(profiles=[self.profile])
        save_profiles_snapshot(config, self.test_yaml)
        
        loaded = load_profiles(self.test_yaml)
        self.assertEqual(len(loaded.profiles), 1)
        self.assertEqual(loaded.profiles[0].id, "neuro_test")
        self.assertEqual(loaded.profiles[0].revision, 0)

if __name__ == '__main__':
    unittest.main()
