#!/usr/bin/env python3
"""One-off cleanup: destroy old Secret Manager versions accumulated before
per-write pruning was added (see flyer-sync/ht_flyer_sync_job.py).

Secret Manager bills for replica storage of every version — including
disabled ones — so leftover versions from before pruning was in place keep
costing money until destroyed. This script destroys all but the most
recent enabled version of each secret listed in SECRETS below.

Usage:
    python3 scripts/cleanup_secret_versions.py --dry-run   # preview only
    python3 scripts/cleanup_secret_versions.py             # actually destroy

Requires: google-cloud-secret-manager (already in flyer-sync/requirements.txt
and api/requirements.txt), and ADC credentials with
roles/secretmanager.admin (or versionManager) on the target project.
"""

import argparse
import sys

from google.cloud import secretmanager

PROJECT_ID = "personal-494020"

# Secret IDs to clean up. Note: the service account key secret is actually
# named `recipe-sa-key` in GCP (api/deploy.sh), not `google-service-account-key`
# as older README revisions stated.
SECRETS = ["ht-oauth-token", "recipe-api-key", "recipe-sa-key"]

KEEP = 1  # keep only the latest enabled version of each secret


def cleanup_secret(sm: secretmanager.SecretManagerServiceClient, secret_id: str, dry_run: bool) -> None:
    parent = f"projects/{PROJECT_ID}/secrets/{secret_id}"

    try:
        versions = list(sm.list_secret_versions(request={"parent": parent}))
    except Exception as e:
        print(f"  [{secret_id}] Could not list versions: {e}")
        return

    enabled = [v for v in versions if v.state == secretmanager.SecretVersion.State.ENABLED]
    enabled.sort(key=lambda v: v.create_time, reverse=True)

    to_destroy = enabled[KEEP:]
    if not to_destroy:
        print(f"  [{secret_id}] Nothing to clean up ({len(enabled)} enabled version(s))")
        return

    print(f"  [{secret_id}] {len(enabled)} enabled version(s), destroying {len(to_destroy)}, keeping {KEEP} newest:")
    for v in to_destroy:
        version_num = v.name.rsplit("/", 1)[-1]
        if dry_run:
            print(f"    [dry-run] would destroy version {version_num} (created {v.create_time})")
        else:
            sm.destroy_secret_version(request={"name": v.name})
            print(f"    destroyed version {version_num} (created {v.create_time})")


def main() -> None:
    global PROJECT_ID

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--project", default=PROJECT_ID, help=f"GCP project ID (default: {PROJECT_ID})")
    parser.add_argument("--dry-run", action="store_true", help="Preview what would be destroyed without doing it")
    args = parser.parse_args()

    PROJECT_ID = args.project

    print(f"Project: {PROJECT_ID}")
    print(f"Secrets: {', '.join(SECRETS)}")
    print(f"Mode: {'DRY RUN (no changes)' if args.dry_run else 'LIVE — versions will be destroyed'}")
    print()

    if not args.dry_run:
        confirm = input("Type 'yes' to permanently destroy old secret versions: ")
        if confirm.strip().lower() != "yes":
            print("Aborted.")
            sys.exit(1)

    sm = secretmanager.SecretManagerServiceClient()
    for secret_id in SECRETS:
        cleanup_secret(sm, secret_id, args.dry_run)

    print("\nDone.")


if __name__ == "__main__":
    main()
