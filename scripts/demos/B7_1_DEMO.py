from datetime import date

from crow_authority import (
    DocumentAuthorityMetadata,
    DocumentAuthorityType,
    ab04_framework,
    resolve_authority,
    summarize_resolution,
)
from crow_knowledge_fusion import (
    FusionStatus,
    KnowledgeCluster,
    KnowledgeFusionResult,
    ValueVariant,
)


def variant(value: str, document_id: str) -> ValueVariant:
    return ValueVariant(
        normalized_value=value,
        unit="L/S",
        candidate_ids=(f"candidate:{document_id}",),
        document_ids=(document_id,),
        confidence_max=0.95,
        confidence_mean=0.95,
    )


clusters = (
    KnowledgeCluster(
        id="cluster:airflow",
        semantic_key="key_value|luftflöde|has_value|l/s",
        subject="Luftflöde",
        predicate="has_value",
        unit="L/S",
        candidate_ids=("candidate:drawing", "candidate:description"),
        document_ids=("drawing", "description"),
        variants=(variant("320", "drawing"), variant("400", "description")),
        status=FusionStatus.CONFLICTING,
        support_count=2,
        fingerprint="airflow-fingerprint",
    ),
    KnowledgeCluster(
        id="cluster:unique",
        semantic_key="quantity|unspecified|has_quantity|mm",
        subject="unspecified",
        predicate="has_quantity",
        unit="MM",
        candidate_ids=("candidate:drawing-new",),
        document_ids=("drawing-new",),
        variants=(
            ValueVariant(
                normalized_value="160",
                unit="MM",
                candidate_ids=("candidate:drawing-new",),
                document_ids=("drawing-new",),
                confidence_max=0.8,
                confidence_mean=0.8,
            ),
        ),
        status=FusionStatus.SINGLETON,
        support_count=1,
        fingerprint="unique-fingerprint",
    ),
)

fusion = KnowledgeFusionResult(project_id="demo", clusters=clusters)
documents = (
    DocumentAuthorityMetadata(
        document_id="drawing",
        authority_type=DocumentAuthorityType.DRAWING,
        title="V-57.1-100",
        issue_date=date(2026, 1, 10),
    ),
    DocumentAuthorityMetadata(
        document_id="description",
        authority_type=DocumentAuthorityType.TECHNICAL_DESCRIPTION,
        title="Teknisk beskrivning",
        issue_date=date(2025, 12, 20),
    ),
    DocumentAuthorityMetadata(
        document_id="drawing-new",
        authority_type=DocumentAuthorityType.DRAWING,
        title="V-57.1-101",
        issue_date=date(2026, 2, 1),
    ),
)

resolution = resolve_authority(fusion, ab04_framework(), documents)
print(summarize_resolution(resolution))
for decision in resolution.decisions:
    print(decision.cluster_id, decision.status.value, decision.accepted_value)
