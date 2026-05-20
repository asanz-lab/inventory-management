<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="isOpen && backlogItem" class="modal-overlay" @click="close">
        <div class="modal-container" @click.stop>
          <div class="modal-header">
            <h3 class="modal-title">
              {{ mode === 'create' ? 'Create Purchase Order' : 'Purchase Order Details' }}
            </h3>
            <button class="close-button" @click="close" aria-label="Close">
              <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                <path d="M15 5L5 15M5 5L15 15" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
              </svg>
            </button>
          </div>

          <div class="modal-body">
            <!-- Backlog item summary (always shown) -->
            <div class="item-summary">
              <div class="summary-row">
                <div class="summary-field">
                  <div class="summary-label">Item</div>
                  <div class="summary-value">{{ backlogItem.item_name }}</div>
                </div>
                <div class="summary-field">
                  <div class="summary-label">SKU</div>
                  <div class="summary-value sku">{{ backlogItem.item_sku }}</div>
                </div>
              </div>
              <div class="summary-row">
                <div class="summary-field">
                  <div class="summary-label">Priority</div>
                  <div class="summary-value">
                    <span class="badge" :class="backlogItem.priority">{{ backlogItem.priority }}</span>
                  </div>
                </div>
                <div class="summary-field">
                  <div class="summary-label">Shortage</div>
                  <div class="summary-value shortage">{{ shortage }} units</div>
                </div>
              </div>
            </div>

            <div v-if="errorMessage" class="error-banner">{{ errorMessage }}</div>

            <!-- Create mode: form -->
            <form
              v-if="mode === 'create'"
              class="po-form"
              @submit.prevent="submit"
            >
              <div class="form-group">
                <label for="po-supplier-name" class="form-label">Supplier Name *</label>
                <input
                  id="po-supplier-name"
                  v-model="form.supplier_name"
                  type="text"
                  class="form-input"
                  required
                  :disabled="submitting"
                />
              </div>

              <div class="form-row">
                <div class="form-group">
                  <label for="po-quantity" class="form-label">Quantity *</label>
                  <input
                    id="po-quantity"
                    v-model.number="form.quantity"
                    type="number"
                    class="form-input"
                    min="1"
                    required
                    :disabled="submitting"
                  />
                </div>

                <div class="form-group">
                  <label for="po-unit-cost" class="form-label">Unit Cost *</label>
                  <input
                    id="po-unit-cost"
                    v-model.number="form.unit_cost"
                    type="number"
                    class="form-input"
                    min="0"
                    step="0.01"
                    required
                    :disabled="submitting"
                  />
                </div>
              </div>

              <div class="form-group">
                <label for="po-expected-delivery" class="form-label">Expected Delivery Date *</label>
                <input
                  id="po-expected-delivery"
                  v-model="form.expected_delivery_date"
                  type="date"
                  class="form-input"
                  required
                  :disabled="submitting"
                />
              </div>

              <div class="form-group">
                <label for="po-notes" class="form-label">Notes</label>
                <textarea
                  id="po-notes"
                  v-model="form.notes"
                  class="form-input form-textarea"
                  rows="3"
                  :disabled="submitting"
                ></textarea>
              </div>

              <div class="form-actions">
                <button
                  type="button"
                  class="btn-secondary"
                  :disabled="submitting"
                  @click="close"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  class="btn-primary"
                  :disabled="!canSubmit"
                >
                  {{ submitting ? 'Creating...' : 'Create Purchase Order' }}
                </button>
              </div>
            </form>

            <!-- View mode: read-only PO details -->
            <div v-else class="po-view">
              <div v-if="loading" class="po-loading">Loading purchase order...</div>
              <div v-else-if="purchaseOrder" class="info-grid">
                <div class="info-item">
                  <div class="info-label">PO ID</div>
                  <div class="info-value mono">{{ purchaseOrder.id }}</div>
                </div>

                <div class="info-item">
                  <div class="info-label">Supplier</div>
                  <div class="info-value">{{ purchaseOrder.supplier_name }}</div>
                </div>

                <div class="info-item">
                  <div class="info-label">Quantity</div>
                  <div class="info-value">{{ purchaseOrder.quantity }} units</div>
                </div>

                <div class="info-item">
                  <div class="info-label">Unit Cost</div>
                  <div class="info-value">{{ formatCurrency(purchaseOrder.unit_cost) }}</div>
                </div>

                <div class="info-item">
                  <div class="info-label">Total</div>
                  <div class="info-value total">{{ formatCurrency(totalCost) }}</div>
                </div>

                <div class="info-item">
                  <div class="info-label">Status</div>
                  <div class="info-value">
                    <span class="badge" :class="statusBadgeClass">{{ purchaseOrder.status }}</span>
                  </div>
                </div>

                <div class="info-item">
                  <div class="info-label">Expected Delivery</div>
                  <div class="info-value">{{ formatDate(purchaseOrder.expected_delivery_date) }}</div>
                </div>

                <div class="info-item">
                  <div class="info-label">Created Date</div>
                  <div class="info-value">{{ formatDate(purchaseOrder.created_date) }}</div>
                </div>

                <div v-if="purchaseOrder.notes" class="info-item full-row">
                  <div class="info-label">Notes</div>
                  <div class="info-value notes">{{ purchaseOrder.notes }}</div>
                </div>
              </div>
            </div>
          </div>

          <div v-if="mode === 'view'" class="modal-footer">
            <button class="btn-secondary" @click="close">Close</button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { ref, reactive, computed, watch, onBeforeUnmount } from 'vue'
import { api } from '../api'
import { formatCurrency } from '../utils/currency'

const props = defineProps({
  isOpen: {
    type: Boolean,
    default: false
  },
  backlogItem: {
    type: Object,
    default: null
  },
  mode: {
    type: String,
    default: 'create',
    validator: (value) => ['create', 'view'].includes(value)
  }
})

const emit = defineEmits(['close', 'po-created'])

// Compute default values from backlog item
const defaultQuantity = () => {
  if (!props.backlogItem) return 1
  // Shortage = needed - available; floor at 1 in case data already reconciled
  return Math.max(1, props.backlogItem.quantity_needed - props.backlogItem.quantity_available)
}

const defaultDeliveryDate = () => {
  // Default expected delivery = today + 7 days, formatted as YYYY-MM-DD for <input type="date">
  const date = new Date()
  date.setDate(date.getDate() + 7)
  return date.toISOString().split('T')[0]
}

const buildInitialForm = () => ({
  supplier_name: '',
  quantity: defaultQuantity(),
  unit_cost: 0,
  expected_delivery_date: defaultDeliveryDate(),
  notes: ''
})

const form = reactive(buildInitialForm())
const submitting = ref(false)
const loading = ref(false)
const errorMessage = ref('')
const purchaseOrder = ref(null)

const shortage = computed(() => {
  if (!props.backlogItem) return 0
  return props.backlogItem.quantity_needed - props.backlogItem.quantity_available
})

const totalCost = computed(() => {
  if (!purchaseOrder.value) return 0
  return purchaseOrder.value.quantity * purchaseOrder.value.unit_cost
})

const statusBadgeClass = computed(() => {
  if (!purchaseOrder.value) return 'info'
  // Map server PO statuses to existing badge color classes
  const status = (purchaseOrder.value.status || '').toLowerCase()
  if (status === 'delivered' || status === 'completed') return 'success'
  if (status === 'pending') return 'warning'
  if (status === 'cancelled') return 'danger'
  return 'info'
})

const canSubmit = computed(() => {
  if (submitting.value) return false
  if (!form.supplier_name.trim()) return false
  if (!form.quantity || form.quantity < 1) return false
  if (form.unit_cost === null || form.unit_cost === undefined || form.unit_cost < 0) return false
  if (!form.expected_delivery_date) return false
  return true
})

const resetState = () => {
  Object.assign(form, buildInitialForm())
  submitting.value = false
  loading.value = false
  errorMessage.value = ''
  purchaseOrder.value = null
}

const close = () => {
  emit('close')
}

const submit = async () => {
  if (!canSubmit.value || !props.backlogItem) return
  submitting.value = true
  errorMessage.value = ''
  try {
    const payload = {
      backlog_item_id: props.backlogItem.id,
      supplier_name: form.supplier_name.trim(),
      quantity: form.quantity,
      unit_cost: form.unit_cost,
      expected_delivery_date: form.expected_delivery_date,
      notes: form.notes?.trim() || ''
    }
    const created = await api.createPurchaseOrder(payload)
    // Emit full server response so parent can stash it on the backlog item
    emit('po-created', created)
    emit('close')
  } catch (err) {
    // Show inline error; don't bubble out of the modal
    const detail = err?.response?.data?.detail
    errorMessage.value = typeof detail === 'string'
      ? detail
      : 'Failed to create purchase order. Please try again.'
    console.error('Create PO failed:', err)
  } finally {
    submitting.value = false
  }
}

const loadPurchaseOrder = async () => {
  if (!props.backlogItem) return
  loading.value = true
  errorMessage.value = ''
  purchaseOrder.value = null
  try {
    purchaseOrder.value = await api.getPurchaseOrderByBacklogItem(props.backlogItem.id)
  } catch (err) {
    const detail = err?.response?.data?.detail
    errorMessage.value = typeof detail === 'string'
      ? detail
      : 'Failed to load purchase order.'
    console.error('Load PO failed:', err)
  } finally {
    loading.value = false
  }
}

const formatDate = (dateString) => {
  if (!dateString) return '-'
  const date = new Date(dateString)
  // Guard against invalid date strings before calling locale methods
  if (isNaN(date.getTime())) return dateString
  return date.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric'
  })
}

// Reset form / trigger fetch on open transitions. Closing also resets so reopening starts fresh.
watch(
  () => props.isOpen,
  (open) => {
    if (open) {
      resetState()
      if (props.mode === 'view') {
        loadPurchaseOrder()
      }
    } else {
      resetState()
    }
  }
)

// Escape key closes the modal. Use window listener so focus inside form inputs still triggers it.
const handleKeydown = (event) => {
  if (event.key === 'Escape' && props.isOpen) {
    close()
  }
}
window.addEventListener('keydown', handleKeydown)

onBeforeUnmount(() => {
  window.removeEventListener('keydown', handleKeydown)
})
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
  padding: 1rem;
}

.modal-container {
  background: white;
  border-radius: 12px;
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.15);
  max-width: 700px;
  width: 100%;
  max-height: 90vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1.5rem;
  border-bottom: 1px solid #e2e8f0;
}

.modal-title {
  font-size: 1.25rem;
  font-weight: 700;
  color: #0f172a;
  letter-spacing: -0.025em;
  margin: 0;
}

.close-button {
  background: none;
  border: none;
  color: #64748b;
  cursor: pointer;
  padding: 0.5rem;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  transition: all 0.15s ease;
}

.close-button:hover {
  background: #f1f5f9;
  color: #0f172a;
}

.modal-body {
  flex: 1;
  overflow-y: auto;
  padding: 2rem;
}

.item-summary {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 1.25rem;
  margin-bottom: 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.summary-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.5rem;
}

.summary-field {
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
  min-width: 0;
}

.summary-label {
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #64748b;
}

.summary-value {
  font-size: 0.938rem;
  color: #0f172a;
  font-weight: 600;
  word-break: break-word;
}

.summary-value.sku {
  font-family: 'Monaco', 'Courier New', monospace;
  color: #2563eb;
}

.summary-value.shortage {
  color: #dc2626;
}

.error-banner {
  background: #fef2f2;
  border: 1px solid #fecaca;
  color: #991b1b;
  border-radius: 8px;
  padding: 0.75rem 1rem;
  font-size: 0.875rem;
  margin-bottom: 1.25rem;
}

.po-form {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
}

.form-label {
  font-size: 0.813rem;
  font-weight: 600;
  color: #334155;
}

.form-input {
  padding: 0.625rem 0.75rem;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-size: 0.938rem;
  font-family: inherit;
  color: #0f172a;
  background: white;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.form-input:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.15);
}

.form-input:disabled {
  background: #f1f5f9;
  color: #94a3b8;
  cursor: not-allowed;
}

.form-textarea {
  resize: vertical;
  min-height: 72px;
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
  padding-top: 0.5rem;
  margin-top: 0.5rem;
  border-top: 1px solid #e2e8f0;
}

.btn-secondary {
  padding: 0.625rem 1.25rem;
  background: #f1f5f9;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-weight: 500;
  font-size: 0.875rem;
  color: #334155;
  cursor: pointer;
  transition: all 0.15s ease;
  font-family: inherit;
}

.btn-secondary:hover:not(:disabled) {
  background: #e2e8f0;
  border-color: #cbd5e1;
}

.btn-secondary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-primary {
  padding: 0.625rem 1.25rem;
  background: #3b82f6;
  border: 1px solid #3b82f6;
  border-radius: 8px;
  font-weight: 600;
  font-size: 0.875rem;
  color: white;
  cursor: pointer;
  transition: all 0.15s ease;
  font-family: inherit;
}

.btn-primary:hover:not(:disabled) {
  background: #2563eb;
  border-color: #2563eb;
}

.btn-primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.po-loading {
  padding: 2rem;
  text-align: center;
  color: #64748b;
  font-size: 0.938rem;
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1.25rem;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
}

.info-item.full-row {
  grid-column: 1 / -1;
}

.info-label {
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #64748b;
}

.info-value {
  font-size: 0.938rem;
  color: #0f172a;
  font-weight: 500;
}

.info-value.mono {
  font-family: 'Monaco', 'Courier New', monospace;
  color: #2563eb;
}

.info-value.total {
  font-size: 1.125rem;
  font-weight: 700;
  color: #0f172a;
}

.info-value.notes {
  white-space: pre-wrap;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 0.75rem;
  font-weight: 400;
  line-height: 1.5;
}

.modal-footer {
  padding: 1.5rem;
  border-top: 1px solid #e2e8f0;
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
}

/* Modal transition animations */
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.2s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-active .modal-container,
.modal-leave-active .modal-container {
  transition: transform 0.2s ease;
}

.modal-enter-from .modal-container,
.modal-leave-to .modal-container {
  transform: scale(0.95);
}
</style>
