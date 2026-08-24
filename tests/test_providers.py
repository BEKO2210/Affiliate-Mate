from affiliate_mate.evidence import EvidenceObservation
from affiliate_mate.models import ProductCandidate
from affiliate_mate.providers import CandidateProvider, EvidenceProvider


class DemoProvider:
    @property
    def name(self):
        return "demo"

    def candidates(self):
        return []

    def collect(self, candidate):
        return [
            EvidenceObservation(
                product_id=candidate.product_id,
                signal="price",
                value=candidate.price,
                source=self.name,
            )
        ]


def test_structural_provider_protocols_are_runtime_checkable():
    provider = DemoProvider()
    assert isinstance(provider, CandidateProvider)
    assert isinstance(provider, EvidenceProvider)


def test_evidence_provider_does_not_decide_opportunity():
    candidate = ProductCandidate(
        product_id="p1",
        title="Widget",
        marketplace="DE",
        currency="EUR",
        price=100,
        commission_rate=0.04,
        monthly_searches=1000,
        youtube_competition=50,
        buyer_intent=60,
        content_gap=60,
    )
    observation = list(DemoProvider().collect(candidate))[0]
    assert observation.signal == "price"
    assert observation.value == 100
