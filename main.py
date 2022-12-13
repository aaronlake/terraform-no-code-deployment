#!/usr/bin/env python3

import argparse
import os
import re
import sys
import uuid
import requests
import tfvars

TFC_TOKEN = os.environ.get("TFC_TOKEN")
TFC_ORG = os.environ.get("TFC_ORG")
TFC_WORKSPACE = os.environ.get("TFC_WORKSPACE")
HEADERS = {
    "Authorization": f"Bearer {TFC_TOKEN}",
    "Content-Type": "application/vnd.api+json",
}


def cli():
    """CLI Argument Parser"""
    parser = argparse.ArgumentParser(
        prog="Terraform Enterprise No-Code Deployment",
        description="Assists with creating an ephemeral Workspace, "
        + "attach a new VCS repository, and apply.",
    )

    parser.add_argument(
        "-u",
        "--url",
        help="Terraform Enterprise URL blank for Terraform Cloud "
        + "(https://app.terraform.io/api/v2)",
        default="https://app.terraform.io/api/v2",
    )
    parser.add_argument(
        "-w", "--workspace", help="Workspace name (required if not using prefix)"
    )
    parser.add_argument(
        "-p",
        "--prefix",
        help="Workspace prefix, will generate random UUID suffix "
        + "(required if not using workspace)",
    )

    parser.add_argument(
        "-m",
        "--module",
        help="Terraform Enterprise Module ID (required). "
        + "Example: /private/<org>/<module-name>/<provider>/<version>",
    )

    parser.add_argument(
        "-v",
        "--variables",
        help="Path to .tfvars file containing variables "
        + "to be set in the workspace",
    )

    parser.add_argument(
        "-s",
        "--sensitive",
        help="Path to .tfvars file containing sensitive variables to "
        + "be set in the workspace",
    )

    return parser.parse_args()


def format_url(url):
    """Format URL for API calls"""
    if url is None:
        url = "https://app.terraform.io/api/v2"

    if not re.match(r"^http[s]?:\/\/.*?\/api\/v2", url):
        print("Invalid URL: must start with http[s] and end with /api/v2")
        sys.exit(1)

    return url.rstrip("/")


def create_workspace(args):
    """Create a new Terraform Enterprise Workspace"""
    url = format_url(args.url) + f"/organizations/{TFC_ORG}/workspaces"
    workspace = args.workspace

    if workspace is None:
        workspace = args.prefix + "-" + str(uuid.uuid4())

    data = {
        "data": {
            "type": "workspaces",
            "attributes": {
                "name": workspace,
                "source-module-id": args.module,
                "auto-apply": "true",
            },
        }
    }

    response = requests.post(url, headers=HEADERS, json=data, timeout=30)

    if response.status_code != 201:
        print(response.json())
        sys.exit(1)

    return response.json().get("data").get("id")


def variable_payload(key, value, sensitive, description, workspace_id):
    """Create a variable payload for API calls"""
    payload = {
        "data": {
            "type": "vars",
            "attributes": {
                "key": key,
                "value": value,
                "description": description,
                "category": "terraform",
                "hcl": "false",
                "sensitive": sensitive,
            },
            "relationships": {
                "workspace": {"data": {"id": workspace_id, "type": "workspaces"}}
            },
        }
    }

    return payload


def put_variables(args, workspace_id):
    """Create a new Terraform Enterprise Workspace"""
    url = format_url(args.url) + "/vars"

    tfv = tfvars.LoadSecrets(args.variables)

    for key, value in tfv.items():
        payload = variable_payload(key, value, "false", "", workspace_id)
        response = requests.post(url, headers=HEADERS, json=payload, timeout=30)

    if response.status_code != 201:
        print(response.json())
        sys.exit(1)

    if args.sensitive:
        tfv = tfvars.LoadSecrets(args.sensitive)

        for key, value in tfv.items():
            payload = variable_payload(key, value, "true", "", workspace_id)
            response = requests.post(url, headers=HEADERS, json=payload, timeout=30)

    if response.status_code != 201:
        print(response.json())
        sys.exit(1)


def create_run(args, workspace_id):
    """Apply a Terraform Enterprise Workspace"""
    url = format_url(args.url) + "/runs"
    payload = {
        "data": {
            "type": "runs",
            "attributes": {"auto-apply": "true"},
            "relationships": {
                "workspace": {"data": {"id": workspace_id, "type": "workspaces"}}
            },
        }
    }

    response = requests.post(url, headers=HEADERS, json=payload, timeout=30)

    if response.status_code != 201:
        print(response.json())
        sys.exit(1)

    return response.json().get("data").get("id")


def main():
    """Main"""
    if not TFC_TOKEN:
        print("TFC_TOKEN environment variable not set")
        sys.exit(1)

    if not TFC_ORG:
        print("TFC_ORG environment variable not set")
        sys.exit(1)

    args = cli()
    workspace = create_workspace(args)
    put_variables(args, workspace)
    print(workspace)
    run_id = create_run(args, workspace)

    output = {
        "workspace": workspace,
        "run_id": run_id,
        "url": f"{format_url(args.url)}/app/{TFC_ORG}/workspaces/{workspace}/runs/{run_id}",
    }

    print(output)


if __name__ == "__main__":
    main()
