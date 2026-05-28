from core.runtime.retry import ProviderErrorClassifier


def test_governance_failures_are_classified_as_governance_validation_error() -> None:
    classifier = ProviderErrorClassifier()
    decision = classifier.classify(
        RuntimeError("governance_validation_error: Governance runtime rejection: some rule failed")
    )
    assert decision.error_type == "governance_validation_error"
    assert decision.classification == "non_retryable"
    assert "Governance validation failed" in decision.user_message

