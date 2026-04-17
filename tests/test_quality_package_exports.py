from src.quality import (
    UNKNOWN_REASON_EVIDENCE_LOCATION_MISSING,
    UNKNOWN_REASON_EVIDENCE_MISSING,
    UNKNOWN_REASON_UNSPECIFIED,
    enforce_claimset_evidence_policy,
)
from src.quality.claimset_policy import (
    UNKNOWN_REASON_EVIDENCE_LOCATION_MISSING as UNKNOWN_REASON_EVIDENCE_LOCATION_MISSING_DIRECT,
)
from src.quality.claimset_policy import (
    UNKNOWN_REASON_EVIDENCE_MISSING as UNKNOWN_REASON_EVIDENCE_MISSING_DIRECT,
)
from src.quality.claimset_policy import (
    UNKNOWN_REASON_UNSPECIFIED as UNKNOWN_REASON_UNSPECIFIED_DIRECT,
)
from src.quality.claimset_policy import (
    enforce_claimset_evidence_policy as enforce_claimset_evidence_policy_direct,
)


def test_quality_package_exports_claimset_policy_subset():
    assert enforce_claimset_evidence_policy is enforce_claimset_evidence_policy_direct
    assert UNKNOWN_REASON_EVIDENCE_MISSING == UNKNOWN_REASON_EVIDENCE_MISSING_DIRECT
    assert UNKNOWN_REASON_EVIDENCE_LOCATION_MISSING == UNKNOWN_REASON_EVIDENCE_LOCATION_MISSING_DIRECT
    assert UNKNOWN_REASON_UNSPECIFIED == UNKNOWN_REASON_UNSPECIFIED_DIRECT
