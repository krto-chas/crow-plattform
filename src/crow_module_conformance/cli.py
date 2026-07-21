from __future__ import annotations

import argparse
import sys
from datetime import UTC
from importlib import import_module
from pathlib import Path
from typing import Any

from crow_accepted_claims import build_project_accepted_claims, summarize_accepted_claims
from crow_authority import resolve_project, summarize_resolution, write_manifest_template
from crow_authority_discovery import discover_project, summarize_discovery
from crow_claim_extraction import extract_project_claims, summarize_claim_candidates
from crow_commercial_adjustment import (
    apply_project_adjustments,
    summarize_adjustments,
)
from crow_commercial_adjustment import (
    write_profile_template as write_adjustment_profile_template,
)
from crow_commercial_impact import (
    build_project_commercial_impacts,
    summarize_commercial_impacts,
    write_price_book_template,
)
from crow_commercial_review import (
    CommercialReviewStatus,
    initialize_project_commercial_review,
    update_project_commercial_review,
)
from crow_commercial_review import (
    summarize_review as summarize_commercial_review,
)
from crow_decision_engine import evaluate_project, summarize_decisions, write_rule_set_template
from crow_document_intelligence import create_project, import_into_project, load_index, summarize
from crow_estimate_line import build_project_estimate, summarize_estimate
from crow_estimate_revision import build_project_revision, summarize_revision
from crow_estimate_structure import (
    build_project_structure,
    summarize_structured_estimate,
    write_grouping_profile_template,
)
from crow_knowledge_fusion import fuse_project, summarize_fusion
from crow_module_sdk import ModuleRegistry
from crow_observation_engine import observe_project, summarize_observations
from crow_scope_impact import (
    build_project_scope_impacts,
    summarize_scope_impacts,
)
from crow_scope_impact import (
    write_rule_set_template as write_scope_rule_set_template,
)
from crow_technical_delta import (
    build_project_deltas,
    summarize_deltas,
    write_baseline_template,
)
from crow_technical_review import (
    ReviewStatus,
    initialize_project_reviews,
    summarize_reviews,
    update_project_review,
)
from crow_technical_validation import (
    summarize_validation,
    validate_project,
    write_profile_template,
)

from .release_review import review_repository
from .validator import validate_plugin


def _load_plugin(entrypoint: str) -> Any:
    if ":" not in entrypoint:
        raise ValueError("Entrypoint must use module.path:ClassName")
    module_name, attribute_name = entrypoint.split(":", 1)
    module = import_module(module_name)
    factory = getattr(module, attribute_name)
    return factory()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="crow")
    commands = parser.add_subparsers(dest="command", required=True)

    module = commands.add_parser("module")
    module_commands = module.add_subparsers(dest="module_command", required=True)

    validate = module_commands.add_parser("validate")
    validate.add_argument("entrypoint", help="Python entrypoint, e.g. package.plugin:Plugin")
    validate.add_argument("--source-root", type=Path)
    validate.add_argument("--backbone-version", default="1.0.0")
    validate.add_argument("--domain-model-version", default="1.0.0")

    module_commands.add_parser("list", help="Discover and list installed Crow modules")

    project = commands.add_parser("project")
    project_commands = project.add_subparsers(dest="project_command", required=True)
    create = project_commands.add_parser("create")
    create.add_argument("directory", type=Path)
    create.add_argument("--name", required=True)
    create.add_argument("--id")
    import_command = project_commands.add_parser("import")
    import_command.add_argument("project_file", type=Path)
    import_command.add_argument("inputs", nargs="+", type=Path)
    import_command.add_argument("--recursive", action="store_true")
    show = project_commands.add_parser("show")
    show.add_argument("project_file", type=Path)
    show.add_argument("--json", action="store_true")

    review = commands.add_parser("technical-review")
    review_commands = review.add_subparsers(dest="review_command", required=True)
    review_init = review_commands.add_parser("init")
    review_init.add_argument("project_file", type=Path)
    review_init.add_argument("--decisions", type=Path)
    review_init.add_argument("--validation", type=Path)
    review_init.add_argument("--json", action="store_true")
    review_set = review_commands.add_parser("set")
    review_set.add_argument("project_file", type=Path)
    review_set.add_argument("target_id")
    review_set.add_argument(
        "status",
        choices=[status.value for status in ReviewStatus if status != ReviewStatus.PROPOSED],
    )
    review_set.add_argument("--reviewer", required=True)
    review_set.add_argument("--reason", required=True)
    review_set.add_argument("--review-file", type=Path)
    review_set.add_argument("--json", action="store_true")

    estimate = commands.add_parser("estimate")
    estimate_commands = estimate.add_subparsers(
        dest="estimate_command",
        required=True,
    )
    estimate_build = estimate_commands.add_parser("build")
    estimate_build.add_argument("project_file", type=Path)
    estimate_build.add_argument("--estimate-id", required=True)
    estimate_build.add_argument("--commercial", type=Path)
    estimate_build.add_argument("--adjusted", type=Path)
    estimate_build.add_argument("--review", type=Path)
    estimate_build.add_argument("--json", action="store_true")
    estimate_structure_template = estimate_commands.add_parser("structure-template")
    estimate_structure_template.add_argument("output", type=Path)
    estimate_structure = estimate_commands.add_parser("structure")
    estimate_structure.add_argument("project_file", type=Path)
    estimate_structure.add_argument("--structure-id", required=True)
    estimate_structure.add_argument("--profile", type=Path, required=True)
    estimate_structure.add_argument("--estimate", type=Path)
    estimate_structure.add_argument("--json", action="store_true")
    estimate_revision = estimate_commands.add_parser("revision")
    estimate_revision.add_argument("project_file", type=Path)
    estimate_revision.add_argument("--revision-id", required=True)
    estimate_revision.add_argument("--previous", type=Path, required=True)
    estimate_revision.add_argument("--current", type=Path, required=True)
    estimate_revision.add_argument("--include-unchanged", action="store_true")
    estimate_revision.add_argument("--json", action="store_true")

    commercial = commands.add_parser("commercial")
    commercial_commands = commercial.add_subparsers(
        dest="commercial_command",
        required=True,
    )
    commercial_template = commercial_commands.add_parser("template")
    commercial_template.add_argument("output", type=Path)
    commercial_build = commercial_commands.add_parser("build")
    commercial_build.add_argument("project_file", type=Path)
    commercial_build.add_argument("--price-book", type=Path, required=True)
    commercial_build.add_argument("--scope", type=Path)
    commercial_build.add_argument("--json", action="store_true")
    commercial_adjustment_template = commercial_commands.add_parser("adjustment-template")
    commercial_adjustment_template.add_argument("output", type=Path)
    commercial_adjust = commercial_commands.add_parser("adjust")
    commercial_adjust.add_argument("project_file", type=Path)
    commercial_adjust.add_argument("--profile", type=Path, required=True)
    commercial_adjust.add_argument("--commercial", type=Path)
    commercial_adjust.add_argument("--json", action="store_true")
    commercial_review_init = commercial_commands.add_parser("review-init")
    commercial_review_init.add_argument("project_file", type=Path)
    commercial_review_init.add_argument("--adjusted", type=Path)
    commercial_review_init.add_argument("--json", action="store_true")
    commercial_review_set = commercial_commands.add_parser("review-set")
    commercial_review_set.add_argument("project_file", type=Path)
    commercial_review_set.add_argument(
        "status",
        choices=[item.value for item in CommercialReviewStatus],
    )
    commercial_review_set.add_argument("--reviewer", required=True)
    commercial_review_set.add_argument("--reason", required=True)
    commercial_review_set.add_argument("--review-file", type=Path)
    commercial_review_set.add_argument("--json", action="store_true")

    scope = commands.add_parser("scope")
    scope_commands = scope.add_subparsers(dest="scope_command", required=True)
    scope_template = scope_commands.add_parser("template")
    scope_template.add_argument("output", type=Path)
    scope_build = scope_commands.add_parser("build")
    scope_build.add_argument("project_file", type=Path)
    scope_build.add_argument("--rules", type=Path, required=True)
    scope_build.add_argument("--deltas", type=Path)
    scope_build.add_argument("--json", action="store_true")

    delta = commands.add_parser("delta")
    delta_commands = delta.add_subparsers(dest="delta_command", required=True)
    delta_template = delta_commands.add_parser("template")
    delta_template.add_argument("output", type=Path)
    delta_template.add_argument("--project-id", default="project-id")
    delta_build = delta_commands.add_parser("build")
    delta_build.add_argument("project_file", type=Path)
    delta_build.add_argument("--baseline", type=Path, required=True)
    delta_build.add_argument("--decisions", type=Path)
    delta_build.add_argument("--reviews", type=Path)
    delta_build.add_argument("--json", action="store_true")

    technical = commands.add_parser("technical")
    technical_commands = technical.add_subparsers(dest="technical_command", required=True)
    technical_template = technical_commands.add_parser("template")
    technical_template.add_argument("output", type=Path)
    technical_validate = technical_commands.add_parser("validate")
    technical_validate.add_argument("project_file", type=Path)
    technical_validate.add_argument("--profile", type=Path, required=True)
    technical_validate.add_argument("--accepted", type=Path)
    technical_validate.add_argument("--json", action="store_true")

    decide = commands.add_parser("decide")
    decide_commands = decide.add_subparsers(dest="decide_command", required=True)
    decide_template = decide_commands.add_parser("template")
    decide_template.add_argument("output", type=Path)
    decide_run = decide_commands.add_parser("run")
    decide_run.add_argument("project_file", type=Path)
    decide_run.add_argument("--rules", type=Path, required=True)
    decide_run.add_argument("--accepted", type=Path)
    decide_run.add_argument("--json", action="store_true")

    accepted = commands.add_parser("accepted")
    accepted_commands = accepted.add_subparsers(dest="accepted_command", required=True)
    accepted_build = accepted_commands.add_parser("build")
    accepted_build.add_argument("project_file", type=Path)
    accepted_build.add_argument("--fusion", type=Path)
    accepted_build.add_argument("--resolution", type=Path)
    accepted_build.add_argument("--json", action="store_true")

    authority = commands.add_parser("authority")
    authority_commands = authority.add_subparsers(dest="authority_command", required=True)
    authority_discover = authority_commands.add_parser("discover")
    authority_discover.add_argument("project_file", type=Path)
    authority_discover.add_argument("--json", action="store_true")
    authority_resolve = authority_commands.add_parser("resolve")
    authority_resolve.add_argument("project_file", type=Path)
    authority_resolve.add_argument("--manifest", type=Path, required=True)
    authority_resolve.add_argument("--json", action="store_true")
    authority_template = authority_commands.add_parser("template")
    authority_template.add_argument("output", type=Path)

    fuse = commands.add_parser("fuse")
    fuse.add_argument("project_file", type=Path)
    fuse.add_argument("--json", action="store_true")

    claims = commands.add_parser("claims")
    claims.add_argument("project_file", type=Path)
    claims.add_argument("--json", action="store_true")

    observe = commands.add_parser("observe")
    observe.add_argument("project_file", type=Path)
    observe.add_argument("--json", action="store_true")

    review = commands.add_parser("review")
    review.add_argument("--root", type=Path, default=Path("."))
    review.add_argument("--release", default="0.7.0-alpha.1")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "project":
        if args.project_command == "create":
            project_file = create_project(args.directory, args.name, args.id)
            print(f"Created Crow project: {project_file}")
            return 0
        if args.project_command == "import":
            index, session = import_into_project(
                args.project_file,
                args.inputs,
                args.recursive,
            )
            for result in session.results:
                print(f"{result.outcome.value.upper()}: {result.path} — {result.message}")
            print(
                f"Import session {session.id}: {session.status.value}, "
                f"{session.imported_count} imported, {session.failed_count} failed"
            )
            summary = summarize(index)
            print(
                f"Project contains {summary['documents_active']} active documents "
                f"({summary['superseded']} superseded)"
            )
            return 0
        if args.project_command == "show":
            import json

            summary = summarize(load_index(args.project_file))
            if args.json:
                print(json.dumps(summary, ensure_ascii=False, indent=2))
            else:
                print(f"Project: {summary['project_name']} [{summary['project_id']}]")
                print(f"Active documents: {summary['documents_active']}")
                print(f"Superseded: {summary['superseded']}")
                for name, count in summary["types"].items():
                    print(f"  {name}: {count}")
            return 0
        return 2

    if args.command == "technical-review":
        if args.review_command == "init":
            review_result, output = initialize_project_reviews(
                args.project_file,
                args.decisions,
                args.validation,
            )
            review_summary = summarize_reviews(review_result)
            if args.json:
                import json

                print(json.dumps(review_summary, ensure_ascii=False, indent=2))
            else:
                print(f"Review records: {review_summary['records']}")
                for name, count in review_summary["by_target_type"].items():
                    print(f"  target {name}: {count}")
                print(f"Saved: {output}")
            return 0
        if args.review_command == "set":
            review_result, output = update_project_review(
                args.project_file,
                args.target_id,
                ReviewStatus(args.status),
                args.reviewer,
                args.reason,
                args.review_file,
            )
            review_summary = summarize_reviews(review_result)
            if args.json:
                import json

                print(json.dumps(review_summary, ensure_ascii=False, indent=2))
            else:
                print(f"Updated target: {args.target_id}")
                print(f"New status: {args.status}")
                print(f"Saved: {output}")
            return 0
        return 2

    if args.command == "estimate":
        if args.estimate_command == "revision":
            revision, output = build_project_revision(
                args.project_file,
                args.revision_id,
                args.previous,
                args.current,
                include_unchanged=args.include_unchanged,
            )
            revision_summary = summarize_revision(revision)
            if args.json:
                import json

                print(json.dumps(revision_summary, ensure_ascii=False, indent=2))
            else:
                print(f"Revision: {revision_summary['revision_id']}")
                print(f"Added: {revision_summary['added']}")
                print(f"Removed: {revision_summary['removed']}")
                print(f"Modified: {revision_summary['modified']}")
                print(
                    f"Total delta: {revision_summary['total_delta']} {revision_summary['currency']}"
                )
                print(f"Saved: {output}")
            return 0
        if args.estimate_command == "structure-template":
            write_grouping_profile_template(args.output)
            print(f"Created estimate structure template: {args.output}")
            return 0
        if args.estimate_command == "structure":
            structured, output = build_project_structure(
                args.project_file,
                args.structure_id,
                args.profile,
                args.estimate,
            )
            structure_summary = summarize_structured_estimate(structured)
            if args.json:
                import json

                print(json.dumps(structure_summary, ensure_ascii=False, indent=2))
            else:
                print(f"Structure: {structure_summary['structure_id']}")
                print(f"Sections: {structure_summary['sections']}")
                print(f"Groups: {structure_summary['groups']}")
                print(f"Lines: {structure_summary['lines']}")
                print(
                    f"Grand total: {structure_summary['grand_total']} "
                    f"{structure_summary['currency']}"
                )
                print(f"Saved: {output}")
            return 0
        if args.estimate_command == "build":
            estimate_result, output = build_project_estimate(
                args.project_file,
                args.estimate_id,
                args.commercial,
                args.adjusted,
                args.review,
            )
            estimate_summary = summarize_estimate(estimate_result)
            if args.json:
                import json

                print(json.dumps(estimate_summary, ensure_ascii=False, indent=2))
            else:
                print(f"Estimate: {estimate_summary['estimate_id']}")
                print(f"Lines: {estimate_summary['lines']}")
                print(f"Net total: {estimate_summary['net_total']}")
                print(f"Adjustments: {estimate_summary['adjustment_total']}")
                print(
                    f"Grand total: {estimate_summary['grand_total']} {estimate_summary['currency']}"
                )
                print(f"Saved: {output}")
            return 0
        return 2

    if args.command == "commercial":
        if args.commercial_command == "template":
            write_price_book_template(args.output)
            print(f"Created price-book template: {args.output}")
            return 0
        if args.commercial_command == "review-init":
            review, output = initialize_project_commercial_review(
                args.project_file,
                args.adjusted,
            )
            commercial_review_summary = summarize_commercial_review(review)
            if args.json:
                import json

                print(json.dumps(commercial_review_summary, ensure_ascii=False, indent=2))
            else:
                print(f"Commercial review status: {commercial_review_summary['status']}")
                print(
                    f"Grand total: {commercial_review_summary['grand_total']} "
                    f"{commercial_review_summary['currency']}"
                )
                print(f"Unresolved: {commercial_review_summary['unresolved']}")
                print(f"Saved: {output}")
            return 0
        if args.commercial_command == "review-set":
            from datetime import datetime

            review, output = update_project_commercial_review(
                args.project_file,
                CommercialReviewStatus(args.status),
                args.reviewer,
                args.reason,
                datetime.now(UTC),
                args.review_file,
            )
            commercial_review_summary = summarize_commercial_review(review)
            if args.json:
                import json

                print(json.dumps(commercial_review_summary, ensure_ascii=False, indent=2))
            else:
                print(f"Commercial review status: {commercial_review_summary['status']}")
                print(f"Events: {commercial_review_summary['events']}")
                print(f"Approved: {commercial_review_summary['approved']}")
                print(f"Saved: {output}")
            return 0
        if args.commercial_command == "adjustment-template":
            write_adjustment_profile_template(args.output)
            print(f"Created commercial-adjustment profile: {args.output}")
            return 0
        if args.commercial_command == "adjust":
            adjusted_result, output = apply_project_adjustments(
                args.project_file,
                args.profile,
                args.commercial,
            )
            adjusted_summary = summarize_adjustments(adjusted_result)
            if args.json:
                import json

                print(json.dumps(adjusted_summary, ensure_ascii=False, indent=2))
            else:
                print(f"Currency: {adjusted_summary['currency']}")
                print(f"Net total: {adjusted_summary['net_total']}")
                print(f"Adjustments: {adjusted_summary['adjustment_total']}")
                print(f"Grand total: {adjusted_summary['grand_total']}")
                print(f"Unresolved: {adjusted_summary['unresolved']}")
                for name, amount in adjusted_summary["by_kind"].items():
                    print(f"  {name}: {amount}")
                print(f"Saved: {output}")
            return 0
        if args.commercial_command == "build":
            commercial_result, output = build_project_commercial_impacts(
                args.project_file,
                args.price_book,
                args.scope,
            )
            commercial_summary = summarize_commercial_impacts(commercial_result)
            if args.json:
                import json

                print(json.dumps(commercial_summary, ensure_ascii=False, indent=2))
            else:
                print(f"Currency: {commercial_summary['currency']}")
                print(f"Items: {commercial_summary['items']}")
                print(f"Priced total: {commercial_summary['total']}")
                print(f"Unresolved: {commercial_summary['unresolved']}")
                for name, count in commercial_summary["by_status"].items():
                    print(f"  status {name}: {count}")
                for name, amount in commercial_summary["by_cost_type"].items():
                    print(f"  cost {name}: {amount}")
                print(f"Saved: {output}")
            return 0
        return 2

    if args.command == "scope":
        if args.scope_command == "template":
            write_scope_rule_set_template(args.output)
            print(f"Created scope-impact rule-set template: {args.output}")
            return 0
        if args.scope_command == "build":
            scope_result, output = build_project_scope_impacts(
                args.project_file,
                args.rules,
                args.deltas,
            )
            scope_summary = summarize_scope_impacts(scope_result)
            if args.json:
                import json

                print(json.dumps(scope_summary, ensure_ascii=False, indent=2))
            else:
                print(f"Baseline: {scope_summary['baseline_id']}")
                print(f"Scope impacts: {scope_summary['total']}")
                print(f"Review required: {scope_summary['review_required']}")
                for name, count in scope_summary["by_type"].items():
                    print(f"  {name}: {count}")
                print(f"Saved: {output}")
            return 0
        return 2

    if args.command == "delta":
        if args.delta_command == "template":
            write_baseline_template(args.output, args.project_id)
            print(f"Created technical baseline template: {args.output}")
            return 0
        if args.delta_command == "build":
            delta_result, output = build_project_deltas(
                args.project_file,
                args.baseline,
                args.decisions,
                args.reviews,
            )
            delta_summary = summarize_deltas(delta_result)
            if args.json:
                import json

                print(json.dumps(delta_summary, ensure_ascii=False, indent=2))
            else:
                print(f"Baseline: {delta_summary['baseline_id']}")
                print(f"Deltas: {delta_summary['total']}")
                print(f"Changed: {delta_summary['changed']}")
                for name, count in delta_summary["by_type"].items():
                    print(f"  {name}: {count}")
                print(f"Saved: {output}")
            return 0
        return 2

    if args.command == "technical":
        if args.technical_command == "template":
            write_profile_template(args.output)
            print(f"Created technical validation profile: {args.output}")
            return 0
        if args.technical_command == "validate":
            validation_result, output = validate_project(
                args.project_file,
                args.profile,
                args.accepted,
            )
            validation_summary = summarize_validation(validation_result)
            if args.json:
                import json

                print(json.dumps(validation_summary, ensure_ascii=False, indent=2))
            else:
                print(f"Profile: {validation_summary['profile_id']}")
                print(f"Requirements checked: {validation_summary['checked_requirements']}")
                print(f"Issues: {validation_summary['issues']}")
                print(f"Blocking: {validation_summary['blocking']}")
                for name, count in validation_summary["by_type"].items():
                    print(f"  type {name}: {count}")
                for name, count in validation_summary["by_severity"].items():
                    print(f"  severity {name}: {count}")
                print(f"Saved: {output}")
            return 0
        return 2

    if args.command == "decide":
        if args.decide_command == "template":
            write_rule_set_template(args.output)
            print(f"Created technical rule-set template: {args.output}")
            return 0
        if args.decide_command == "run":
            decision_result, output = evaluate_project(
                args.project_file,
                args.rules,
                args.accepted,
            )
            decision_summary = summarize_decisions(decision_result)
            if args.json:
                import json

                print(json.dumps(decision_summary, ensure_ascii=False, indent=2))
            else:
                print(f"Rule set: {decision_summary['rule_set_id']}")
                print(f"Evaluations: {decision_summary['evaluated']}")
                print(f"Decision candidates: {decision_summary['candidates']}")
                for name, count in decision_summary["by_severity"].items():
                    print(f"  severity {name}: {count}")
                for name, count in decision_summary["by_category"].items():
                    print(f"  category {name}: {count}")
                print(f"Saved: {output}")
            return 0
        return 2

    if args.command == "accepted":
        if args.accepted_command == "build":
            accepted_claims, output = build_project_accepted_claims(
                args.project_file,
                fusion_file=args.fusion,
                resolution_file=args.resolution,
            )
            accepted_summary = summarize_accepted_claims(accepted_claims)
            if args.json:
                import json

                print(json.dumps(accepted_summary, ensure_ascii=False, indent=2))
            else:
                print(f"Accepted claims: {accepted_summary['accepted']}")
                print(f"Pending claims: {accepted_summary['pending']}")
                print(f"Average confidence: {accepted_summary['average_confidence']}")
                for name, count in accepted_summary["by_basis"].items():
                    print(f"  {name}: {count}")
                print(f"Saved: {output}")
            return 0
        return 2

    if args.command == "authority":
        if args.authority_command == "discover":
            discovery, discovery_report_path, discovery_manifest_path = discover_project(
                args.project_file
            )
            discovery_summary = summarize_discovery(discovery)
            if args.json:
                import json

                print(json.dumps(discovery_summary, ensure_ascii=False, indent=2))
            else:
                print(f"Contract framework: {discovery_summary['contract_framework']}")
                print(f"Authority framework: {discovery_summary['framework_id']}")
                print(f"Project override: {discovery_summary['project_override']}")
                print(f"Documents classified: {discovery_summary['documents']}")
                print(f"Requires review: {discovery_summary['requires_review']}")
                print(f"Report: {discovery_report_path}")
                print(f"Manifest: {discovery_manifest_path}")
            return 0
        if args.authority_command == "template":
            write_manifest_template(args.output)
            print(f"Created authority manifest template: {args.output}")
            return 0
        if args.authority_command == "resolve":
            authority_resolution, output = resolve_project(
                args.project_file,
                args.manifest,
            )
            authority_summary = summarize_resolution(authority_resolution)
            if args.json:
                import json

                print(json.dumps(authority_summary, ensure_ascii=False, indent=2))
            else:
                print(f"Framework: {authority_summary['framework_id']}")
                print(f"Project override: {authority_summary['project_override']}")
                print(f"Decisions: {authority_summary['decisions']}")
                print(f"Resolved: {authority_summary['resolved']}")
                print(f"Unresolved: {authority_summary['unresolved']}")
                for name, count in authority_summary["by_status"].items():
                    print(f"  {name}: {count}")
                print(f"Saved: {output}")
            return 0
        return 2

    if args.command == "fuse":
        fusion_result, output = fuse_project(args.project_file)
        fusion_summary = summarize_fusion(fusion_result)
        if args.json:
            import json

            print(json.dumps(fusion_summary, ensure_ascii=False, indent=2))
        else:
            print(f"Knowledge clusters: {fusion_summary['clusters']}")
            print(f"Singleton: {fusion_summary['singleton']}")
            print(f"Consistent: {fusion_summary['consistent']}")
            print(f"Conflicting: {fusion_summary['conflicting']}")
            print(f"Value variants: {fusion_summary['value_variants']}")
            print(f"Saved: {output}")
        return 0

    if args.command == "claims":
        candidates, output = extract_project_claims(args.project_file)
        claim_summary = summarize_claim_candidates(candidates)
        if args.json:
            import json

            print(json.dumps(claim_summary, ensure_ascii=False, indent=2))
        else:
            print(f"Claim candidates: {claim_summary['candidates']}")
            print(f"Unique candidates: {claim_summary['unique_candidates']}")
            print(f"Duplicates: {claim_summary['duplicates']}")
            print(f"Average confidence: {claim_summary['average_confidence']}")
            for name, count in claim_summary["by_type"].items():
                print(f"  {name}: {count}")
            print(f"Saved: {output}")
        return 0

    if args.command == "observe":
        collection, output = observe_project(args.project_file)
        observation_summary = summarize_observations(collection)
        if args.json:
            import json

            print(json.dumps(observation_summary, ensure_ascii=False, indent=2))
        else:
            print(f"Observations: {observation_summary['observations']}")
            print(f"Unique content: {observation_summary['unique_content']}")
            print(f"Duplicates: {observation_summary['duplicates']}")
            for name, count in observation_summary["by_type"].items():
                print(f"  {name}: {count}")
            print(f"Saved: {output}")
        return 0

    if args.command == "review":
        architecture_review = review_repository(args.root, release=args.release)
        for check in architecture_review.checks:
            print(f"{check.status.value.upper()} {check.id}: {check.description}")
            if check.detail:
                print(f"  {check.detail}")
        return 0 if architecture_review.passed else 1

    if args.command != "module":
        return 2

    if args.module_command == "list":
        registry = ModuleRegistry()
        discovered = registry.discover()
        if not discovered:
            print("No installed Crow modules discovered")
            return 0
        for item in registry.list():
            print(f"{item.module_id} {item.version} [{item.origin}]")
        return 0

    if args.module_command != "validate":
        return 2

    try:
        plugin = _load_plugin(args.entrypoint)
        conformance_report = validate_plugin(
            plugin,
            module_source_root=args.source_root,
            backbone_version=args.backbone_version,
            domain_model_version=args.domain_model_version,
        )
    except (ImportError, AttributeError, TypeError, ValueError) as error:
        print(f"FAIL CMC-000: {error}")
        return 2

    manifest = plugin.manifest()
    print(f"Crow module: {manifest.module_id} {manifest.version}")
    if conformance_report.passed:
        print("PASS: module is Crow-compatible")
        return 0

    for issue in conformance_report.issues:
        print(f"FAIL {issue.code}: {issue.message}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
