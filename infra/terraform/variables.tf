variable "aws_region" {
  description = "AWS region to deploy into"
  type        = string
  default     = "eu-west-1"
}

variable "project_name" {
  description = "Short name used to prefix resources"
  type        = string
  default     = "transit-satisfaction"
}

variable "vpc_id" {
  description = "Existing VPC to deploy into (use the default VPC for a demo)"
  type        = string
}

variable "subnet_ids" {
  description = "Subnets (at least 2, in different AZs) for the EKS cluster"
  type        = list(string)
}
