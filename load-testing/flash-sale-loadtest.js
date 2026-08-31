import http from 'k6/http';
import { check, sleep, group } from 'k6';
import { Counter, Rate, Trend } from 'k6/metrics';

// Custom Metrics
const successfulOrders = new Counter('successful_orders');
const failedOrders = new Counter('failed_orders');
const catalogLatency = new Trend('catalog_latency');
const checkoutLatency = new Trend('checkout_latency');
const errorRate = new Rate('error_rate');

// Test Configuration - Flash Sale Load Profile
export const options = {
  stages: [
    { duration: '30s', target: 20 },   // Warm-up baseline
    { duration: '1m',  target: 100 },  // Traffic ramp-up before flash sale
    { duration: '2m',  target: 400 },  // Flash Sale Surge (Triggers HPA pod scale-out)
    { duration: '3m',  target: 600 },  // Peak Concurrency (Triggers Cluster Autoscaler EC2 expansion)
    { duration: '1m',  target: 100 },  // Post-sale cooldown
    { duration: '30s', target: 0 },    // Scale down to zero
  ],
  thresholds: {
    'http_req_duration': ['p(95)<600'], // 95% of requests must complete within 600ms
    'error_rate': ['rate<0.02'],        // Error rate must stay under 2%
    'successful_orders': ['count>50'],  // Must successfully process checkouts
  },
};

const BASE_URL = __ENV.TARGET_URL || 'http://localhost:8000';

const PRODUCT_IDS = [
  'prod-101', 'prod-102', 'prod-103', 'prod-104', 'prod-105',
  'prod-106', 'prod-107', 'prod-108', 'prod-109', 'prod-110'
];

const SEARCH_TERMS = ['wireless', 'tv', 'jacket', 'espresso', 'cotton', 'yoga', '4k'];

export default function () {
  const userId = `usr-flash-${__VU}-${__ITER}`;
  
  // 1. Browse Catalog
  group('1. Browse Catalog', function () {
    const res = http.get(`${BASE_URL}/api/catalog/products?limit=10`);
    const success = check(res, {
      'catalog status is 200': (r) => r.status === 200,
      'products list returned': (r) => JSON.parse(r.body).total > 0,
    });
    errorRate.add(!success);
    catalogLatency.add(res.timings.duration);
  });

  sleep(0.5);

  // 2. Search Products
  group('2. Search Catalog', function () {
    const term = SEARCH_TERMS[Math.floor(Math.random() * SEARCH_TERMS.length)];
    const res = http.get(`${BASE_URL}/api/catalog/search?q=${term}`);
    const success = check(res, {
      'search status is 200': (r) => r.status === 200,
    });
    errorRate.add(!success);
  });

  sleep(0.5);

  // 3. View Product Details
  const selectedProdId = PRODUCT_IDS[Math.floor(Math.random() * PRODUCT_IDS.length)];
  group('3. View Product Details', function () {
    const res = http.get(`${BASE_URL}/api/catalog/products/${selectedProdId}`);
    const success = check(res, {
      'product detail status is 200': (r) => r.status === 200,
      'correct product returned': (r) => JSON.parse(r.body).id === selectedProdId,
    });
    errorRate.add(!success);
  });

  sleep(0.5);

  // 4. Flash-Sale Checkout (40% of users execute purchase)
  if (Math.random() < 0.40) {
    group('4. Flash-Sale Checkout', function () {
      const checkoutPayload = JSON.stringify({
        user_id: userId,
        customer_email: `${userId}@megamart-shopper.com`,
        items: [
          {
            product_id: selectedProdId,
            product_name: "MegaMart Featured Flash Deal",
            unit_price: 49.99,
            quantity: Math.floor(Math.random() * 2) + 1
          }
        ],
        shipping_address: {
          street: "777 Retail Express Blvd",
          city: "Austin",
          state: "TX",
          zip_code: "78701",
          country: "USA"
        },
        payment_method: "CREDIT_CARD"
      });

      const params = {
        headers: {
          'Content-Type': 'application/json',
        },
      };

      const res = http.post(`${BASE_URL}/api/orders/checkout`, checkoutPayload, params);
      const success = check(res, {
        'checkout status is 201': (r) => r.status === 201,
        'order confirmed': (r) => JSON.parse(r.body).status === 'CONFIRMED',
        'receipt url generated': (r) => JSON.parse(r.body).receipt_url !== null,
      });

      if (success) {
        successfulOrders.inc();
      } else {
        failedOrders.inc();
      }
      
      errorRate.add(!success);
      checkoutLatency.add(res.timings.duration);
    });
  }

  sleep(1);
}
