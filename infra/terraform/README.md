# Infra (demo scope)

```
terraform init
terraform apply -var="vpc_id=<your-vpc>" -var='subnet_ids=["subnet-a","subnet-b"]'
```

Push the image once the ECR repo exists:

```
aws ecr get-login-password --region eu-west-1 | docker login --username AWS --password-stdin <account>.dkr.ecr.eu-west-1.amazonaws.com
docker build -t <ecr_repository_url>:latest .
docker push <ecr_repository_url>:latest
```

Then apply the manifests in `../k8s` (update the image reference first).

**Don't forget**: `terraform destroy` when you're done demoing -- the EKS
control plane bills ~$0.10/hr whether or not pods are running on it.
