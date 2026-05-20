<template>
  <div class="restocking">
    <div class="page-header">
      <h2>Restocking</h2>
      <p>Set your available budget and place restock orders based on forecasted demand.</p>
    </div>

    <div v-if="loading" class="loading">Loading recommendations…</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else>

      <div class="card">
        <div class="card-header">
          <h3 class="card-title">Available Budget</h3>
          <div class="budget-readout">${{ budget.toLocaleString() }}</div>
        </div>
        <div class="slider-row">
          <span class="slider-end">$0</span>
          <input
            class="budget-slider"
            type="range"
            :min="0"
            :max="maxBudget"
            :step="sliderStep"
            v-model.number="budget"
          />
          <span class="slider-end">${{ maxBudget.toLocaleString() }}</span>
        </div>
        <div class="slider-hint">
          Drag to adjust. Maximum reflects the cost to fully cover every under-stocked SKU.
        </div>
      </div>

      <div class="stats-grid">
        <div class="stat-card info">
          <div class="stat-label">Items recommended</div>
          <div class="stat-value">{{ recommendations.length }}</div>
        </div>
        <div class="stat-card success">
          <div class="stat-label">Total cost</div>
          <div class="stat-value">${{ totalCost.toLocaleString() }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Remaining budget</div>
          <div class="stat-value">${{ remainingBudget.toLocaleString() }}</div>
        </div>
        <div class="stat-card warning">
          <div class="stat-label">Skipped (over budget)</div>
          <div class="stat-value">{{ skippedCount }}</div>
        </div>
      </div>

      <div class="card">
        <div class="card-header">
          <h3 class="card-title">Recommended Restock</h3>
          <button
            class="place-order-btn"
            :disabled="recommendations.length === 0 || placing"
            @click="placeOrder"
          >
            {{ placing ? 'Placing order…' : 'Place Order' }}
          </button>
        </div>

        <div v-if="orderSuccess" class="success-banner">
          Order {{ orderSuccess.order_number }} submitted —
          {{ orderSuccess.items.length }} line items,
          ${{ orderSuccess.total_value.toLocaleString() }} total,
          lead time {{ orderSuccess.lead_time_days }} days.
          See it in <router-link to="/orders">Orders</router-link>.
        </div>

        <div class="table-container">
          <table>
            <thead>
              <tr>
                <th>SKU</th>
                <th>Item</th>
                <th>Category</th>
                <th class="num">Current demand</th>
                <th class="num">Forecast</th>
                <th class="num">Gap</th>
                <th class="num">Unit cost</th>
                <th class="num">Order qty</th>
                <th class="num">Line cost</th>
              </tr>
            </thead>
            <tbody v-if="recommendations.length">
              <tr v-for="item in recommendations" :key="item.sku">
                <td><code>{{ item.sku }}</code></td>
                <td>{{ item.name }}</td>
                <td><span class="badge info">{{ item.category }}</span></td>
                <td class="num">{{ item.current_demand }}</td>
                <td class="num">{{ item.forecasted_demand }}</td>
                <td class="num">{{ item.gap }}</td>
                <td class="num">${{ item.unit_cost.toLocaleString() }}</td>
                <td class="num"><strong>{{ item.suggested_quantity }}</strong></td>
                <td class="num">${{ item.line_cost.toLocaleString() }}</td>
              </tr>
            </tbody>
            <tbody v-else>
              <tr>
                <td colspan="9" class="empty-row">
                  No items fit the current budget. Increase the budget to see recommendations.
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

    </div>
  </div>
</template>

<script>
import { ref, onMounted, watch, computed } from 'vue'
import { api } from '../api'

export default {
  name: 'Restocking',
  setup() {
    const loading = ref(true)
    const error = ref(null)
    const placing = ref(false)
    const orderSuccess = ref(null)

    const budget = ref(0)
    const maxBudget = ref(0)
    const recommendations = ref([])
    const totalCost = ref(0)
    const remainingBudget = ref(0)
    const skippedCount = ref(0)

    // Slider step adapts to magnitude so a $300K range doesn't require pixel-perfect
    // dragging while a $5K range still feels granular.
    const sliderStep = computed(() => {
      if (maxBudget.value >= 100000) return 1000
      if (maxBudget.value >= 10000) return 100
      return 10
    })

    const refresh = async () => {
      try {
        error.value = null
        const data = await api.getRestockRecommendations(budget.value)
        recommendations.value = data.recommendations
        totalCost.value = data.total_cost
        remainingBudget.value = data.remaining_budget
        skippedCount.value = data.skipped_count
      } catch (err) {
        error.value = 'Failed to load recommendations: ' + (err.message || err)
      }
    }

    // Debounce slider input so we don't fire a request on every pixel of drag.
    let debounceTimer = null
    watch(budget, () => {
      orderSuccess.value = null
      clearTimeout(debounceTimer)
      debounceTimer = setTimeout(refresh, 120)
    })

    const placeOrder = async () => {
      if (!recommendations.value.length) return
      try {
        placing.value = true
        orderSuccess.value = null
        const items = recommendations.value.map(r => ({
          sku: r.sku,
          quantity: r.suggested_quantity,
        }))
        const created = await api.placeRestockOrder(items)
        orderSuccess.value = created
        // Refresh recommendations: after restocking, those SKUs are no longer
        // gapped (the backend doesn't update inventory, but the user expects
        // visual feedback). We just clear the table for the placed items.
        recommendations.value = []
        totalCost.value = 0
        remainingBudget.value = budget.value
        skippedCount.value = 0
      } catch (err) {
        error.value = 'Failed to place order: ' + (err.response?.data?.detail || err.message)
      } finally {
        placing.value = false
      }
    }

    onMounted(async () => {
      try {
        // Query with a very large budget so the response reveals the natural
        // upper bound (total cost to fully restock everything). Use that as
        // the slider max and seed the initial budget at ~25% of it.
        const probe = await api.getRestockRecommendations(1e12)
        const ceiling = Math.max(1000, Math.ceil(probe.total_cost / 1000) * 1000)
        maxBudget.value = ceiling
        budget.value = Math.round(ceiling * 0.25 / 1000) * 1000
        await refresh()
      } catch (err) {
        error.value = 'Failed to initialize: ' + (err.message || err)
      } finally {
        loading.value = false
      }
    })

    return {
      loading, error, placing, orderSuccess,
      budget, maxBudget, sliderStep,
      recommendations, totalCost, remainingBudget, skippedCount,
      placeOrder,
    }
  }
}
</script>

<style scoped>
.budget-readout {
  font-size: 1.5rem;
  font-weight: 700;
  color: #0f172a;
  font-variant-numeric: tabular-nums;
}

.slider-row {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 0.5rem 0;
}

.slider-end {
  font-size: 0.813rem;
  color: #64748b;
  font-variant-numeric: tabular-nums;
  min-width: 70px;
}

.slider-end:last-child {
  text-align: right;
}

.budget-slider {
  flex: 1;
  -webkit-appearance: none;
  appearance: none;
  height: 6px;
  background: #e2e8f0;
  border-radius: 3px;
  outline: none;
  cursor: pointer;
}

.budget-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #2563eb;
  cursor: pointer;
  border: 3px solid #ffffff;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
  transition: transform 0.15s ease;
}

.budget-slider::-webkit-slider-thumb:hover {
  transform: scale(1.1);
}

.budget-slider::-moz-range-thumb {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #2563eb;
  cursor: pointer;
  border: 3px solid #ffffff;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
}

.slider-hint {
  font-size: 0.813rem;
  color: #64748b;
  margin-top: 0.5rem;
}

.place-order-btn {
  background: #2563eb;
  color: #ffffff;
  border: none;
  border-radius: 6px;
  padding: 0.5rem 1.25rem;
  font-size: 0.875rem;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s ease;
}

.place-order-btn:hover:not(:disabled) {
  background: #1d4ed8;
}

.place-order-btn:disabled {
  background: #cbd5e1;
  cursor: not-allowed;
}

.success-banner {
  background: #ecfdf5;
  border: 1px solid #a7f3d0;
  color: #065f46;
  padding: 0.75rem 1rem;
  border-radius: 8px;
  margin-bottom: 1rem;
  font-size: 0.875rem;
}

.success-banner a {
  color: #047857;
  font-weight: 600;
  text-decoration: underline;
}

.num {
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.empty-row {
  text-align: center;
  color: #64748b;
  padding: 2rem;
  font-style: italic;
}

code {
  font-family: 'SF Mono', Menlo, Consolas, monospace;
  font-size: 0.813rem;
  color: #1e293b;
  background: #f1f5f9;
  padding: 2px 6px;
  border-radius: 4px;
}
</style>
