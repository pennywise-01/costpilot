"""Publish the CloudFormation template to the public S3 bucket.

Usage:
    python scripts/publish_cfn_template.py [--profile PROFILE] [--region REGION]

Publishes `templates/aws-readonly-role.yaml` to:
    s3://costpilot-public-templates/aws-readonly-role.yaml

The file is made publicly readable so the CloudFormation Quick-Create
URL in IamPolicyModal.tsx works for any AWS customer.

Prerequisites:
    - AWS credentials with s3:PutObject on the target bucket.
    - The bucket must exist and allow public-read ACLs or have a
      bucket policy that grants GetObject to *.
"""

import argparse
import sys
from pathlib import Path

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "templates" / "aws-readonly-role.yaml"
BUCKET = "costpilot-public-templates"
KEY = "aws-readonly-role.yaml"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Publish the CostPilot CloudFormation template to S3."
    )
    parser.add_argument(
        "--profile",
        default=None,
        help="AWS CLI profile name (defaults to boto3 default resolution).",
    )
    parser.add_argument(
        "--region",
        default="us-east-1",
        help="AWS region for the S3 bucket (default: us-east-1).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate the template without uploading.",
    )
    args = parser.parse_args()

    if not TEMPLATE_PATH.exists():
        print(f"ERROR: Template not found at {TEMPLATE_PATH}", file=sys.stderr)
        sys.exit(1)

    template = TEMPLATE_PATH.read_text(encoding="utf-8")

    # Quick YAML parse to verify it's at least well-formed.
    try:
        import yaml
        yaml.safe_load(template)
    except Exception as e:
        print(f"ERROR: Template fails YAML parse: {e}", file=sys.stderr)
        sys.exit(1)

    if args.dry_run:
        print(f"Dry run: template at {TEMPLATE_PATH} is valid YAML ({len(template)} bytes).")
        print(f"Would upload to s3://{BUCKET}/{KEY}")
        return

    session_kwargs = {}
    if args.profile:
        session_kwargs["profile_name"] = args.profile
    if args.region:
        session_kwargs["region_name"] = args.region

    try:
        session = boto3.Session(**session_kwargs)
        s3 = session.client("s3")
        s3.put_object(
            Bucket=BUCKET,
            Key=KEY,
            Body=template,
            ContentType="application/x-yaml",
            ACL="public-read",
        )
        print(f"Published: https://{BUCKET}.s3.amazonaws.com/{KEY}")
        print(f"Published: https://s3.amazonaws.com/{BUCKET}/{KEY}")
        print(f"Published (alt): https://{BUCKET}.s3.{args.region}.amazonaws.com/{KEY}")
    except NoCredentialsError:
        print(
            "ERROR: No AWS credentials found. Set AWS_PROFILE, AWS_ACCESS_KEY_ID, "
            "or run `aws configure`.",
            file=sys.stderr,
        )
        sys.exit(1)
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        if code == "NoSuchBucket":
            print(
                f"ERROR: Bucket '{BUCKET}' does not exist. Create it first:\n"
                f"  aws s3 mb s3://{BUCKET} --region {args.region}\n"
                f"  aws s3api put-bucket-acl --bucket {BUCKET} --acl public-read\n"
                f"  # Or add a bucket policy granting s3:GetObject to *",
                file=sys.stderr,
            )
        elif code == "AccessDenied":
            print(
                f"ERROR: Access denied to bucket '{BUCKET}'. "
                "Check your IAM permissions for s3:PutObject.",
                file=sys.stderr,
            )
        else:
            print(f"ERROR: S3 upload failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
