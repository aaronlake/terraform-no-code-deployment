# Terraform No-Code Deployment Script

This script is designed to be an example method for deploying a Terraform configuration using [No-Code](hashi.co/nocode). This is not intended to be used in production, but rather as a reference for how to leverage no-code in your own workflows.

## Prerequisites

Works with Python 3.6+, and as of this writing, No-Code only exists in Terraform Cloud. Terraform Enterprise support is baked in but no-code has not been released yet.

Install Python dependencies:

```bash
pip install -r requirements.txt
```

Export your Terraform Cloud API and Organization tokens:

```bash
export TFC_TOKEN=...
export TFC_ORG=...
```

## Usage

- Before running the script, you must have a no-code-enabled module published in a private registry on Terraform Cloud/Enterprise (soon). A simple code example can be found in `module/terraform-aws-s3-bucket`.
- Create a `.tfvars` file with the variables you want to set in the workspace. See `variables.tfvars.example` for an example.
- Create a `.tfvars` file with the sensitive variables you want to set in the workspace. See `secret.tfvars.example` for an example. (This is bad practice, but is included for demonstration purposes.)

```
./main.py --help
usage: Terraform Enterprise No-Code Deployment [-h] [-u URL] [-w WORKSPACE] [-p PREFIX] [-m MODULE] [-v VARIABLES]
                                               [-s SENSITIVE]

Assists with creating an ephemeral Workspace, attach a new VCS repository, and apply.

options:
  -h, --help            show this help message and exit
  -u URL, --url URL     Terraform Enterprise URL blank for Terraform Cloud (https://app.terraform.io/api/v2)
  -w WORKSPACE, --workspace WORKSPACE
                        Workspace name (required if not using prefix)
  -p PREFIX, --prefix PREFIX
                        Workspace prefix, will generate random UUID suffix (required if not using workspace)
  -m MODULE, --module MODULE
                        Terraform Enterprise Module ID (required). Example: /private/<org>/<module-
                        name>/<provider>/<version>
  -v VARIABLES, --variables VARIABLES
                        Path to .tfvars file containing variables to be set in the workspace
  -s SENSITIVE, --sensitive SENSITIVE
                        Path to .tfvars file containing sensitive variables to be set in the workspace
```

Example Run:

```
./main.py --prefix test --module "private/<ORG_NAME>/s3-bucket/aws/1.0.0" --variables ./variables.tfvars --sensitive secret.tfvars | jq
{
  "workspace": "ws-K5pdFamUZC6hr3wz",
  "run_id": "run-nE2o62QDchx5Fkpn",
  "url": "https://app.terraform.io/api/v2/app/<ORG_NAME>/workspaces/ws-K5pdFamUZC6hr3wz/runs/run-nE2o62QDchx5Fkpn"
}
```
