"""Conservative eligibility gates for NGO Grants AI catalog candidates.

This module does not fetch URLs or infer evidence from missing metadata.
The upstream extractor must attach verified fields from official sources.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Iterable
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
import re
import unicodedata


class Decision(str, Enum):
    DIRECT = "direct"
    CONDITIONAL = "conditional"
    VERIFY = "needs_verification"
    REJECT = "reject"


class DeadlineStatus(str, Enum):
    OPEN = "open_confirmed"
    ROLLING = "rolling_confirmed"
    UPCOMING = "upcoming"
    UNKNOWN = "unknown"
    CLOSED = "closed"


GRANT_TYPES = frozenset({"grant", "microgrant", "subgrant"})
NON_GRANT_TYPES = frozenset({
    "mentoring", "training", "award", "prize", "partnership_eoi",
    "procurement", "loan", "contract", "fellowship_non_grant",
})


@dataclass(frozen=True)
class Candidate:
    title: str
    donor: str = ""
    official_url: str = ""
    programme_id: str = ""
    round_id: str = ""
    funding_type: str = "unknown"
    funding_verified: bool = False
    thematic_match: str = "unknown"  # yes | partial | no | unknown
    applicant_eligible: str = "unknown"  # yes | conditional | no | unknown
    conditions: tuple[str, ...] = ()
    deadline_status: DeadlineStatus = DeadlineStatus.UNKNOWN
    deadline: date | None = None
    evidence_verified: bool = False
    # The record may originate in Telegram, but direct catalogs need an official source.
    source_checked_at: datetime | None = None


@dataclass(frozen=True)
class Assessment:
    decision: Decision
    reasons: tuple[str, ...] = ()


def assess(candidate: Candidate, *, grant_only: bool = True,
           include_upcoming: bool = False, today: date | None = None) -> Assessment:
    """Return the strictest applicable decision without silently filling evidence gaps."""
    today = today or date.today()
    reasons: list[str] = []
    typ = candidate.funding_type.lower().strip()
    theme = candidate.thematic_match.lower().strip()
    eligible = candidate.applicant_eligible.lower().strip()

    if theme == "no":
        return Assessment(Decision.REJECT, ("thematic_mismatch",))
    if eligible == "no":
        return Assessment(Decision.REJECT, ("applicant_ineligible",))
    if candidate.deadline_status == DeadlineStatus.CLOSED:
        return Assessment(Decision.REJECT, ("application_closed",))
    if candidate.deadline is not None and candidate.deadline < today and (
        candidate.deadline_status != DeadlineStatus.ROLLING
    ):
        return Assessment(Decision.REJECT, ("expired_deadline",))
    if grant_only and typ in NON_GRANT_TYPES:
        return Assessment(Decision.REJECT, ("not_grant_funding",))
    if candidate.deadline_status == DeadlineStatus.UPCOMING and not include_upcoming:
        return Assessment(Decision.REJECT, ("applications_not_open_yet",))

    if grant_only and (typ not in GRANT_TYPES or not candidate.funding_verified):
        reasons.append("grant_funding_not_verified")
    if not candidate.official_url or not candidate.evidence_verified:
        reasons.append("official_source_not_verified")
    if candidate.source_checked_at is None:
        reasons.append("source_check_date_missing")
    if candidate.deadline_status == DeadlineStatus.UNKNOWN:
        reasons.append("deadline_not_verified")
    if candidate.deadline_status == DeadlineStatus.OPEN and candidate.deadline is None:
        reasons.append("open_deadline_date_missing")
    if theme == "unknown":
        reasons.append("theme_not_verified")
    if eligible == "unknown":
        reasons.append("applicant_eligibility_not_verified")
    if reasons:
        return Assessment(Decision.VERIFY, tuple(reasons))

    if theme == "partial":
        reasons.append("partial_thematic_match")
    if eligible == "conditional":
        reasons.append("conditional_applicant_eligibility")
    if candidate.conditions:
        reasons.extend("condition: " + item for item in candidate.conditions)
    if reasons:
        return Assessment(Decision.CONDITIONAL, tuple(reasons))
    return Assessment(Decision.DIRECT)


def normalized_url(url: str) -> str:
    """Discard common analytics parameters, preserve grant-identifying parameters."""
    if not url:
        return ""
    parsed = urlsplit(url.strip())
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return ""
    keep = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True)
            if not (k.lower().startswith("utm_") or k.lower() in
                    {"fbclid", "gclid", "mc_cid", "mc_eid"})]
    return urlunsplit(("https", parsed.netloc.lower().removeprefix("www."),
                       parsed.path.rstrip("/") or "/", urlencode(sorted(keep)), ""))


def _text_key(value: str) -> str:
    value = unicodedata.normalize("NFKC", value or "").casefold()
    return re.sub(r"[^\w]+", " ", value, flags=re.UNICODE).strip()


def same_call(a: Candidate, b: Candidate) -> bool:
    """Avoid conflating different calls or rounds under one umbrella programme."""
    if a.programme_id and b.programme_id:
        if _text_key(a.programme_id) != _text_key(b.programme_id):
            return False
        if a.round_id and b.round_id:
            return _text_key(a.round_id) == _text_key(b.round_id)
        # A missing round identifier is uncertain, not proof of identity.
        return False
    if a.round_id and b.round_id and _text_key(a.round_id) != _text_key(b.round_id):
        return False
    ua, ub = normalized_url(a.official_url), normalized_url(b.official_url)
    if ua and ub and ua == ub:
        # A generic programme landing page is insufficient when rounds are ambiguous.
        return not (a.round_id or b.round_id)
    return bool(a.title and b.title and a.donor and b.donor
                and _text_key(a.title) == _text_key(b.title)
                and _text_key(a.donor) == _text_key(b.donor)
                and a.round_id == b.round_id
                and (a.deadline == b.deadline or a.deadline is None or b.deadline is None))


def deduplicate(candidates: Iterable[Candidate]) -> list[Candidate]:
    """Keep original order; do not impose a cap on legitimate results."""
    selected: list[Candidate] = []
    for candidate in candidates:
        if not any(same_call(candidate, previous) for previous in selected):
            selected.append(candidate)
    return selected


def partition(candidates: Iterable[Candidate], **kwargs) -> dict[str, list[Candidate]]:
    """Produce two publishable groups and explicit unpublished review/reject queues."""
    output: dict[str, list[Candidate]] = {decision.value: [] for decision in Decision}
    for candidate in deduplicate(candidates):
        output[assess(candidate, **kwargs).decision.value].append(candidate)
    return output
