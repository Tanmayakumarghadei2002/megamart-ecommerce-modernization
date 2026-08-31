output "vpc_id" {
  description = "VPC ID"
  value       = aws_vpc.megamart_vpc.id
}

output "eks_cluster_name" {
  description = "EKS Cluster Name"
  value       = aws_eks_cluster.megamart_eks.name
}

output "eks_cluster_endpoint" {
  description = "EKS Cluster API Endpoint"
  value       = aws_eks_cluster.megamart_eks.endpoint
}

output "eks_oidc_provider_arn" {
  description = "IAM OIDC Provider ARN for IRSA"
  value       = aws_iam_openid_connect_provider.eks.arn
}

output "order_service_irsa_role_arn" {
  description = "IAM Role ARN to annotate Order Service Kubernetes ServiceAccount"
  value       = aws_iam_role.order_service_irsa.arn
}

output "cluster_autoscaler_irsa_role_arn" {
  description = "IAM Role ARN to annotate Cluster Autoscaler Kubernetes ServiceAccount"
  value       = aws_iam_role.cluster_autoscaler_irsa.arn
}

output "aws_load_balancer_controller_irsa_role_arn" {
  description = "IAM Role ARN for AWS Load Balancer Controller"
  value       = aws_iam_role.aws_lbc_irsa.arn
}

output "dynamodb_orders_table_name" {
  description = "Amazon DynamoDB Orders Table Name"
  value       = aws_dynamodb_table.orders.name
}

output "s3_order_receipts_bucket_name" {
  description = "Amazon S3 Order Receipts Bucket Name"
  value       = aws_s3_bucket.order_receipts.id
}
