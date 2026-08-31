#!/usr/bin/env bash
set -euo pipefail

TARGET_URL="${1:-http://localhost:8000}"

echo "============================================================"
echo "  MegaMart Flash-Sale Simulation & Autoscaling Test Runner"
echo "============================================================"
echo "Target Endpoint: ${TARGET_URL}"
echo "Starting load test..."

if command -v k6 &> /dev/null; then
    echo "[INFO] Running k6 Flash-Sale Load Test profile..."
    TARGET_URL="${TARGET_URL}" k6 run flash-sale-loadtest.js
elif command -v locust &> /dev/null; then
    echo "[INFO] Running Locust Headless Load Test profile..."
    locust -f locustfile.py --headless --users 300 --spawn-rate 20 -H "${TARGET_URL}" --run-time 5m
else
    echo "[WARN] Neither k6 nor locust was found on PATH."
    echo "You can install k6 (https://k6.io) or run: pip install locust && locust -f locustfile.py"
    echo "Alternatively, running quick cURL benchmark loop:"
    for i in {1..50}; do
        curl -s -o /dev/null -w "Request #$i - HTTP %{http_code} - Total Time: %{time_total}s\n" "${TARGET_URL}/api/catalog/products"
    done
fi

echo "============================================================"
echo "  Load Test Completed. Inspect Grafana Dashboard for HPA"
echo "  and Cluster Autoscaler scale-out metrics."
echo "============================================================"
