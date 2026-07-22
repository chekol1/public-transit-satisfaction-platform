output "ecr_repository_url" {
  value = aws_ecr_repository.api.repository_url
}

output "eks_cluster_name" {
  value = aws_eks_cluster.this.name
}

output "eks_cluster_endpoint" {
  value = aws_eks_cluster.this.endpoint
}
