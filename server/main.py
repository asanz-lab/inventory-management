from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from pydantic import BaseModel
from mock_data import inventory_items, orders, demand_forecasts, backlog_items, spending_summary, monthly_spending, category_spending, recent_transactions, purchase_orders

app = FastAPI(title="Factory Inventory Management System")

# Quarter mapping for date filtering
QUARTER_MAP = {
    'Q1-2025': ['2025-01', '2025-02', '2025-03'],
    'Q2-2025': ['2025-04', '2025-05', '2025-06'],
    'Q3-2025': ['2025-07', '2025-08', '2025-09'],
    'Q4-2025': ['2025-10', '2025-11', '2025-12']
}

# Supplier lead times per category. No lead-time field exists on inventory or
# demand fixtures, so the restocking flow derives it from the item's category
# at order-placement time. Defaults to 14 days when a category is unmapped.
LEAD_TIME_BY_CATEGORY = {
    'Circuit Boards':  14,
    'Sensors':          7,
    'Actuators':       10,
    'Controllers':     12,
    'Power Supplies':   9,
}
DEFAULT_LEAD_TIME_DAYS = 14

def filter_by_month(items: list, month: Optional[str]) -> list:
    """Filter items by month/quarter based on order_date field"""
    if not month or month == 'all':
        return items

    if month.startswith('Q'):
        # Handle quarters
        if month in QUARTER_MAP:
            months = QUARTER_MAP[month]
            return [item for item in items if any(m in item.get('order_date', '') for m in months)]
    else:
        # Direct month match
        return [item for item in items if month in item.get('order_date', '')]

    return items

def apply_filters(items: list, warehouse: Optional[str] = None, category: Optional[str] = None,
                 status: Optional[str] = None) -> list:
    """Apply common filters to a list of items"""
    filtered = items

    if warehouse and warehouse != 'all':
        filtered = [item for item in filtered if item.get('warehouse') == warehouse]

    if category and category != 'all':
        filtered = [item for item in filtered if item.get('category', '').lower() == category.lower()]

    if status and status != 'all':
        filtered = [item for item in filtered if item.get('status', '').lower() == status.lower()]

    return filtered

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Data models
class InventoryItem(BaseModel):
    id: str
    sku: str
    name: str
    category: str
    warehouse: str
    quantity_on_hand: int
    reorder_point: int
    unit_cost: float
    location: str
    last_updated: str

class Order(BaseModel):
    id: str
    order_number: str
    customer: str
    items: List[dict]
    status: str
    order_date: str
    expected_delivery: str
    total_value: float
    actual_delivery: Optional[str] = None
    warehouse: Optional[str] = None
    category: Optional[str] = None
    # Populated only for restocks placed through /api/restock/orders.
    lead_time_days: Optional[int] = None

class DemandForecast(BaseModel):
    id: str
    item_sku: str
    item_name: str
    current_demand: int
    forecasted_demand: int
    trend: str
    period: str
    # Added for the restocking flow. Optional so older fixtures still validate.
    category: Optional[str] = None
    unit_cost: Optional[float] = None

class BacklogItem(BaseModel):
    id: str
    order_id: str
    item_sku: str
    item_name: str
    quantity_needed: int
    quantity_available: int
    days_delayed: int
    priority: str
    has_purchase_order: Optional[bool] = False

class PurchaseOrder(BaseModel):
    id: str
    backlog_item_id: str
    supplier_name: str
    quantity: int
    unit_cost: float
    expected_delivery_date: str
    status: str
    created_date: str
    notes: Optional[str] = None

class CreatePurchaseOrderRequest(BaseModel):
    backlog_item_id: str
    supplier_name: str
    quantity: int
    unit_cost: float
    expected_delivery_date: str
    notes: Optional[str] = None

# API endpoints
@app.get("/")
def root():
    return {"message": "Factory Inventory Management System API", "version": "1.0.0"}

@app.get("/api/inventory", response_model=List[InventoryItem])
def get_inventory(
    warehouse: Optional[str] = None,
    category: Optional[str] = None
):
    """Get all inventory items with optional filtering"""
    return apply_filters(inventory_items, warehouse, category)

@app.get("/api/inventory/{item_id}", response_model=InventoryItem)
def get_inventory_item(item_id: str):
    """Get a specific inventory item"""
    item = next((item for item in inventory_items if item["id"] == item_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item

@app.get("/api/orders", response_model=List[Order])
def get_orders(
    warehouse: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    month: Optional[str] = None
):
    """Get all orders with optional filtering"""
    filtered_orders = apply_filters(orders, warehouse, category, status)
    filtered_orders = filter_by_month(filtered_orders, month)
    return filtered_orders

@app.get("/api/orders/{order_id}", response_model=Order)
def get_order(order_id: str):
    """Get a specific order"""
    order = next((order for order in orders if order["id"] == order_id), None)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order

@app.get("/api/demand", response_model=List[DemandForecast])
def get_demand_forecasts():
    """Get demand forecasts"""
    return demand_forecasts

@app.get("/api/backlog", response_model=List[BacklogItem])
def get_backlog():
    """Get backlog items with purchase order status"""
    # Add has_purchase_order flag to each backlog item
    result = []
    for item in backlog_items:
        item_dict = dict(item)
        # Check if this backlog item has a purchase order
        has_po = any(po["backlog_item_id"] == item["id"] for po in purchase_orders)
        item_dict["has_purchase_order"] = has_po
        result.append(item_dict)
    return result

@app.get("/api/dashboard/summary")
def get_dashboard_summary(
    warehouse: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    month: Optional[str] = None
):
    """Get summary statistics for dashboard with optional filtering"""
    # Filter inventory
    filtered_inventory = apply_filters(inventory_items, warehouse, category)

    # Filter orders
    filtered_orders = apply_filters(orders, warehouse, category, status)
    filtered_orders = filter_by_month(filtered_orders, month)

    total_inventory_value = sum(item["quantity_on_hand"] * item["unit_cost"] for item in filtered_inventory)
    low_stock_items = len([item for item in filtered_inventory if item["quantity_on_hand"] <= item["reorder_point"]])
    pending_orders = len([order for order in filtered_orders if order["status"] in ["Processing", "Backordered"]])
    total_backlog_items = len(backlog_items)

    return {
        "total_inventory_value": round(total_inventory_value, 2),
        "low_stock_items": low_stock_items,
        "pending_orders": pending_orders,
        "total_backlog_items": total_backlog_items,
        "total_orders_value": sum(order["total_value"] for order in filtered_orders)
    }

@app.get("/api/spending/summary")
def get_spending_summary():
    """Get spending summary statistics"""
    return spending_summary

@app.get("/api/spending/monthly")
def get_monthly_spending():
    """Get monthly spending breakdown"""
    return monthly_spending

@app.get("/api/spending/categories")
def get_category_spending():
    """Get spending by category"""
    return category_spending

@app.get("/api/spending/transactions")
def get_recent_transactions():
    """Get recent transactions"""
    return recent_transactions

@app.get("/api/reports/quarterly")
def get_quarterly_reports():
    """Get quarterly performance reports"""
    # Calculate quarterly statistics from orders
    quarters = {}

    for order in orders:
        order_date = order.get('order_date', '')
        # Determine quarter
        if '2025-01' in order_date or '2025-02' in order_date or '2025-03' in order_date:
            quarter = 'Q1-2025'
        elif '2025-04' in order_date or '2025-05' in order_date or '2025-06' in order_date:
            quarter = 'Q2-2025'
        elif '2025-07' in order_date or '2025-08' in order_date or '2025-09' in order_date:
            quarter = 'Q3-2025'
        elif '2025-10' in order_date or '2025-11' in order_date or '2025-12' in order_date:
            quarter = 'Q4-2025'
        else:
            continue

        if quarter not in quarters:
            quarters[quarter] = {
                'quarter': quarter,
                'total_orders': 0,
                'total_revenue': 0,
                'delivered_orders': 0,
                'avg_order_value': 0
            }

        quarters[quarter]['total_orders'] += 1
        quarters[quarter]['total_revenue'] += order.get('total_value', 0)
        if order.get('status') == 'Delivered':
            quarters[quarter]['delivered_orders'] += 1

    # Calculate averages and fulfillment rate
    result = []
    for q, data in quarters.items():
        if data['total_orders'] > 0:
            data['avg_order_value'] = round(data['total_revenue'] / data['total_orders'], 2)
            data['fulfillment_rate'] = round((data['delivered_orders'] / data['total_orders']) * 100, 1)
        result.append(data)

    # Sort by quarter
    result.sort(key=lambda x: x['quarter'])
    return result

@app.get("/api/reports/monthly-trends")
def get_monthly_trends():
    """Get month-over-month trends"""
    months = {}

    for order in orders:
        order_date = order.get('order_date', '')
        if not order_date:
            continue

        # Extract month (format: YYYY-MM-DD)
        month = order_date[:7]  # Gets YYYY-MM

        if month not in months:
            months[month] = {
                'month': month,
                'order_count': 0,
                'revenue': 0,
                'delivered_count': 0
            }

        months[month]['order_count'] += 1
        months[month]['revenue'] += order.get('total_value', 0)
        if order.get('status') == 'Delivered':
            months[month]['delivered_count'] += 1

    # Convert to list and sort
    result = list(months.values())
    result.sort(key=lambda x: x['month'])
    return result

# ---------------------------------------------------------------------------
# Restocking
# ---------------------------------------------------------------------------

class RestockOrderItem(BaseModel):
    sku: str
    quantity: int

class CreateRestockOrderRequest(BaseModel):
    items: List[RestockOrderItem]
    warehouse: Optional[str] = None


def _forecast_by_sku(sku: str):
    return next((f for f in demand_forecasts if f.get("item_sku") == sku), None)


def _compute_restock_candidates():
    """The forecast fixture is the source of truth for restocking — its SKUs
    intentionally don't overlap with inventory SKUs in this demo. A SKU is a
    candidate when forecasted demand exceeds current demand; the gap is what
    needs to be ordered to meet the projection."""
    candidates = []
    for forecast in demand_forecasts:
        gap = forecast.get("forecasted_demand", 0) - forecast.get("current_demand", 0)
        if gap <= 0:
            continue
        unit_cost = forecast.get("unit_cost", 0) or 0
        candidates.append({
            "sku": forecast["item_sku"],
            "name": forecast["item_name"],
            "category": forecast.get("category"),
            "current_demand": forecast.get("current_demand", 0),
            "forecasted_demand": forecast.get("forecasted_demand", 0),
            "gap": gap,
            "unit_cost": unit_cost,
            "line_cost": round(gap * unit_cost, 2),
            "trend": forecast.get("trend"),
        })
    return candidates


@app.get("/api/restock/recommend")
def recommend_restock(budget: float = 0):
    """Greedy restock recommendation: rank under-stocked items by demand gap
    (descending) and accept each one only if its full line cost still fits in
    the remaining budget. Items that don't fit are skipped rather than partially
    filled — partial fills don't actually cover the forecast for that SKU."""
    if budget < 0:
        raise HTTPException(status_code=400, detail="budget must be non-negative")

    candidates = _compute_restock_candidates()
    # Sort by raw quantity gap so the most under-stocked items are considered
    # first; ties broken by line_cost descending so a tied pair prefers the
    # higher-value (more business-critical) restock.
    candidates.sort(key=lambda c: (c["gap"], c["line_cost"]), reverse=True)

    selected = []
    remaining = budget
    for c in candidates:
        if c["line_cost"] <= remaining:
            selected.append({**c, "suggested_quantity": c["gap"]})
            remaining -= c["line_cost"]

    total_cost = round(sum(s["line_cost"] for s in selected), 2)
    return {
        "budget": budget,
        "total_cost": total_cost,
        "remaining_budget": round(remaining, 2),
        "recommendations": selected,
        "skipped_count": len(candidates) - len(selected),
    }


@app.post("/api/restock/orders", response_model=Order)
def create_restock_order(req: CreateRestockOrderRequest):
    """Place a restock order. Builds a new Order record with status='Submitted'
    and pushes it into the in-memory orders list so it shows up in the existing
    Orders endpoint. Lead time is the max across the categories represented in
    the order — the order isn't complete until the slowest line arrives."""
    if not req.items:
        raise HTTPException(status_code=400, detail="items must not be empty")

    from datetime import datetime, timedelta
    order_items = []
    total_value = 0.0
    lead_times = []

    for line in req.items:
        forecast = _forecast_by_sku(line.sku)
        if not forecast:
            raise HTTPException(status_code=404, detail=f"Unknown SKU: {line.sku}")
        if line.quantity <= 0:
            raise HTTPException(status_code=400, detail=f"quantity must be positive for {line.sku}")

        unit_cost = forecast.get("unit_cost", 0) or 0
        line_total = round(line.quantity * unit_cost, 2)
        total_value += line_total
        lead_times.append(LEAD_TIME_BY_CATEGORY.get(forecast.get("category"), DEFAULT_LEAD_TIME_DAYS))

        # Keep the same item shape Orders.vue already renders: it reads
        # item.name, item.quantity and item.unit_price. Restock uses unit_cost
        # as the price the company pays the supplier.
        order_items.append({
            "sku": forecast["item_sku"],
            "name": forecast["item_name"],
            "quantity": line.quantity,
            "unit_price": unit_cost,
            "line_total": line_total,
        })

    lead_time_days = max(lead_times) if lead_times else DEFAULT_LEAD_TIME_DAYS
    today = datetime.utcnow().date()
    expected = today + timedelta(days=lead_time_days)
    sequence = sum(1 for o in orders if o.get("status") == "Submitted") + 1

    new_order = {
        "id": f"RSO-{int(datetime.utcnow().timestamp())}",
        "order_number": f"RSO-{today.strftime('%Y%m%d')}-{sequence:03d}",
        "customer": "Internal Restock",
        "items": order_items,
        "status": "Submitted",
        "order_date": today.isoformat(),
        "expected_delivery": expected.isoformat(),
        "total_value": round(total_value, 2),
        "actual_delivery": None,
        "warehouse": req.warehouse,
        # Restock orders span multiple categories by design; leave blank so the
        # standard category filter doesn't accidentally hide them.
        "category": None,
        "lead_time_days": lead_time_days,
    }
    orders.append(new_order)
    return new_order


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
