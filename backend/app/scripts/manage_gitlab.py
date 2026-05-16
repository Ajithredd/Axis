"""Axis — CLI for GitLab Project Management."""

import argparse
import sys
import json
from typing import List
from app.services.gitlab import gitlab_service

def main():
    parser = argparse.ArgumentParser(description="Manage GitLab issues and project metadata.")
    parser.add_argument("--project-id", required=True, help="GitLab Project ID")
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Create Issue
    issue_parser = subparsers.add_parser("create-issue", help="Create a new issue")
    issue_parser.add_argument("--title", required=True)
    issue_parser.add_argument("--description", required=True)
    issue_parser.add_argument("--labels", help="Comma-separated labels")
    issue_parser.add_argument("--weight", type=int)
    issue_parser.add_argument("--due-date", help="YYYY-MM-DD")
    issue_parser.add_argument("--milestone-id", type=int)

    # Update Issue
    update_parser = subparsers.add_parser("update-issue", help="Update an existing issue")
    update_parser.add_argument("--iid", required=True, type=int)
    update_parser.add_argument("--title")
    update_parser.add_argument("--description")
    update_parser.add_argument("--labels", help="Comma-separated labels")
    update_parser.add_argument("--weight", type=int)
    update_parser.add_argument("--due-date", help="YYYY-MM-DD")
    update_parser.add_argument("--milestone-id", type=int)

    # Create Label
    label_parser = subparsers.add_parser("create-label", help="Create a label")
    label_parser.add_argument("--name", required=True)
    label_parser.add_argument("--color", required=True, help="Hex color like #FF0000")
    label_parser.add_argument("--description")

    # Create Milestone
    milestone_parser = subparsers.add_parser("create-milestone", help="Create a milestone")
    milestone_parser.add_argument("--title", required=True)
    milestone_parser.add_argument("--description")
    milestone_parser.add_argument("--start-date", help="YYYY-MM-DD")
    milestone_parser.add_argument("--due-date", help="YYYY-MM-DD")

    # List Milestones
    subparsers.add_parser("list-milestones", help="List project milestones")

    # List Labels
    subparsers.add_parser("list-labels", help="List project labels")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        if args.command == "create-issue":
            labels = args.labels.split(",") if args.labels else []
            issue = gitlab_service.create_issue(
                args.project_id,
                args.title,
                args.description,
                labels=labels,
                weight=args.weight,
                due_date=args.due_date,
                milestone_id=args.milestone_id
            )
            print(f"SUCCESS: Created issue #{issue.iid} - {issue.web_url}")

        elif args.command == "update-issue":
            update_data = {}
            if args.title: update_data["title"] = args.title
            if args.description: update_data["description"] = args.description
            if args.labels: update_data["labels"] = args.labels.split(",")
            if args.weight is not None: update_data["weight"] = args.weight
            if args.due_date: update_data["due_date"] = args.due_date
            if args.milestone_id: update_data["milestone_id"] = args.milestone_id
            
            issue = gitlab_service.update_issue(args.project_id, args.iid, **update_data)
            print(f"SUCCESS: Updated issue #{issue.iid}")

        elif args.command == "create-label":
            label = gitlab_service.create_label(args.project_id, args.name, args.color, args.description)
            print(f"SUCCESS: Created label '{label.name}'")

        elif args.command == "create-milestone":
            m = gitlab_service.create_milestone(
                args.project_id, 
                args.title, 
                args.description, 
                args.start_date, 
                args.due_date
            )
            print(f"SUCCESS: Created milestone '{m.title}' (ID: {m.id})")

        elif args.command == "list-milestones":
            milestones = gitlab_service.list_milestones(args.project_id)
            for m in milestones:
                print(f"ID: {m.id} | IID: {m.iid} | Title: {m.title}")

        elif args.command == "list-labels":
            labels = gitlab_service.list_labels(args.project_id)
            for l in labels:
                print(f"Name: {l.name} | Color: {l.color}")

    except Exception as e:
        print(f"ERROR: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
