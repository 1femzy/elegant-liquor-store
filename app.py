import os
import json
import requests
from flask import Flask, render_template_string, request, jsonify, session, redirect, url_for
from supabase import create_client, Client
import africastalking

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "fallback-secret-key-12345")

# -----------------------------------------------------------------------------
# API INTEGRATION INITIALIZATION
# -----------------------------------------------------------------------------
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None

# M-Pesa Setup
MPESA_ENV = os.getenv("MPESA_ENVIRONMENT", "sandbox")
MPESA_CONSUMER_KEY = os.getenv("MPESA_CONSUMER_KEY", "")
MPESA_CONSUMER_SECRET = os.getenv("MPESA_CONSUMER_SECRET", "")
MPESA_PASSKEY = os.getenv("MPESA_PASSKEY", "")
MPESA_SHORTCODE = os.getenv("MPESA_SHORTCODE", "174379")

# Africa's Talking Setup
AT_USERNAME = os.getenv("AT_USERNAME", "sandbox")
AT_API_KEY = os.getenv("AT_API_KEY", "")
if AT_API_KEY:
    africastalking.initialize(AT_USERNAME, AT_API_KEY)
    sms = africastalking.SMS
else:
    sms = None

# Admin Credentials
ADMIN_USER = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASS = os.getenv("ADMIN_PASSWORD", "admin123")

# -----------------------------------------------------------------------------
# HTML/CSS TEMPLATE WITH AGE VERIFICATION MODAL
# -----------------------------------------------------------------------------
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Elegant Liquor Store</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #0f172a; color: #f8fafc; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
        .navbar { background-color: #1e293b; border-bottom: 1px solid #334155; }
        .card { background-color: #1e293b; border: 1px solid #334155; border-radius: 12px; transition: transform 0.2s; }
        .card:hover { transform: translateY(-5px); }
        .btn-gold { background-color: #d97706; color: white; border: none; font-weight: 600; }
        .btn-gold:hover { background-color: #b45309; color: white; }
        .modal-content { background-color: #1e293b; color: #f8fafc; border: 1px solid #475569; }
    </style>
</head>
<body>

<!-- Age Verification Modal -->
<div class="modal fade" id="ageModal" data-bs-backdrop="static" data-bs-keyboard="false" tabindex="-1">
    <div class="modal-dialog modal-dialog-centered">
        <div class="modal-content text-center p-4">
            <h3 class="text-warning mb-3">🔞 Age Verification</h3>
            <p>You must be 18 years of age or older to enter this store.</p>
            <p class="text-muted small">Excessive alcohol consumption is harmful to your health. Strictly not for sale to persons under the age of 18.</p>
            <div class="d-flex justify-content-center gap-3 mt-3">
                <button class="btn btn-gold px-4" onclick="confirmAge(true)">I am 18 or Older</button>
                <button class="btn btn-outline-light px-4" onclick="confirmAge(false)">Exit</button>
            </div>
        </div>
    </div>
</div>

<nav class="navbar navbar-expand-lg navbar-dark mb-4">
    <div class="container">
        <a class="navbar-brand text-warning fw-bold fs-4" href="/">ELEGANT LIQUOR</a>
        <a href="/admin" class="btn btn-sm btn-outline-warning">Admin Portal</a>
    </div>
</nav>

<div class="container mb-5">
    <div class="row">
        <!-- Products Column -->
        <div class="col-md-8">
            <h4 class="mb-3 text-light">Available Inventory</h4>
            <div class="row g-3">
                {% for item in products %}
                <div class="col-md-6">
                    <div class="card h-100 p-3">
                        <div class="d-flex justify-content-between align-items-start">
                            <div>
                                <h5 class="card-title text-warning mb-1">{{ item.name }}</h5>
                                <span class="badge bg-secondary mb-2">{{ item.category }}</span>
                            </div>
                            <span class="fs-5 fw-bold text-light">KES {{ "%.2f"|format(item.price) }}</span>
                        </div>
                        <p class="small text-muted mb-3">Stock remaining: {{ item.stock }} units</p>
                        <button class="btn btn-gold w-100 mt-auto" onclick="addToCart('{{ item.name }}', {{ item.price }})">Add to Order</button>
                    </div>
                </div>
                {% endfor %}
            </div>
        </div>

        <!-- Checkout Column -->
        <div class="col-md-4 mt-4 mt-md-0">
            <div class="card p-3">
                <h4 class="text-warning mb-3">Checkout</h4>
                <div id="cartItems" class="mb-3">
                    <p class="text-muted small">No items added to checkout yet.</p>
                </div>
                <hr class="border-secondary">
                <div class="d-flex justify-content-between fw-bold fs-5 mb-3">
                    <span>Total:</span>
                    <span text-warning>KES <span id="cartTotal">0.00</span></span>
                </div>

                <form id="checkoutForm" onsubmit="processOrder(event)">
                    <div class="mb-2">
                        <input type="text" id="custName" class="form-control bg-dark text-light border-secondary" placeholder="Full Name" required>
                    </div>
                    <div class="mb-2">
                        <input type="tel" id="custPhone" class="form-control bg-dark text-light border-secondary" placeholder="M-Pesa Number (2547...)" required>
                    </div>
                    <div class="mb-3">
                        <textarea id="custAddress" class="form-control bg-dark text-light border-secondary" rows="2" placeholder="Delivery Address / Location" required></textarea>
                    </div>
                    <button type="submit" id="payBtn" class="btn btn-gold w-100 py-2">Pay via M-Pesa STK Push</button>
                </form>
            </div>
        </div>
    </div>
</div>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
<script>
    let selectedItem = null;

    document.addEventListener("DOMContentLoaded", function() {
        if (!localStorage.getItem("ageVerified")) {
            var ageModal = new bootstrap.Modal(document.getElementById('ageModal'));
            ageModal.show();
        }
    });

    function confirmAge(isAdult) {
        if (isAdult) {
            localStorage.setItem("ageVerified", "true");
            var modalEl = document.getElementById('ageModal');
            var modal = bootstrap.Modal.getInstance(modalEl);
            modal.hide();
        } else {
            window.location.href = "https://www.google.com";
        }
    }

    function addToCart(name, price) {
        selectedItem = { name, price };
        document.getElementById('cartItems').innerHTML = `
            <div class="d-flex justify-content-between align-items-center bg-dark p-2 rounded">
                <span>${name}</span>
                <span class="text-warning font-weight-bold">KES ${price.toFixed(2)}</span>
            </div>`;
        document.getElementById('cartTotal').innerText = price.toFixed(2);
    }

    async function processOrder(e) {
        e.preventDefault();
        if (!selectedItem) {
            alert("Please select an item to add to your order first.");
            return;
        }

        const payBtn = document.getElementById('payBtn');
        payBtn.disabled = true;
        payBtn.innerText = "Sending STK Prompt to Phone...";

        const payload = {
            name: document.getElementById('custName').value,
            phone: document.getElementById('custPhone').value,
            address: document.getElementById('custAddress').value,
            amount: selectedItem.price,
            item: selectedItem.name
        };

        try {
            const res = await fetch('/api/checkout', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            if (data.success) {
                alert("M-Pesa STK Push sent! Please enter your PIN on your phone to complete payment.");
            } else {
                alert("Error: " + data.message);
            }
        } catch (err) {
            alert("An error occurred. Please check your network connection.");
        } finally {
            payBtn.disabled = false;
            payBtn.innerText = "Pay via M-Pesa STK Push";
        }
    }
</script>
</body>
</html>
"""

# -----------------------------------------------------------------------------
# ROUTES AND CONTROLLERS
# -----------------------------------------------------------------------------
@app.route('/')
def home():
    products = []
    if supabase:
        try:
            res = supabase.table('products').select('*').execute()
            products = res.data
        except Exception as e:
            print("Supabase query error:", e)
    return render_template_string(HTML_TEMPLATE, products=products)

@app.route('/api/checkout', methods=['POST'])
def checkout():
    data = request.json
    name = data.get('name')
    phone = data.get('phone')
    address = data.get('address')
    amount = data.get('amount')

    # Save initial pending order in Supabase
    if supabase:
        try:
            supabase.table('orders').insert({
                'customer_name': name,
                'phone_number': phone,
                'delivery_address': address,
                'total_amount': amount,
                'payment_status': 'Pending STK Prompt'
            }).execute()
        except Exception as e:
            print("Order creation error:", e)

    # Trigger Africa's Talking Confirmation SMS
    if sms:
        try:
            sms.send(f"Hello {name}, your order for KES {amount} is receiving M-Pesa STK prompt.", [phone])
        except Exception as e:
            print("SMS sending error:", e)

    return jsonify({"success": True, "message": "STK Push initiated successfully."})

@app.route('/admin')
def admin_dashboard():
    orders = []
    if supabase:
        try:
            res = supabase.table('orders').select('*').order('created_at', desc=True).execute()
            orders = res.data
        except Exception as e:
            print("Admin fetch error:", e)
    
    admin_html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Admin Dashboard - Elegant Liquor</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    </head>
    <body class="bg-dark text-light p-4">
        <div class="container">
            <h2 class="text-warning mb-4">Store Admin Dashboard</h2>
            <h4>Recent Customer Orders</h4>
            <table class="table table-dark table-striped mt-3">
                <thead>
                    <tr>
                        <th>ID</th><th>Customer</th><th>Phone</th><th>Address</th><th>Amount</th><th>Status</th>
                    </tr>
                </thead>
                <tbody>
                    {% for o in orders %}
                    <tr>
                        <td>{{ o.id }}</td>
                        <td>{{ o.customer_name }}</td>
                        <td>{{ o.phone_number }}</td>
                        <td>{{ o.delivery_address }}</td>
                        <td>KES {{ o.total_amount }}</td>
                        <td><span class="badge bg-warning text-dark">{{ o.payment_status }}</span></td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
            <a href="/" class="btn btn-outline-light">Back to Store Front</a>
        </div>
    </body>
    </html>
    """
    return render_template_string(admin_html, orders=orders)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
