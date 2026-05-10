<template>
  <section class="question-list">
    <div class="question-head">
      <span>快速追问建议</span>
      <small v-if="loading">生成中...</small>
    </div>

    <div class="question-grid">
      <button
        v-for="question in questions"
        :key="question.id"
        class="question-button"
        type="button"
        @click="$emit('select', question.text)"
      >
        {{ question.text }}
      </button>
    </div>
  </section>
</template>

<script setup>
defineProps({
  questions: {
    type: Array,
    default: () => []
  },
  loading: {
    type: Boolean,
    default: false
  }
})

defineEmits(['select'])
</script>

<style scoped>
.question-list {
  border-top: 1px solid #edf0f6;
  padding-top: 16px;
  max-height: 200px;
  overflow-y: auto;
}

.question-head {
  align-items: center;
  color: #4653ff;
  display: flex;
  font-size: 14px;
  font-weight: 700;
  justify-content: space-between;
  margin-bottom: 10px;
}

.question-head small {
  color: #8c96aa;
  font-weight: 600;
}

.question-grid {
  display: grid;
  gap: 10px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.question-button {
  background: #effdf5;
  border: 1px solid #bdebd0;
  border-radius: 8px;
  color: #15734a;
  cursor: pointer;
  font-size: 14px;
  font-weight: 650;
  line-height: 1.45;
  min-height: 42px;
  padding: 10px 14px;
  text-align: left;
  transition: border-color 0.16s ease, box-shadow 0.16s ease, transform 0.16s ease;
}

.question-button:hover {
  border-color: #39c178;
  box-shadow: 0 8px 20px rgba(30, 170, 96, 0.12);
  transform: translateY(-1px);
}

@media (max-width: 720px) {
  .question-grid {
    grid-template-columns: 1fr;
  }
}
</style>
