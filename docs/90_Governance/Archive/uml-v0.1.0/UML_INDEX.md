

| No. | File | Diagram | Purpose | Primary traceability |
|---:|---|---|---|---|
| 01 | `01_caf_system_context` | CAF System Context | Shows CAF in relation to enterprises, federations, architects, governance bodies, systems and external standards. | CAF-000; CAS-900–910 |
| 02 | `02_cas_portfolio_packages` | CAS Portfolio Package Diagram | Organizes the main CAS series as architecture packages and shows their dependencies. | CAF-000; CAS-100–910 |
| 03 | `03_core_domain_class_model` | Core Domain Class Model | Defines the principal architecture entities and their structural relationships. | CAF-000; CAS-900; CAS-901 |
| 04 | `04_federation_domain_class_model` | Federation Domain Class Model | Models ecosystem participants, federation agreements, shared capabilities, boundaries and governance. | CAS-900; CAS-901; CAS-902 |
| 05 | `05_distributed_governance_components` | Distributed Governance Component Diagram | Shows governance boards, policy services, decision-rights registry, exception handling and assurance integration. | CAS-902; CAS-908 |
| 06 | `06_semantic_knowledge_model` | Semantic and Knowledge Class Model | Combines canonical concepts, local concepts, mappings, knowledge assets, provenance, evidence and stewardship. | CAS-903; CAS-904 |
| 07 | `07_trust_assurance_model` | Trust and Assurance Class Model | Models evidence-based trust, assurance claims, controls, findings and confidence assessments. | CAS-905; CAS-908 |
| 08 | `08_cognitive_reasoning_components` | Federated Cognitive and Reasoning Components | Shows human, AI and analytical participants coordinated through reasoning, knowledge, trust and governance services. | CAS-906; CAS-907 |
| 09 | `09_collective_reasoning_sequence` | Collective Reasoning Sequence Diagram | Illustrates a complete reasoning cycle from observation to decision and knowledge feedback. | CAS-907 |
| 10 | `10_autonomy_state_machine` | Autonomy Lifecycle State Machine | Defines controlled progression, suspension, rollback and revocation of delegated autonomy. | CAS-909 |
| 11 | `11_assurance_activity` | Continuous Assurance Activity Diagram | Shows how objectives, evidence, verification, confidence, findings and corrective action form a closed loop. | CAS-908 |
| 12 | `12_federation_intelligence_pipeline` | Federation Intelligence Pipeline | Shows the transformation from distributed observations into coordinated action, learning and adaptation. | CAS-910 |
| 13 | `13_deployment_reference` | Federated Reference Deployment | Illustrates a technology-neutral deployment topology for multiple organizations and shared federation services. | CAS-901; CAS-903–910 |
| 14 | `14_architecture_review_sequence` | Architecture Review and Approval Sequence | Shows proposal, automated conformance, domain review, board decision, exception handling and publication. | CAF-000; CAS-902; CAS-908 |
| 15 | `15_traceability_model` | Standards Traceability Model | Shows end-to-end traceability from strategic intent through principles, requirements, controls, evidence and architecture decisions. | CAF-000; all CAS |

## Recommended use

Use SVG in the formal CAF/CAS documents. Retain PlantUML as the authoritative editable source. Diagram identifiers and filenames SHOULD remain stable after publication; structural changes SHOULD be versioned through the repository change process.

## Rendering PlantUML

The `.puml` files are standard PlantUML sources and can be rendered using a PlantUML IDE extension, local PlantUML CLI or a CI rendering action. This package includes SVG and PNG outputs rendered from equivalent Graphviz definitions so the diagrams are immediately usable.
