# Multi-AZ AWS Infrastructure with Terraform

A fully automated, highly available AWS infrastructure built entirely with **Terraform** (Infrastructure as Code), running a real Flask application connected end-to-end to a PostgreSQL database — verified live from the public internet.

This project was built as a hands-on complement to learn Terraform , applying every core of terraform concept (state management, workspaces, modules, variables, provisioning, security) to a real, working system rather than isolated exercises.

---

## Architecture

```
Internet
   │
   ▼
Application Load Balancer (Public Subnets, 2 AZs)
   │
   ▼
Auto Scaling Group — EC2 (Flask App, Private Subnets, 2 AZs)
   │
   ├──► SSM Parameter Store (DB connection config, SecureString)
   ├──► Secrets Manager (DB credentials)
   │
   ▼
RDS PostgreSQL (Multi-AZ, Private Subnets)
```

**Live verified endpoints (via ALB DNS):**
- `GET /` → project info
- `GET /health` → health check (used by ALB target group)
- `GET /db-check` → live PostgreSQL connection test

---

## What This Project Demonstrates

- **Networking:** Custom VPC, 6 subnets (public / private-app / private-db) across 2 Availability Zones, Internet Gateway, 2 NAT Gateways, route tables per tier
- **Security:** Three-tier Security Group chain (Internet → ALB → EC2 → RDS) following least-privilege access
- **IAM:** Custom role and policy scoped to only the specific SSM parameters and Secrets Manager secret the app needs, plus `AmazonSSMManagedInstanceCore` for remote management
- **Secrets Management:** Auto-generated database password (`random_password`), stored in Secrets Manager, referenced dynamically via SSM `SecureString` parameters — no credentials ever hardcoded
- **Compute:** Launch Template + Auto Scaling Group (min 2 / max 4), health-checked by the ALB
- **Database:** RDS PostgreSQL with Multi-AZ failover
- **Remote State:** S3 backend with DynamoDB state locking, enabling safe multi-machine / multi-person workflows
- **Load Balancing:** Public-facing ALB routing to private EC2 instances

---

## Tech Stack

| Layer | Tool |
|---|---|
| Infrastructure as Code | Terraform (`~> 1.12`), AWS Provider `~> 6.0` |
| Compute | Amazon Linux 2023, Flask (Python) |
| Database | Amazon RDS for PostgreSQL 16 |
| Secrets | AWS Secrets Manager, SSM Parameter Store |
| State Backend | Amazon S3 + DynamoDB (locking) |

---

## Project Structure

```
.
├── main.tf          # All resources: networking, security, IAM, RDS, compute, ALB
├── variables.tf     # Input variable definitions (subnet CIDRs, etc.)
├── providers.tf     # Terraform + provider version constraints
├── backend.tf       # S3 remote state + DynamoDB locking configuration
├── outputs.tf       # Output values (ALB DNS name, etc.)
├── app.py           # Flask application deployed to EC2 via user_data
└── README.md
```

---

## Troubleshooting Log

Real issues hit while building this — kept as a record of the debugging process, not a curated "everything worked perfectly" writeup.

### 1. RDS rejected the auto-generated password

**Error:** `InvalidParameterValue: The parameter MasterUserPassword is not a valid password. Only printable ASCII characters besides '/', '@', '"', ' ' may be used.`

**Cause:** `random_password` with `special = true` can generate any special character by default, including ones RDS explicitly disallows.

**Fix:** Restricted the character set:
```hcl
resource "random_password" "db_password" {
  length           = 16
  special          = true
  override_special = "!#$%^&*()-_=+[]{}<>:?"
}
```

---

### 2. `cloud-init` hung indefinitely — SSM never came online

**Symptom:** Boot log stopped at `Press CTRL+C to quit`. Instance never registered with SSM.

**Cause:** Flask was launched as a foreground process in `user_data`:
```bash
python3 /home/ec2-user/app.py
```
Since it never returns, `cloud-init` could never finish its boot sequence.

**Fix:** Backgrounded it and redirected output to a log file:
```bash
nohup python3 /home/ec2-user/app.py > /var/log/app.log 2>&1 &
```

---

### 3. SSM Agent stayed "Offline" despite correct IAM, networking, and security groups

Checked and confirmed all correct: NAT Gateway state, route tables, `AmazonSSMManagedInstanceCore` attachment, security group egress rules, NACLs, VPC DNS settings — all passed.

**Cause:** The AMI filter was too broad:
```hcl
values = ["al2023-ami-*-x86_64"]
```
It matched `al2023-ami-minimal-...` — the **Minimal** variant of Amazon Linux 2023, which does not ship with SSM Agent pre-installed.

**Fix:** Anchored the filter to exclude the minimal image:
```hcl
values = ["al2023-ami-2023*-x86_64"]
```

**Takeaway:** Always verify the actual resolved AMI name from a `data` source before assuming it's the "standard" image.

---

### 4. Secrets Manager `AccessDeniedException` — but the "resource" in the error wasn't a real ARN

**Error snippet:** `...not authorized to perform: secretsmanager:GetSecretValue on resource: AQICAHhwjbtIkEYIhilPQZthv8dOCWudLS4Y...`

**Cause:** That string is KMS ciphertext, not an ARN. The app fetched the secret's ARN from an SSM `SecureString` parameter without requesting decryption:
```python
ssm.get_parameter(Name=name)
```
AWS returns SecureString values encrypted by default unless told otherwise.

**Fix:**
```python
ssm.get_parameter(Name=name, WithDecryption=True)
```

---

### 5. Recreating a Secrets Manager secret after `destroy` failed

**Error:** `You can't create this secret because a secret with this name is already scheduled for deletion.`

**Cause:** Secrets Manager holds deleted secrets in a recovery window (30 days by default) before freeing the name.

**Fix:** For a dev/learning environment, force immediate deletion:
```hcl
recovery_window_in_days = 0
```

---

### 6. New IAM permissions didn't fix already-running instances

**Cause:** SSM Agent registers once at boot. Attaching a policy afterward doesn't make a running instance retry registration automatically.

**Fix:** Triggered an **Instance Refresh** on the Auto Scaling Group so new instances launch with the correct permissions from the start.

---

## Key Lessons

1. Broad wildcards in `data` source filters can silently match the wrong resource variant — always verify the resolved value.
2. Any long-running process in `user_data` must be backgrounded (`nohup ... &`), or it blocks the entire boot sequence.
3. `SecureString` parameters require explicit `WithDecryption=True` — decryption is never automatic.
4. IAM role and Launch Template changes apply going forward only; existing instances need a refresh to pick them up.
5. Terraform `destroy` on some AWS resources (like Secrets Manager) doesn't mean immediate, final deletion — plan around retention windows.

---

## Cost Notes

This infrastructure includes billable resources when running:
- 2× NAT Gateways (~$0.045/hr each)
- RDS `db.t3.micro` Multi-AZ (Free Tier eligible for 12 months, otherwise ~$12–15/month)

Run `terraform destroy` when not actively working with the infrastructure.

---

## Certification Context

Built alongside preparation for **HashiCorp Certified: Terraform Associate**, applying exam topics — state locking, `for_each`, data sources, variable validation, remote backends, module structure — directly to a real multi-tier AWS deployment rather than isolated practice snippets.
