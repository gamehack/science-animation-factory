"""Separate technical readiness from editorial/scientific approval."""
from dataclasses import dataclass,field
from enum import StrEnum

class ReviewStatus(StrEnum):
    TECHNICAL_FAILED="TECHNICAL_FAILED"
    TECHNICALLY_READY="TECHNICALLY_READY"
    CONTENT_REVIEW_REQUIRED="CONTENT_REVIEW_REQUIRED"
    APPROVED="APPROVED"
    REJECTED="REJECTED"

@dataclass
class QualityReport:
    technical_passed:bool=False
    visual_passed:bool|None=None
    semantic_passed:bool|None=None
    factual_passed:bool|None=None
    findings:list[str]=field(default_factory=list)
    @property
    def status(self):
        if not self.technical_passed: return ReviewStatus.TECHNICAL_FAILED
        if None in (self.visual_passed,self.semantic_passed,self.factual_passed):
            return ReviewStatus.CONTENT_REVIEW_REQUIRED
        if not all((self.visual_passed,self.semantic_passed,self.factual_passed)):
            return ReviewStatus.REJECTED
        return ReviewStatus.APPROVED
    def to_dict(self):
        return {"technical_passed":self.technical_passed,"visual_passed":self.visual_passed,
                "semantic_passed":self.semantic_passed,"factual_passed":self.factual_passed,
                "status":self.status.value,"findings":list(self.findings)}
