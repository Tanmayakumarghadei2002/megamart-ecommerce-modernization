variable "aws_region" {
  description = "AWS region for provisioning resources"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Deployment environment (e.g. production, staging, dev)"
  type        = string
  default     = "production"
}

variable "cluster_name" {
  description = "Amazon EKS cluster name"
  type        = string
  default     = "megamart-eks-cluster"
}

variable "kubernetes_version" {
  description = "Kubernetes control plane version"
  type        = string
  default     = "1.30"
}

variable "vpc_cidr" {
  description = "CIDR block for the MegaMart VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "node_instance_types" {
  description = "EC2 instance types for EKS managed worker nodes (cost-performance optimized)"
  type        = list(string)
  default     = ["t3.medium", "m5.large"]
}

variable "node_desired_size" {
  description = "Desired number of worker nodes at baseline"
  type        = number
  default     = 3
}

variable "node_min_size" {
  description = "Minimum number of worker nodes (Multi-AZ baseline)"
  type        = number
  default     = 2
}

variable "node_max_size" {
  description = "Maximum number of worker nodes during flash sales"
  type        = number
  default     = 10
}
