// Cloudflare Worker for INITIUM Shop Stripe Checkout
// Deploy at: https://workers.cloudflare.com
// Environment variable: STRIPE_SECRET_KEY (your Stripe secret key)

export default {
  async fetch(request, env) {
    // CORS headers
    const corsHeaders = {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type',
      'Content-Type': 'application/json',
    };

    if (request.method === 'OPTIONS') {
      return new Response(null, { headers: corsHeaders });
    }

    if (request.method !== 'POST') {
      return new Response(JSON.stringify({ error: 'Method not allowed' }), {
        status: 405, headers: corsHeaders,
      });
    }

    try {
      const { items, success_url, cancel_url } = await request.json();

      if (!items || !Array.isArray(items) || items.length === 0) {
        return new Response(JSON.stringify({ error: 'Cart is empty' }), {
          status: 400, headers: corsHeaders,
        });
      }

      // Build line items for Stripe Checkout
      const line_items = items.map(item => ({
        price_data: {
          currency: 'sgd',
          product_data: {
            name: item.name,
            description: item.desc || '',
          },
          unit_amount: Math.round(item.price * 100), // Convert to cents
        },
        quantity: item.qty,
      }));

      // Create Stripe Checkout Session
      const stripeRes = await fetch('https://api.stripe.com/v1/checkout/sessions', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${env.STRIPE_SECRET_KEY}`,
          'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: new URLSearchParams({
          'mode': 'payment',
          'success_url': success_url || 'https://initium.sg/intm-shop.html?status=success',
          'cancel_url': cancel_url || 'https://initium.sg/intm-shop.html?status=cancel',
          'shipping_address_collection[allowed_countries][]': 'SG',
          'automatic_tax[enabled]': 'false',
          ...line_items.flatMap((item, i) =>
            Object.entries(item.price_data).flatMap(([k, v]) => {
              if (typeof v === 'object') {
                return Object.entries(v).map(([sk, sv]) => [`line_items[${i}][price_data][${k}][${sk}]`, sv]);
              }
              return [[`line_items[${i}][price_data][${k}]`, v]];
            }).concat([[`line_items[${i}][quantity]`, item.quantity]])
          ).reduce((acc, [k, v]) => { acc[k] = v; return acc; }, {}),
        }),
      });

      const session = await stripeRes.json();

      if (session.error) {
        return new Response(JSON.stringify({ error: session.error.message }), {
          status: 400, headers: corsHeaders,
        });
      }

      return new Response(JSON.stringify({
        url: session.url,
        session_id: session.id,
      }), { headers: corsHeaders });

    } catch (err) {
      return new Response(JSON.stringify({ error: err.message }), {
        status: 500, headers: corsHeaders,
      });
    }
  },
};
