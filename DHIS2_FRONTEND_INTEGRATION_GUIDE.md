# DHIS2 Frontend Integration Guide
*Complete Vue.js Implementation Strategy for Health Data Intelligence*

## 🎯 Overview

This guide provides a complete strategy for integrating DHIS2 data into your Vue.js frontend, following the hierarchical data model:

```
Data Element → Dataset → Organization Unit → Period → Data Value → Indicators
```

## 📋 Table of Contents

1. [Frontend Architecture](#frontend-architecture)
2. [API Integration Setup](#api-integration-setup)
3. [Pinia Store Implementation](#pinia-store-implementation)
4. [Component Implementation](#component-implementation)
5. [Data Visualization](#data-visualization)
6. [Advanced Features](#advanced-features)
7. [Testing Strategy](#testing-strategy)

---

## 🏗️ Frontend Architecture

### Project Structure
```
src/
├── services/
│   ├── dhis2Api.js          # API client
│   └── dataProcessor.js     # Data transformation utilities
├── stores/
│   ├── dhis2Store.js        # Main DHIS2 data store
│   ├── organizationStore.js # Organization units
│   ├── datasetStore.js      # Datasets and data elements
│   └── analyticsStore.js    # Data values and analytics
├── components/
│   ├── dhis2/
│   │   ├── DatasetSelector.vue
│   │   ├── OrganizationSelector.vue
│   │   ├── PeriodSelector.vue
│   │   ├── DataElementsTable.vue
│   │   └── DataVisualization.vue
│   └── common/
│       ├── LoadingSpinner.vue
│       └── ErrorAlert.vue
├── views/
│   ├── DHIS2Dashboard.vue
│   ├── DatasetExplorer.vue
│   └── AnalyticsView.vue
└── utils/
    ├── dateHelpers.js
    └── chartHelpers.js
```

---

## 🔌 API Integration Setup

### 1. Create API Service (`src/services/dhis2Api.js`)

```javascript
import axios from 'axios'

const API_BASE = 'http://localhost:8000/api/dhis2'

class DHIS2ApiService {
  constructor() {
    this.client = axios.create({
      baseURL: API_BASE,
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json'
      }
    })
  }

  // ===================
  // METADATA ENDPOINTS
  // ===================

  // Test connection
  async testConnection() {
    const response = await this.client.get('/test-connection')
    return response.data
  }

  // Datasets
  async getStoredDatasets() {
    const response = await this.client.get('/datasets')
    return response.data
  }

  async syncDatasets(connectionId = 1, limit = 50) {
    const response = await this.client.post(`/datasets/sync?connection_id=${connectionId}&limit=${limit}`)
    return response.data
  }

  async getDatasetDataElements(datasetId) {
    const response = await this.client.get(`/datasets/${datasetId}/data-elements`)
    return response.data
  }

  // Organization Units
  async syncOrganizationUnits(connectionId = 1, limit = 100) {
    const response = await this.client.post(`/sync/organization-units?connection_id=${connectionId}&limit=${limit}`)
    return response.data
  }

  // Periods
  async syncPeriods(startYear = 2023, endYear = 2025) {
    const response = await this.client.post(`/sync/periods?start_year=${startYear}&end_year=${endYear}`)
    return response.data
  }

  // Indicators
  async syncIndicators(connectionId = 1, limit = 50) {
    const response = await this.client.post(`/sync/indicators?connection_id=${connectionId}&limit=${limit}`)
    return response.data
  }

  // ===================
  // DATA ENDPOINTS
  // ===================

  // Data Values
  async getDatasetData(datasetId, periods = 'LAST_12_MONTHS', orgUnits = 'LEVEL-2') {
    const response = await this.client.get(`/datasets/${datasetId}/data?periods=${periods}&org_units=${orgUnits}`)
    return response.data
  }

  async syncDataValues(datasetId, periods = 'LAST_6_MONTHS', orgUnits = 'LEVEL-2', maxElements = 10) {
    const response = await this.client.post(`/sync/data-values?dataset_id=${datasetId}&periods=${periods}&org_units=${orgUnits}&max_elements=${maxElements}`)
    return response.data
  }

  // Discovery endpoints (for exploration)
  async discoverDatasets(limit = 10) {
    const response = await this.client.get(`/discover/datasets?limit=${limit}`)
    return response.data
  }

  async discoverDataElements(limit = 10, filterText = '') {
    const response = await this.client.get(`/discover/data-elements?limit=${limit}&filter_text=${filterText}`)
    return response.data
  }

  async discoverOrganizationUnits(level = 2, limit = 10) {
    const response = await this.client.get(`/discover/organisation-units?level=${level}&limit=${limit}`)
    return response.data
  }

  // ===================
  // ORCHESTRATION
  // ===================

  async syncFullMetadata(connectionId = 1) {
    const response = await this.client.post(`/sync/full-metadata?connection_id=${connectionId}`)
    return response.data
  }

  async getDiscoverySummary() {
    const response = await this.client.get('/discovery-summary')
    return response.data
  }
}

export default new DHIS2ApiService()
</script>
```

### 2. Data Processing Utilities (`src/services/dataProcessor.js`)

```javascript
export class DataProcessor {
  // Transform analytics data into chart-friendly format
  static transformAnalyticsData(analyticsResponse) {
    const { headers, rows, metadata } = analyticsResponse.data || {}

    if (!headers || !rows) return { labels: [], datasets: [] }

    // Find column indices
    const dxIdx = headers.findIndex(h => h.name === 'dx')
    const peIdx = headers.findIndex(h => h.name === 'pe')
    const ouIdx = headers.findIndex(h => h.name === 'ou')
    const valueIdx = headers.findIndex(h => h.name === 'value')

    // Group data by data element
    const groupedData = {}

    rows.forEach(row => {
      const dataElement = row[dxIdx]
      const period = row[peIdx]
      const orgUnit = row[ouIdx]
      const value = parseFloat(row[valueIdx]) || 0

      if (!groupedData[dataElement]) {
        groupedData[dataElement] = {
          name: metadata?.items?.[dataElement]?.name || dataElement,
          data: {}
        }
      }

      if (!groupedData[dataElement].data[period]) {
        groupedData[dataElement].data[period] = 0
      }

      groupedData[dataElement].data[period] += value
    })

    return this.formatForCharts(groupedData)
  }

  // Format data for Chart.js
  static formatForCharts(groupedData) {
    const allPeriods = new Set()
    Object.values(groupedData).forEach(element => {
      Object.keys(element.data).forEach(period => allPeriods.add(period))
    })

    const sortedPeriods = Array.from(allPeriods).sort()

    return {
      labels: sortedPeriods.map(p => this.formatPeriodLabel(p)),
      datasets: Object.entries(groupedData).map(([key, element]) => ({
        label: element.name,
        data: sortedPeriods.map(period => element.data[period] || 0),
        backgroundColor: this.generateColor(key),
        borderColor: this.generateColor(key, 0.8),
        tension: 0.1
      }))
    }
  }

  // Convert DHIS2 period format to readable labels
  static formatPeriodLabel(period) {
    if (period.length === 6) { // YYYYMM format
      const year = period.substring(0, 4)
      const month = period.substring(4, 6)
      const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                         'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
      return `${monthNames[parseInt(month) - 1]} ${year}`
    }
    return period
  }

  // Generate consistent colors for data elements
  static generateColor(seed, alpha = 0.6) {
    let hash = 0
    for (let i = 0; i < seed.length; i++) {
      hash = seed.charCodeAt(i) + ((hash << 5) - hash)
    }

    const hue = Math.abs(hash % 360)
    return `hsla(${hue}, 70%, 50%, ${alpha})`
  }

  // Aggregate data by organization unit
  static aggregateByOrgUnit(analyticsResponse) {
    const { headers, rows, metadata } = analyticsResponse.data || {}

    const ouIdx = headers.findIndex(h => h.name === 'ou')
    const valueIdx = headers.findIndex(h => h.name === 'value')

    const aggregated = {}

    rows.forEach(row => {
      const orgUnit = row[ouIdx]
      const value = parseFloat(row[valueIdx]) || 0

      if (!aggregated[orgUnit]) {
        aggregated[orgUnit] = {
          name: metadata?.items?.[orgUnit]?.name || orgUnit,
          total: 0,
          count: 0
        }
      }

      aggregated[orgUnit].total += value
      aggregated[orgUnit].count += 1
    })

    return Object.entries(aggregated).map(([id, data]) => ({
      id,
      name: data.name,
      total: data.total,
      average: data.count > 0 ? data.total / data.count : 0
    }))
  }
}
```

---

## 🗄️ Pinia Store Implementation

### 1. Main DHIS2 Store (`src/stores/dhis2Store.js`)

```javascript
import { defineStore } from 'pinia'
import dhis2Api from '@/services/dhis2Api'

export const useDHIS2Store = defineStore('dhis2', {
  state: () => ({
    // Connection status
    isConnected: false,
    connectionStatus: null,

    // Sync status
    isSyncing: false,
    syncProgress: {},
    lastSyncTime: null,

    // Datasets
    datasets: [],
    selectedDataset: null,
    dataElements: [],

    // Organization Units
    organizationUnits: [],
    selectedOrgUnits: [],

    // Periods
    periods: [],
    selectedPeriods: 'LAST_12_MONTHS',

    // Data Values
    analyticsData: null,
    dataValues: [],

    // Indicators
    indicators: [],

    // UI State
    loading: false,
    error: null
  }),

  getters: {
    // Dataset getters
    availableDatasets: (state) => state.datasets.filter(d => d.data_elements_count > 0),

    selectedDatasetElements: (state) => {
      return state.selectedDataset ? state.dataElements : []
    },

    // Organization getters
    organizationsByLevel: (state) => {
      const grouped = {}
      state.organizationUnits.forEach(org => {
        if (!grouped[org.level]) grouped[org.level] = []
        grouped[org.level].push(org)
      })
      return grouped
    },

    // Analytics getters
    hasAnalyticsData: (state) => state.analyticsData && state.analyticsData.data.rows.length > 0,

    totalDataPoints: (state) => state.analyticsData ? state.analyticsData.data.row_count : 0
  },

  actions: {
    // ===================
    // CONNECTION ACTIONS
    // ===================

    async testConnection() {
      try {
        this.loading = true
        const result = await dhis2Api.testConnection()
        this.isConnected = result.status === 'connected'
        this.connectionStatus = result
        return result
      } catch (error) {
        this.error = `Connection failed: ${error.message}`
        this.isConnected = false
        throw error
      } finally {
        this.loading = false
      }
    },

    // ===================
    // METADATA SYNC ACTIONS
    // ===================

    async syncAllMetadata() {
      try {
        this.isSyncing = true
        this.syncProgress = { step: 'Starting metadata sync...', progress: 0 }

        // Step 1: Organization Units
        this.syncProgress = { step: 'Syncing organization units...', progress: 20 }
        await dhis2Api.syncOrganizationUnits()

        // Step 2: Periods
        this.syncProgress = { step: 'Syncing periods...', progress: 40 }
        await dhis2Api.syncPeriods()

        // Step 3: Datasets
        this.syncProgress = { step: 'Syncing datasets...', progress: 60 }
        await dhis2Api.syncDatasets()

        // Step 4: Indicators
        this.syncProgress = { step: 'Syncing indicators...', progress: 80 }
        await dhis2Api.syncIndicators()

        this.syncProgress = { step: 'Metadata sync completed!', progress: 100 }
        this.lastSyncTime = new Date()

        // Load synced data
        await this.loadDatasets()

      } catch (error) {
        this.error = `Metadata sync failed: ${error.message}`
        throw error
      } finally {
        this.isSyncing = false
      }
    },

    // ===================
    // DATA LOADING ACTIONS
    // ===================

    async loadDatasets() {
      try {
        this.loading = true
        const response = await dhis2Api.getStoredDatasets()
        this.datasets = response.datasets || []
      } catch (error) {
        this.error = `Failed to load datasets: ${error.message}`
        throw error
      } finally {
        this.loading = false
      }
    },

    async selectDataset(datasetId) {
      try {
        this.loading = true
        this.selectedDataset = this.datasets.find(d => d.id === datasetId)

        if (this.selectedDataset) {
          const response = await dhis2Api.getDatasetDataElements(datasetId)
          this.dataElements = response.data_elements || []
        }
      } catch (error) {
        this.error = `Failed to load data elements: ${error.message}`
        throw error
      } finally {
        this.loading = false
      }
    },

    // ===================
    // ANALYTICS ACTIONS
    // ===================

    async fetchAnalyticsData(datasetId = null, periods = null, orgUnits = null) {
      try {
        this.loading = true

        const targetDatasetId = datasetId || this.selectedDataset?.id
        const targetPeriods = periods || this.selectedPeriods
        const targetOrgUnits = orgUnits || 'LEVEL-2'

        if (!targetDatasetId) {
          throw new Error('No dataset selected')
        }

        const response = await dhis2Api.getDatasetData(targetDatasetId, targetPeriods, targetOrgUnits)
        this.analyticsData = response

        return response
      } catch (error) {
        this.error = `Failed to fetch analytics data: ${error.message}`
        throw error
      } finally {
        this.loading = false
      }
    },

    async syncDataValues(datasetId = null, maxElements = 10) {
      try {
        this.loading = true

        const targetDatasetId = datasetId || this.selectedDataset?.id
        if (!targetDatasetId) {
          throw new Error('No dataset selected')
        }

        const response = await dhis2Api.syncDataValues(
          targetDatasetId,
          this.selectedPeriods,
          'LEVEL-2',
          maxElements
        )

        return response
      } catch (error) {
        this.error = `Failed to sync data values: ${error.message}`
        throw error
      } finally {
        this.loading = false
      }
    },

    // ===================
    // UTILITY ACTIONS
    // ===================

    clearError() {
      this.error = null
    },

    resetAnalytics() {
      this.analyticsData = null
      this.dataValues = []
    }
  }
})
```

---

## 🧩 Component Implementation

### 1. Dataset Selector (`src/components/dhis2/DatasetSelector.vue`)

```vue
<template>
  <div class="dataset-selector">
    <div class="flex justify-between items-center mb-4">
      <h3 class="text-lg font-semibold">Select Dataset</h3>
      <button
        @click="syncDatasets"
        :disabled="store.isSyncing"
        class="btn btn-primary btn-sm"
      >
        <span v-if="store.isSyncing" class="loading loading-spinner loading-xs"></span>
        {{ store.isSyncing ? 'Syncing...' : 'Sync Datasets' }}
      </button>
    </div>

    <!-- Datasets List -->
    <div class="grid gap-3">
      <div
        v-for="dataset in store.availableDatasets"
        :key="dataset.id"
        :class="[
          'card bg-base-100 border-2 cursor-pointer transition-all',
          selectedDataset?.id === dataset.id ? 'border-primary' : 'border-base-300 hover:border-primary/50'
        ]"
        @click="selectDataset(dataset)"
      >
        <div class="card-body p-4">
          <div class="flex justify-between items-start">
            <div>
              <h4 class="card-title text-sm">{{ dataset.name }}</h4>
              <p class="text-xs text-base-content/70">
                {{ dataset.period_type }} • {{ dataset.data_elements_count }} elements
              </p>
            </div>
            <div class="badge badge-outline">
              {{ dataset.period_type }}
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- No datasets message -->
    <div v-if="store.datasets.length === 0 && !store.loading" class="text-center py-8">
      <p class="text-base-content/70">No datasets available</p>
      <button @click="syncDatasets" class="btn btn-primary btn-sm mt-2">
        Sync Datasets
      </button>
    </div>

    <!-- Loading state -->
    <div v-if="store.loading" class="flex justify-center py-8">
      <span class="loading loading-spinner loading-lg"></span>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useDHIS2Store } from '@/stores/dhis2Store'

const store = useDHIS2Store()

// Props
const props = defineProps({
  modelValue: Object
})

// Emits
const emit = defineEmits(['update:modelValue', 'dataset-selected'])

// Computed
const selectedDataset = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value)
})

// Methods
const selectDataset = async (dataset) => {
  selectedDataset.value = dataset
  await store.selectDataset(dataset.id)
  emit('dataset-selected', dataset)
}

const syncDatasets = async () => {
  try {
    await store.syncAllMetadata()
  } catch (error) {
    console.error('Sync failed:', error)
  }
}

// Load datasets on mount
store.loadDatasets()
</script>
```

### 2. Data Elements Table (`src/components/dhis2/DataElementsTable.vue`)

```vue
<template>
  <div class="data-elements-table">
    <div class="flex justify-between items-center mb-4">
      <h3 class="text-lg font-semibold">Data Elements</h3>
      <div class="flex gap-2">
        <button
          @click="fetchAnalytics"
          :disabled="!canFetchAnalytics"
          class="btn btn-primary btn-sm"
        >
          <ChartBarIcon class="w-4 h-4" />
          View Analytics
        </button>
        <button
          @click="syncDataValues"
          :disabled="!canSyncData"
          class="btn btn-outline btn-sm"
        >
          Sync Data
        </button>
      </div>
    </div>

    <!-- Data Elements Table -->
    <div class="overflow-x-auto" v-if="store.dataElements.length > 0">
      <table class="table table-zebra w-full">
        <thead>
          <tr>
            <th>Name</th>
            <th>Type</th>
            <th>Domain</th>
            <th>Aggregation</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="element in store.dataElements" :key="element.id">
            <td>
              <div>
                <div class="font-medium">{{ element.name }}</div>
                <div class="text-sm text-base-content/70">{{ element.display_name }}</div>
              </div>
            </td>
            <td>
              <span class="badge badge-outline">{{ element.value_type }}</span>
            </td>
            <td>{{ element.domain_type }}</td>
            <td>{{ element.aggregation_type }}</td>
            <td>
              <button
                @click="viewElementDetails(element)"
                class="btn btn-ghost btn-xs"
              >
                Details
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- No data elements message -->
    <div v-else-if="store.selectedDataset && !store.loading" class="text-center py-8">
      <p class="text-base-content/70">No data elements found for this dataset</p>
    </div>

    <!-- Select dataset message -->
    <div v-else-if="!store.selectedDataset" class="text-center py-8">
      <p class="text-base-content/70">Select a dataset to view its data elements</p>
    </div>

    <!-- Loading state -->
    <div v-if="store.loading" class="flex justify-center py-8">
      <span class="loading loading-spinner loading-lg"></span>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { ChartBarIcon } from '@heroicons/vue/24/outline'
import { useDHIS2Store } from '@/stores/dhis2Store'

const store = useDHIS2Store()

// Emits
const emit = defineEmits(['analytics-requested', 'element-selected'])

// Computed
const canFetchAnalytics = computed(() => {
  return store.selectedDataset && store.dataElements.length > 0 && !store.loading
})

const canSyncData = computed(() => {
  return store.selectedDataset && !store.loading
})

// Methods
const fetchAnalytics = async () => {
  try {
    await store.fetchAnalyticsData()
    emit('analytics-requested', store.analyticsData)
  } catch (error) {
    console.error('Analytics fetch failed:', error)
  }
}

const syncDataValues = async () => {
  try {
    await store.syncDataValues(store.selectedDataset.id, 5) // Limit to 5 elements
  } catch (error) {
    console.error('Data sync failed:', error)
  }
}

const viewElementDetails = (element) => {
  emit('element-selected', element)
}
</script>
```

### 3. Data Visualization Component (`src/components/dhis2/DataVisualization.vue`)

```vue
<template>
  <div class="data-visualization">
    <div class="flex justify-between items-center mb-4">
      <h3 class="text-lg font-semibold">Analytics Visualization</h3>
      <div class="flex gap-2">
        <select v-model="chartType" class="select select-sm select-bordered">
          <option value="line">Line Chart</option>
          <option value="bar">Bar Chart</option>
          <option value="pie">Pie Chart</option>
        </select>
        <button @click="refreshData" class="btn btn-outline btn-sm">
          <ArrowPathIcon class="w-4 h-4" />
          Refresh
        </button>
      </div>
    </div>

    <!-- Chart Container -->
    <div class="bg-base-100 rounded-lg p-4" v-if="hasData">
      <canvas ref="chartCanvas" class="w-full h-64"></canvas>
    </div>

    <!-- Summary Stats -->
    <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mt-4" v-if="hasData">
      <div class="stat bg-base-100 rounded-lg">
        <div class="stat-title">Total Data Points</div>
        <div class="stat-value text-primary">{{ store.totalDataPoints }}</div>
      </div>
      <div class="stat bg-base-100 rounded-lg">
        <div class="stat-title">Data Elements</div>
        <div class="stat-value text-secondary">{{ uniqueDataElements }}</div>
      </div>
      <div class="stat bg-base-100 rounded-lg">
        <div class="stat-title">Time Range</div>
        <div class="stat-value text-accent text-sm">{{ timeRange }}</div>
      </div>
    </div>

    <!-- No data message -->
    <div v-else class="text-center py-12">
      <ChartBarIcon class="w-16 h-16 mx-auto text-base-content/30 mb-4" />
      <p class="text-base-content/70">No analytics data available</p>
      <p class="text-sm text-base-content/50">Select a dataset and fetch analytics data to view visualizations</p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, nextTick } from 'vue'
import { Chart, registerables } from 'chart.js'
import { ArrowPathIcon, ChartBarIcon } from '@heroicons/vue/24/outline'
import { useDHIS2Store } from '@/stores/dhis2Store'
import { DataProcessor } from '@/services/dataProcessor'

Chart.register(...registerables)

const store = useDHIS2Store()

// Refs
const chartCanvas = ref(null)
const chartInstance = ref(null)
const chartType = ref('line')

// Computed
const hasData = computed(() => store.hasAnalyticsData)

const uniqueDataElements = computed(() => {
  if (!store.analyticsData) return 0
  const { headers, rows } = store.analyticsData.data
  const dxIdx = headers.findIndex(h => h.name === 'dx')
  const uniqueElements = new Set(rows.map(row => row[dxIdx]))
  return uniqueElements.size
})

const timeRange = computed(() => {
  if (!store.analyticsData) return 'N/A'
  const { headers, rows } = store.analyticsData.data
  const peIdx = headers.findIndex(h => h.name === 'pe')
  const periods = rows.map(row => row[peIdx]).sort()

  if (periods.length === 0) return 'N/A'

  const start = DataProcessor.formatPeriodLabel(periods[0])
  const end = DataProcessor.formatPeriodLabel(periods[periods.length - 1])

  return periods.length === 1 ? start : `${start} - ${end}`
})

// Methods
const createChart = () => {
  if (!chartCanvas.value || !store.analyticsData) return

  // Destroy existing chart
  if (chartInstance.value) {
    chartInstance.value.destroy()
  }

  const chartData = DataProcessor.transformAnalyticsData(store.analyticsData)

  const config = {
    type: chartType.value,
    data: chartData,
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: 'top',
        },
        title: {
          display: true,
          text: `${store.selectedDataset?.name || 'Dataset'} Analytics`
        }
      },
      scales: chartType.value !== 'pie' ? {
        y: {
          beginAtZero: true
        }
      } : undefined
    }
  }

  chartInstance.value = new Chart(chartCanvas.value, config)
}

const refreshData = async () => {
  try {
    await store.fetchAnalyticsData()
  } catch (error) {
    console.error('Failed to refresh data:', error)
  }
}

// Watchers
watch([() => store.analyticsData, chartType], () => {
  nextTick(() => {
    createChart()
  })
})

// Lifecycle
onMounted(() => {
  if (hasData.value) {
    nextTick(() => {
      createChart()
    })
  }
})
</script>
```

---

## 📊 Main Dashboard View (`src/views/DHIS2Dashboard.vue`)

```vue
<template>
  <div class="dhis2-dashboard p-6">
    <!-- Header -->
    <div class="flex justify-between items-center mb-6">
      <div>
        <h1 class="text-3xl font-bold">DHIS2 Data Intelligence</h1>
        <p class="text-base-content/70">Explore and analyze health data from DHIS2</p>
      </div>

      <!-- Connection Status -->
      <div class="flex items-center gap-4">
        <div class="flex items-center gap-2">
          <div :class="[
            'w-3 h-3 rounded-full',
            store.isConnected ? 'bg-success' : 'bg-error'
          ]"></div>
          <span class="text-sm">
            {{ store.isConnected ? 'Connected' : 'Disconnected' }}
          </span>
        </div>
        <button @click="testConnection" class="btn btn-outline btn-sm">
          Test Connection
        </button>
      </div>
    </div>

    <!-- Error Alert -->
    <div v-if="store.error" class="alert alert-error mb-6">
      <XCircleIcon class="w-6 h-6" />
      <div>
        <h3 class="font-bold">Error</h3>
        <div class="text-xs">{{ store.error }}</div>
      </div>
      <button @click="store.clearError" class="btn btn-ghost btn-sm">
        <XMarkIcon class="w-4 h-4" />
      </button>
    </div>

    <!-- Sync Progress -->
    <div v-if="store.isSyncing" class="alert alert-info mb-6">
      <div class="flex items-center gap-4 w-full">
        <span class="loading loading-spinner"></span>
        <div class="flex-1">
          <div class="font-medium">{{ store.syncProgress.step }}</div>
          <progress
            class="progress progress-primary w-full"
            :value="store.syncProgress.progress"
            max="100"
          ></progress>
        </div>
      </div>
    </div>

    <!-- Main Content Grid -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <!-- Sidebar: Dataset Selection -->
      <div class="lg:col-span-1">
        <div class="card bg-base-100 shadow-sm">
          <div class="card-body">
            <DatasetSelector
              v-model="selectedDataset"
              @dataset-selected="onDatasetSelected"
            />
          </div>
        </div>
      </div>

      <!-- Main Content -->
      <div class="lg:col-span-2 space-y-6">
        <!-- Data Elements Section -->
        <div class="card bg-base-100 shadow-sm">
          <div class="card-body">
            <DataElementsTable
              @analytics-requested="onAnalyticsRequested"
              @element-selected="onElementSelected"
            />
          </div>
        </div>

        <!-- Visualization Section -->
        <div class="card bg-base-100 shadow-sm">
          <div class="card-body">
            <DataVisualization />
          </div>
        </div>
      </div>
    </div>

    <!-- Quick Actions -->
    <div class="fixed bottom-6 right-6" v-if="!store.isSyncing">
      <div class="dropdown dropdown-top dropdown-end">
        <div tabindex="0" role="button" class="btn btn-primary btn-circle btn-lg">
          <PlusIcon class="w-6 h-6" />
        </div>
        <ul tabindex="0" class="dropdown-content z-[1] menu p-2 shadow bg-base-100 rounded-box w-52 mb-2">
          <li><a @click="syncAllData">Sync All Metadata</a></li>
          <li><a @click="syncCurrentDataset">Sync Current Dataset</a></li>
          <li><a @click="exportData">Export Data</a></li>
        </ul>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import {
  XCircleIcon,
  XMarkIcon,
  PlusIcon
} from '@heroicons/vue/24/outline'
import { useDHIS2Store } from '@/stores/dhis2Store'
import DatasetSelector from '@/components/dhis2/DatasetSelector.vue'
import DataElementsTable from '@/components/dhis2/DataElementsTable.vue'
import DataVisualization from '@/components/dhis2/DataVisualization.vue'

const store = useDHIS2Store()

// State
const selectedDataset = ref(null)

// Methods
const testConnection = async () => {
  try {
    await store.testConnection()
  } catch (error) {
    console.error('Connection test failed:', error)
  }
}

const onDatasetSelected = (dataset) => {
  selectedDataset.value = dataset
  store.resetAnalytics()
}

const onAnalyticsRequested = (data) => {
  console.log('Analytics data received:', data)
}

const onElementSelected = (element) => {
  console.log('Data element selected:', element)
}

const syncAllData = async () => {
  try {
    await store.syncAllMetadata()
  } catch (error) {
    console.error('Full sync failed:', error)
  }
}

const syncCurrentDataset = async () => {
  if (!selectedDataset.value) {
    store.error = 'Please select a dataset first'
    return
  }

  try {
    await store.syncDataValues(selectedDataset.value.id)
  } catch (error) {
    console.error('Dataset sync failed:', error)
  }
}

const exportData = () => {
  if (!store.analyticsData) {
    store.error = 'No data to export'
    return
  }

  // Implement CSV export
  const csvData = store.analyticsData.data.rows.map(row => row.join(',')).join('\n')
  const headers = store.analyticsData.data.headers.map(h => h.name).join(',')
  const csv = headers + '\n' + csvData

  const blob = new Blob([csv], { type: 'text/csv' })
  const url = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `${selectedDataset.value?.name || 'data'}_export.csv`
  link.click()
}

// Lifecycle
onMounted(async () => {
  // Test connection on load
  try {
    await store.testConnection()
  } catch (error) {
    console.warn('Initial connection test failed:', error)
  }
})
</script>
```

---

## 🚀 Implementation Steps

### 1. Setup Phase
```bash
# Install required dependencies
npm install axios pinia chart.js @heroicons/vue

# Create directory structure
mkdir -p src/services src/stores src/components/dhis2 src/utils
```

### 2. Integration Phase
1. **Copy the service files** into your project
2. **Set up Pinia stores** for state management
3. **Create base components** starting with DatasetSelector
4. **Build the main dashboard** view
5. **Add error handling** and loading states

### 3. Testing Phase
```javascript
// Test the API connection
import dhis2Api from '@/services/dhis2Api'

// Test connection
await dhis2Api.testConnection()

// Sync metadata
await dhis2Api.syncDatasets()

// Fetch analytics
await dhis2Api.getDatasetData(1)
```

---

## 🎨 Styling Notes

This guide uses **DaisyUI** classes. To adapt for other frameworks:

- **Tailwind CSS**: Remove DaisyUI classes, use utility classes
- **Bootstrap**: Replace with Bootstrap component classes
- **Vuetify**: Use Vuetify components (`v-card`, `v-btn`, etc.)

---

## 🔧 Advanced Features

### 1. Real-time Data Updates
```javascript
// Add to store
async setupWebSocket() {
  const ws = new WebSocket('ws://localhost:8000/ws/dhis2')
  ws.onmessage = (event) => {
    const data = JSON.parse(event.data)
    if (data.type === 'data_updated') {
      this.fetchAnalyticsData()
    }
  }
}
```

### 2. Offline Support
```javascript
// Service worker for caching
self.addEventListener('fetch', (event) => {
  if (event.request.url.includes('/api/dhis2/datasets')) {
    event.respondWith(
      caches.match(event.request)
        .then(response => response || fetch(event.request))
    )
  }
})
```

### 3. Advanced Filters
```vue
<!-- Period Selector Component -->
<template>
  <div class="period-selector">
    <select v-model="selectedPeriodType">
      <option value="LAST_12_MONTHS">Last 12 Months</option>
      <option value="THIS_YEAR">This Year</option>
      <option value="LAST_YEAR">Last Year</option>
    </select>
  </div>
</template>
```

---

## ✅ Summary

This comprehensive guide provides:

1. **Complete API integration** with error handling
2. **Pinia stores** for centralized state management
3. **Reusable Vue components** for all DHIS2 data types
4. **Data visualization** with Chart.js
5. **Responsive dashboard** with DaisyUI styling
6. **Advanced features** for production use

Follow the implementation steps and you'll have a fully functional DHIS2 frontend integration! 🎉

---

*Generated for Cuplime Health Data Intelligence Platform*