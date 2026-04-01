<template>
  <div class="scry-container">
    <div class="scry-header">
      <h1>🔮 Scry — Semantic Search</h1>
    </div>

    <!-- Search Input -->
    <div class="search-input">
      <input
        v-model="searchQuery"
        type="text"
        placeholder='Suche: z.B. "Beule am Rahmen"'
        @keyup.enter="performSearch"
        class="search-field"
      />
      <button @click="performSearch" class="search-btn">🔍</button>
    </div>

    <!-- Filters -->
    <div class="filters">
      <div class="filter-group">
        <label>Anzahl:</label>
        <select v-model="resultCount">
          <option>5</option>
          <option>10</option>
          <option>20</option>
          <option>50</option>
        </select>
      </div>

      <div class="filter-group">
        <label>Jahr:</label>
        <select v-model="yearFilter">
          <option value="">Alle</option>
          <option v-for="y in years" :key="y" :value="y">{{ y }}</option>
        </select>
      </div>

      <div class="filter-group checkboxes">
        <label>Berichtsart:</label>
        <div class="checkbox-items">
          <label><input type="checkbox" v-model="reportTypes.calc" /> Berechnungsbericht (FEM/MKS)</label>
          <label><input type="checkbox" v-model="reportTypes.lab" /> Labor-Prüfbericht</label>
          <label><input type="checkbox" v-model="reportTypes.internal" /> Interner Bericht</label>
        </div>
      </div>
    </div>

    <!-- Results -->
    <div class="results" v-if="results.length > 0">
      <h3>ERGEBNISSE ({{ results.length }} von {{ totalDocs }})</h3>

      <div
        v-for="report in results"
        :key="report.id"
        class="result-item"
      >
        <div class="result-header" @click="toggleExpand(report.id)">
          <span class="expand-icon">{{ expanded[report.id] ? '▼' : '▶' }}</span>
          <a :href="report.pdfUrl" target="_blank" class="report-id">
            {{ report.id }}
          </a>
          <span class="relevance">Relevanz: {{ report.relevance }}%</span>
        </div>

        <div class="result-title">{{ report.title }}</div>
        <div class="result-meta">
          Jahr: {{ report.year }} | Typ: {{ report.type }}
        </div>

        <!-- Expanded Fundstellen -->
        <div v-if="expanded[report.id]" class="fundstellen">
          <div class="fundstellen-header">Fundstellen:</div>
          <div
            v-for="hit in report.hits"
            :key="hit.term"
            class="fundstellen-item"
          >
            <span class="term">"{{ hit.term }}"</span>
            <span class="count">{{ hit.count }}x</span>
            <span class="pages">(S. {{ hit.pages.join(', ') }})</span>
          </div>
        </div>
      </div>
    </div>

    <div class="no-results" v-else-if="searchPerformed">
      Keine Ergebnisse gefunden.
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'

const searchQuery = ref('')
const resultCount = ref(10)
const yearFilter = ref('')
const searchPerformed = ref(false)
const totalDocs = ref(331)

const years = ['2026', '2025', '2024', '2023', '2022', '2021', '2020', '2019', '2018']

const reportTypes = reactive({
  calc: true,
  lab: true,
  internal: false
})

const expanded = reactive({})

// Mock results for now
const results = ref([])

const toggleExpand = (id) => {
  expanded[id] = !expanded[id]
}

const performSearch = async () => {
  if (!searchQuery.value.trim()) return
  
  searchPerformed.value = true
  
  // TODO: Call FastAPI backend
  // For now, mock data
  results.value = [
    {
      id: 'BR-2024-0123',
      title: 'Rahmenverformung durch Seitenaufprall',
      year: '2024',
      type: 'Berechnungsbericht',
      relevance: 87,
      pdfUrl: '/pdfs/BR-2024-0123.pdf',
      hits: [
        { term: 'Beule', count: 3, pages: [2, 5, 7] },
        { term: 'Rahmen', count: 12, pages: [1, 2, 3, 4, 5, 6, 7, 8] },
        { term: 'Verformung', count: 5, pages: [3, 4, 5, 6] }
      ]
    },
    {
      id: 'LB-2023-0045',
      title: 'Laborprüfung: Crashtest-Komponente',
      year: '2023',
      type: 'Labor-Prüfbericht',
      relevance: 72,
      pdfUrl: '/pdfs/LB-2023-0045.pdf',
      hits: [
        { term: 'Delle', count: 2, pages: [4, 6] },
        { term: 'Rahmen', count: 8, pages: [2, 3, 4, 5] }
      ]
    }
  ]
}
</script>

<style scoped>
.scry-container {
  max-width: 900px;
  margin: 0 auto;
  padding: 2rem;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

.scry-header h1 {
  font-size: 1.8rem;
  margin-bottom: 1.5rem;
  color: #2c3e50;
}

.search-input {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 1.5rem;
}

.search-field {
  flex: 1;
  padding: 0.75rem 1rem;
  font-size: 1rem;
  border: 2px solid #ddd;
  border-radius: 8px;
  transition: border-color 0.2s;
}

.search-field:focus {
  outline: none;
  border-color: #646cff;
}

.search-btn {
  padding: 0.75rem 1.5rem;
  font-size: 1.2rem;
  background: #646cff;
  color: white;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.2s;
}

.search-btn:hover {
  background: #535bf2;
}

.filters {
  display: flex;
  flex-wrap: wrap;
  gap: 1.5rem;
  margin-bottom: 2rem;
  padding: 1rem;
  background: #f8f9fa;
  border-radius: 8px;
}

.filter-group {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.filter-group label {
  font-weight: 500;
  color: #555;
}

.filter-group select {
  padding: 0.4rem;
  border: 1px solid #ccc;
  border-radius: 4px;
}

.checkbox-items {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.checkbox-items label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-weight: normal;
  cursor: pointer;
}

.results h3 {
  margin-bottom: 1rem;
  color: #2c3e50;
  border-bottom: 2px solid #eee;
  padding-bottom: 0.5rem;
}

.result-item {
  margin-bottom: 1rem;
  padding: 1rem;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  background: white;
  transition: box-shadow 0.2s;
}

.result-item:hover {
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.result-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  cursor: pointer;
}

.expand-icon {
  color: #888;
  font-size: 0.8rem;
}

.report-id {
  font-weight: bold;
  color: #646cff;
  text-decoration: none;
}

.report-id:hover {
  text-decoration: underline;
}

.relevance {
  margin-left: auto;
  color: #27ae60;
  font-weight: 500;
}

.result-title {
  margin-top: 0.5rem;
  font-size: 0.95rem;
  color: #333;
}

.result-meta {
  margin-top: 0.25rem;
  font-size: 0.85rem;
  color: #888;
}

.fundstellen {
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px dashed #ddd;
}

.fundstellen-header {
  font-weight: 500;
  margin-bottom: 0.5rem;
  color: #555;
}

.fundstellen-item {
  display: flex;
  gap: 0.75rem;
  margin-bottom: 0.25rem;
  font-size: 0.9rem;
}

.fundstellen-item .term {
  color: #646cff;
  font-weight: 500;
}

.fundstellen-item .count {
  color: #e67e22;
}

.fundstellen-item .pages {
  color: #888;
}

.no-results {
  text-align: center;
  color: #888;
  padding: 2rem;
}
</style>
