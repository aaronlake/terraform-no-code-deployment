#!/usr/bin/env python3

import argparse
import os
import re
import sys
import uuid
import logging
import requests
import tfvars

logging.basicConfig(level=logging.INFO)

TFC_TOKEN = os.environ.get("TFC_TOKEN")
TFC_ORG = os.environ.get("TFC_ORG")
TFC_WORKSPACE = os.environ.get("TFC_WORKSPACE")
HEADERS = {
    "Authorization": f"Bearer {TFC_TOKEN}",
    "Content-Type": "application/vnd.api+json",
}


def cli() -> argparse.Namespace:
    """
    CLI Argument Parser

    :return: CLI arguments
    :rtype: argparse.Namespace
    """
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
        "-w",
        "--workspace",
        help="Workspace name (required if not using prefix)",
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
        required=True,
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

    args = parser.parse_args()

    if not args.module:
        logging.error("The '--module' argument is required.")
        sys.exit(1)

    if not args.workspace and not args.prefix:
        logging.error("One of the '--workspace' or '--prefix' arguments is required.")
        sys.exit(1)

    return args


def format_url(url: str) -> str:
    """
    Format URL for API calls

    :param url: Terraform Enterprise URL
    :type url: str
    :return: Formatted URL
    :rtype: str
    """
    if url is None:
        url = "https://app.terraform.io/api/v2"

    if not re.match(r"^http[s]?:\/\/.*?\/api\/v2", url):
        logging.error("Invalid URL: must start with http[s] and end with /api/v2")
        sys.exit(1)

    return url.rstrip("/")


def create_workspace(args: argparse.Namespace) -> str:
    """
    Create a new Terraform Enterprise Workspace

    https://developer.hashicorp.com/terraform/cloud-docs/api-docs/workspaces#create-a-workspace

    :param args: CLI arguments
    :type args: argparse.Namespace
    :return: Workspace ID
    :rtype: str
    """
    url = f"{format_url(args.url)}/organizations/{TFC_ORG}/workspaces"
    workspace = args.workspace

    if workspace is None:
        workspace = f"{args.prefix}-{str(uuid.uuid4())}"

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
        logging.error(
            "Create Workspace: failed to create new workspace: %s", response.json()
        )
        sys.exit(1)

    return response.json().get("data").get("id")


def variable_payload(
    key: str, value: str, sensitive: bool, description: str, workspace_id: str
) -> dict:
    """
    Create a variable payload for API calls

    https://developer.hashicorp.com/terraform/cloud-docs/api-docs/workspace-variables#sample-payload

    :param key: Variable name
    :type key: str
    :param value: Variable value
    :type value: str
    :param sensitive: Is the variable sensitive
    :type sensitive: bool
    :param description: Variable description
    :type description: str
    :param workspace_id: Workspace ID
    :type workspace_id: str
    :return: Variable payload
    :rtype: dict
    """
    return {
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


def put_variables(args: argparse.Namespace, workspace_id: str):
    """
    Insert variables to Terraform Workspace

    https://developer.hashicorp.com/terraform/cloud-docs/api-docs/workspace-variables#create-a-variable

    :param args: CLI arguments
    :type args: argparse.Namespace
    :param workspace_id: Workspace ID
    :type workspace_id: str
    """
    url = f"{format_url(args.url)}/workspaces/{workspace_id}/vars"

    for var_file, sensitive in {
        args.variables: False,
        args.sensitive: True,
    }.items():
        if not var_file:
            continue

        tfv = tfvars.LoadSecrets(var_file)

        for key, value in tfv.items():
            payload = variable_payload(key, value, sensitive, "", workspace_id)
            response = requests.post(url, headers=HEADERS, json=payload, timeout=30)

            if response.status_code != 201:
                logging.error(
                    "Put Variables: Failed to put variables: %s", response.json()
                )
                sys.exit(1)


def create_run(args: argparse.Namespace, workspace_id: str) -> str:
    """
    Apply a Terraform Enterprise Workspace

    https://developer.hashicorp.com/terraform/cloud-docs/api-docs/run#create-a-run

    :param args: CLI arguments
    :type args: argparse.Namespace
    :param workspace_id: Workspace ID
    :type workspace_id: str
    :return: Run ID
    :rtype: str
    """
    url = f"{format_url(args.url)}/runs"
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
        logging.error("Create Run: Failed to create run: %s", response.json())
        sys.exit(1)

    return response.json().get("data").get("id")


def main():
    """Main"""
    if not TFC_TOKEN:
        logging.error("TFC_TOKEN environment variable not set")
        sys.exit(1)

    if not TFC_ORG:
        logging.error("TFC_ORG environment variable not set")
        sys.exit(1)

    args = cli()
    workspace = create_workspace(args)
    put_variables(args, workspace)
    run_id = create_run(args, workspace)

    output = {
        "workspace": workspace,
        "run_id": run_id,
        "url": f"{format_url(args.url)}/app/{TFC_ORG}/workspaces/{workspace}/runs/{run_id}",
    }

    logging.info(output)


if __name__ == "__main__":
    main()
