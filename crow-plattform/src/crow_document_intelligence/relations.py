from __future__ import annotations

from .models import CrowDocument, DocumentRelation, DocumentRole, DocumentStatus, DocumentType


def infer_document_relations(
    documents: tuple[CrowDocument, ...],
) -> tuple[DocumentRelation, ...]:
    active = [document for document in documents if document.status == DocumentStatus.INDEXED]
    relations: list[DocumentRelation] = []

    authority_documents = [
        document for document in active if document.role == DocumentRole.AUTHORITY
    ]
    primary_documents = [document for document in active if document.role == DocumentRole.PRIMARY]
    reference_documents = [
        document for document in active if document.role == DocumentRole.REFERENCE
    ]

    for authority in authority_documents:
        for target in primary_documents:
            relations.append(
                DocumentRelation(
                    source_document_id=authority.id,
                    target_document_id=target.id,
                    relation_type="governs",
                    confidence=0.60,
                    evidence="Rule-based role relation: AUTHORITY → PRIMARY",
                )
            )

    for reference in reference_documents:
        for target in primary_documents:
            relations.append(
                DocumentRelation(
                    source_document_id=target.id,
                    target_document_id=reference.id,
                    relation_type="references",
                    confidence=0.45,
                    evidence="Rule-based role relation: PRIMARY → REFERENCE",
                )
            )

    drawings = [
        document for document in primary_documents if document.document_type == DocumentType.DRAWING
    ]
    specifications = [
        document
        for document in primary_documents
        if document.document_type == DocumentType.TECHNICAL_SPECIFICATION
    ]
    for specification in specifications:
        for drawing in drawings:
            relations.append(
                DocumentRelation(
                    source_document_id=specification.id,
                    target_document_id=drawing.id,
                    relation_type="describes",
                    confidence=0.55,
                    evidence="Rule-based type relation: specification → drawing",
                )
            )

    unique: dict[tuple[str, str, str], DocumentRelation] = {}
    for relation in relations:
        key = (
            relation.source_document_id,
            relation.target_document_id,
            relation.relation_type,
        )
        unique[key] = relation
    return tuple(unique.values())
