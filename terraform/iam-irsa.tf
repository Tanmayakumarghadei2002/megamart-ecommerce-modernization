# OIDC TLS Certificate and Provider for IAM Roles for Service Accounts (IRSA)
data "tls_certificate" "eks" {
  url = aws_eks_cluster.megamart_eks.identity[0].oidc[0].issuer
}

resource "aws_iam_openid_connect_provider" "eks" {
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = [data.tls_certificate.eks.certificates[0].sha1_fingerprint]
  url             = aws_eks_cluster.megamart_eks.identity[0].oidc[0].issuer

  tags = {
    Name = "megamart-eks-irsa-oidc"
  }
}

# ==============================================================================
# 1. ORDER SERVICE IRSA ROLE & POLICY (DynamoDB + S3 Access)
# ==============================================================================
resource "aws_iam_policy" "order_service_data_access" {
  name        = "megamart-order-service-data-policy"
  description = "Allows order-service to read/write to DynamoDB orders table and upload receipts to S3"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "DynamoDBOrderAccess"
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:GetItem",
          "dynamodb:UpdateItem",
          "dynamodb:Query",
          "dynamodb:Scan",
          "dynamodb:BatchWriteItem"
        ]
        Resource = [
          aws_dynamodb_table.orders.arn,
          "${aws_dynamodb_table.orders.arn}/index/*"
        ]
      },
      {
        Sid    = "S3ReceiptsAccess"
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:GetObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.order_receipts.arn,
          "${aws_s3_bucket.order_receipts.arn}/*"
        ]
      }
    ]
  })
}

resource "aws_iam_role" "order_service_irsa" {
  name = "megamart-order-service-irsa-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Federated = aws_iam_openid_connect_provider.eks.arn
        }
        Action = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringEquals = {
            "${replace(aws_iam_openid_connect_provider.eks.url, "https://", "")}:sub" = "system:serviceaccount:megamart-prod:order-service-sa",
            "${replace(aws_iam_openid_connect_provider.eks.url, "https://", "")}:aud" = "sts.amazonaws.com"
          }
        }
      }
    ]
  })

  tags = {
    Service = "order-service"
  }
}

resource "aws_iam_role_policy_attachment" "order_service_irsa_attach" {
  policy_arn = aws_iam_policy.order_service_data_access.arn
  role       = aws_iam_role.order_service_irsa.name
}

# ==============================================================================
# 2. CLUSTER AUTOSCALER IRSA ROLE & POLICY
# ==============================================================================
resource "aws_iam_policy" "cluster_autoscaler" {
  name        = "megamart-cluster-autoscaler-policy"
  description = "Permissions required by Cluster Autoscaler to scale EKS AutoScaling Groups"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "autoscaling:DescribeAutoScalingGroups",
          "autoscaling:DescribeAutoScalingInstances",
          "autoscaling:DescribeLaunchConfigurations",
          "autoscaling:DescribeScalingActivities",
          "autoscaling:DescribeTags",
          "ec2:DescribeInstanceTypes",
          "ec2:DescribeLaunchTemplateVersions"
        ]
        Resource = ["*"]
      },
      {
        Effect = "Allow"
        Action = [
          "autoscaling:SetDesiredCapacity",
          "autoscaling:TerminateInstanceInAutoScalingGroup"
        ]
        Resource = ["*"]
        Condition = {
          StringEquals = {
            "autoscaling:ResourceTag/k8s.io/cluster-autoscaler/${var.cluster_name}" = "owned"
          }
        }
      }
    ]
  })
}

resource "aws_iam_role" "cluster_autoscaler_irsa" {
  name = "megamart-cluster-autoscaler-irsa-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Federated = aws_iam_openid_connect_provider.eks.arn
        }
        Action = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringEquals = {
            "${replace(aws_iam_openid_connect_provider.eks.url, "https://", "")}:sub" = "system:serviceaccount:kube-system:cluster-autoscaler",
            "${replace(aws_iam_openid_connect_provider.eks.url, "https://", "")}:aud" = "sts.amazonaws.com"
          }
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "cluster_autoscaler_irsa_attach" {
  policy_arn = aws_iam_policy.cluster_autoscaler.arn
  role       = aws_iam_role.cluster_autoscaler_irsa.name
}

# ==============================================================================
# 3. AWS LOAD BALANCER CONTROLLER IRSA ROLE
# ==============================================================================
resource "aws_iam_role" "aws_lbc_irsa" {
  name = "megamart-aws-load-balancer-controller-irsa-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Federated = aws_iam_openid_connect_provider.eks.arn
        }
        Action = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringEquals = {
            "${replace(aws_iam_openid_connect_provider.eks.url, "https://", "")}:sub" = "system:serviceaccount:kube-system:aws-load-balancer-controller",
            "${replace(aws_iam_openid_connect_provider.eks.url, "https://", "")}:aud" = "sts.amazonaws.com"
          }
        }
      }
    ]
  })
}
