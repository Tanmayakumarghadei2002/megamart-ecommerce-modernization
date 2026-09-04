#!/bin/bash
set -e

echo "========================================================"
echo "?? Starting MegaMart Microservices Automated Deployment"
echo "========================================================"

# Auto-detect AWS configuration
AWS_REGION=${AWS_REGION:-"us-east-1"}
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

echo "?? AWS Region:     ${AWS_REGION}"
echo "?? AWS Account ID: ${AWS_ACCOUNT_ID}"
echo "--------------------------------------------------------"

# 1. Login to Amazon ECR
echo "?? Logging in to Amazon ECR..."
aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com

# 2. Build & push catalog-service
echo "?? Building & Pushing catalog-service (v1.0.1)..."
cd apps/catalog-service
docker build -t ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/megamart/catalog-service:v1.0.1 .
docker push ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/megamart/catalog-service:v1.0.1
cd ../..

# 3. Build & push order-service
echo "?? Building & Pushing order-service (v1.0.1)..."
cd apps/order-service
docker build -t ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/megamart/order-service:v1.0.1 .
docker push ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/megamart/order-service:v1.0.1
cd ../..

# 4. Clean up any old pods to immediately free node resources
echo "?? Cleaning up previous pods..."
kubectl delete pods -n megamart-prod --all --wait=false 2>/dev/null || true

# 5. Apply GitOps manifests
echo "?? Applying production workloads..."
kubectl apply -k gitops/environments/production
kubectl apply -k gitops/base/ingress

# 6. Wait for rollout completion
echo "? Waiting for deployments to become ready..."
kubectl rollout status deployment/catalog-service -n megamart-prod --timeout=120s
kubectl rollout status deployment/order-service -n megamart-prod --timeout=120s

echo "========================================================"
echo "? All microservices are successfully running!"
echo "========================================================"

# 7. Check Ingress & Display Test Endpoints
kubectl get pods -n megamart-prod
echo ""
echo "?? Checking Application Load Balancer (ALB)..."
kubectl get ingress megamart-ingress -n megamart-prod

ALB_HOST=$(kubectl get ingress megamart-ingress -n megamart-prod -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null || echo "")

if [ -n "${ALB_HOST}" ]; then
  echo ""
  echo "?? Your Application is live at: http://${ALB_HOST}"
  echo "?? Try: curl http://${ALB_HOST}/api/catalog/products"
  echo "?? Try: curl http://${ALB_HOST}/api/orders/health"
else
  echo ""
  echo "? ALB is still provisioning. Wait ~2 minutes and run:"
  echo "   kubectl get ingress megamart-ingress -n megamart-prod"
fi
