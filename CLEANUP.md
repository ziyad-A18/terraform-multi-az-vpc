# Cleanup Guide

This project provisions billable AWS resources. Use this guide to safely tear down the infrastructure when not actively working on it, and to bring it back up later without losing any code or configuration.

---

## Billable Resources in This Project

| Resource | Approximate Cost | Notes |
|---|---|---|
| 2× NAT Gateway | ~$0.045/hr each (~$64/month combined if left running) | Largest ongoing cost |
| RDS `db.t3.micro` (Multi-AZ) | Free Tier eligible (12 months), otherwise ~$12–15/month | |
| 2× Elastic IP (attached to NAT Gateways) | Free while attached and in use | Charged if left unattached |
| EC2 `t2.micro` × 2 (Auto Scaling Group) | Free Tier eligible, otherwise minimal | |
| Application Load Balancer | ~$0.0225/hr (~$16/month if left running) | |
| VPC, Subnets, Security Groups, IAM, Route Tables | Free | No charge regardless of usage |
| S3 (Terraform state) | Negligible (a few KB stored) | |
| DynamoDB (state locking) | Negligible (on-demand billing, minimal requests) | |
| Secrets Manager | ~$0.40/month per secret | |
| SSM Parameter Store (Standard/SecureString) | Free | |

**Bottom line:** leaving this running costs roughly **$80–100/month**. Destroy it whenever you're done for the day.

---

## Full Teardown

Run from the project directory:

```bash
terraform destroy
```

Review the plan carefully, then confirm with `yes`.

This removes every resource Terraform is tracking, including RDS, NAT Gateways, the ALB, EC2 instances, and the VPC itself.

**Note:** Since `recovery_window_in_days = 0` is set on the Secrets Manager secret, it will be deleted immediately (no 30-day recovery window) — recreating the infrastructure will generate a fresh secret and password automatically, no manual steps needed.

---

## Rebuilding After a Full Teardown

```bash
terraform init      # only needed if backend/provider config changed
terraform plan       # review what will be created
terraform apply      # confirm with 'yes'
```

**What regenerates automatically on `apply` (by design):**
- A new `random_password` for the database
- A new Secrets Manager secret version containing that password
- All SSM Parameters, pointing to the new RDS endpoint and secret ARN

**Nothing needs to be manually re-entered** — the Flask app reads all connection details dynamically from SSM/Secrets Manager at request time, not from hardcoded values.

**Expected timing:**
- Networking (VPC, subnets, NAT, IGW): ~1–2 minutes
- RDS (Multi-AZ PostgreSQL): **~10–11 minutes** — this is the longest step, be patient
- EC2 / Auto Scaling Group: ~2–3 minutes to launch and pass health checks
- ALB: ~1 minute to become active

**Total rebuild time: roughly 15 minutes.**

---

## Partial Cleanup (Cost Reduction Without Full Teardown)

If you want to keep the networking/security/IAM setup but stop the expensive pieces:

```bash
# Scale down compute to zero (stops billing for EC2, but keeps ASG/ALB config)
# Not recommended via manual console changes — prefer full destroy/apply cycles
# to avoid Terraform state drift.
```

**Recommendation:** For a learning project like this, a full `destroy` / `apply` cycle is simpler and safer than partial teardown, since it avoids any risk of state drift (see `README.md` troubleshooting log for what happens when Terraform's state and real infrastructure disagree).

---

## Verifying Everything Is Actually Gone

After `terraform destroy` completes, spot-check in the AWS Console:

- **EC2 → Instances** — should show none running (or "terminated")
- **VPC → NAT Gateways** — should show "Deleted" or be gone entirely
- **RDS → Databases** — should show none, or "deleting"
- **EC2 → Load Balancers** — should show none

If `terraform destroy` reports `Destroy complete!` with no errors, this is generally reliable — but a quick console check costs nothing and confirms there's no unexpected leftover billing.

---

## If `terraform destroy` Fails Partway Through

Run `terraform plan` afterward — it will show exactly what's left. Common causes:
- A resource was manually modified/deleted outside Terraform (state drift)
- An AWS-side dependency wasn't fully released yet (e.g., ENI still attached)

Re-running `terraform destroy` a second time usually resolves transient AWS-side timing issues.
