import unittest
from datetime import date, datetime, timedelta
from catalog_quality import Candidate, Decision, DeadlineStatus, assess, deduplicate, partition

TODAY = date(2026, 11, 28)

def valid(**changes):
    base = dict(title="Community recovery", donor="Donor", official_url="https://donor.org/call/123",
                programme_id="123", round_id="2026", funding_type="grant",
                funding_verified=True, thematic_match="yes", applicant_eligible="yes",
                deadline_status=DeadlineStatus.OPEN, deadline=date(2027, 1, 1),
                evidence_verified=True, source_checked_at=datetime(2026, 11, 28))
    base.update(changes)
    return Candidate(**base)


class QualityTests(unittest.TestCase):
    def test_direct_verified(self):
        self.assertEqual(assess(valid(), today=TODAY).decision, Decision.DIRECT)

    def test_non_grant_never_in_conditional_catalog(self):
        for kind in ("mentoring", "award", "partnership_eoi", "training"):
            self.assertEqual(assess(valid(funding_type=kind), today=TODAY).decision, Decision.REJECT)

    def test_no_theme_or_applicant_rejected(self):
        self.assertEqual(assess(valid(thematic_match="no"), today=TODAY).decision, Decision.REJECT)
        self.assertEqual(assess(valid(applicant_eligible="no"), today=TODAY).decision, Decision.REJECT)

    def test_unknown_needs_review(self):
        self.assertEqual(assess(valid(funding_type="unknown"), today=TODAY).decision, Decision.VERIFY)
        self.assertEqual(assess(valid(deadline_status=DeadlineStatus.UNKNOWN), today=TODAY).decision, Decision.VERIFY)

    def test_rolling_is_valid(self):
        self.assertEqual(assess(valid(deadline_status=DeadlineStatus.ROLLING, deadline=None), today=TODAY).decision, Decision.DIRECT)

    def test_expired_is_rejected_even_when_metadata_says_open(self):
        self.assertEqual(assess(valid(deadline=date(2026, 8, 12)), today=TODAY).decision, Decision.REJECT)

    def test_conditional_consortium(self):
        self.assertEqual(assess(valid(applicant_eligible="conditional", conditions=("international consortium",)), today=TODAY).decision, Decision.CONDITIONAL)

    def test_future_rounds_not_merged(self):
        self.assertEqual(len(deduplicate([valid(), valid(round_id="2027")])), 2)

    def test_different_programme_ids_not_merged(self):
        self.assertEqual(len(deduplicate([valid(), valid(programme_id="456", official_url="https://donor.org/call/456")])), 2)

    def test_analytics_url_dedup(self):
        a = valid(programme_id="", round_id="", official_url="https://donor.org/call/123?utm_source=x")
        b = valid(programme_id="", round_id="", official_url="https://www.donor.org/call/123")
        self.assertEqual(len(deduplicate([a,b])), 1)

    def test_no_limit(self):
        items = [valid(title=str(i), programme_id=str(i), official_url="https://donor.org/call/"+str(i)) for i in range(120)]
        self.assertEqual(len(partition(items, today=TODAY)["direct"]), 120)

if __name__ == "__main__":
    unittest.main()
