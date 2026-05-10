<template>
  <section class="doubts-list">
    <div class="doubts-head">
      <span>存疑内容</span>
    </div>

    <div class="doubts-grid">
      <div
        v-for="doubt in doubts"
        :key="doubt.id"
        class="doubt-item"
      >
        <span class="doubt-number">{{ doubt.index }}</span>
        <span class="doubt-text">{{ doubt.text }}</span>
      </div>
    </div>
  </section>
</template>

<script setup>
defineProps({
  doubts: {
    type: Array,
    default: () => []
  }
})
</script>

<style scoped>
.doubts-list {
  border-top: 1px solid #edf0f6;
  flex: 0 1 auto;
  margin-bottom: 8px;
  max-height: 118px;
  min-height: 0;
  overflow: auto;
  padding-top: 10px;
}

.doubts-head {
  align-items: center;
  color: #f59e0b;
  display: flex;
  font-size: 13px;
  font-weight: 700;
  justify-content: space-between;
  margin-bottom: 8px;
}

.doubts-grid {
  display: grid;
  gap: 8px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.doubt-item {
  background: #fffbeb;
  border: 1px solid #fde68a;
  border-radius: 8px;
  color: #92400e;
  font-size: 13px;
  font-weight: 650;
  line-height: 1.4;
  min-height: 36px;
  min-width: 0;
  padding: 8px 10px;
  display: flex;
  gap: 8px;
  align-items: flex-start;
}

.doubt-number {
  background: #f59e0b;
  color: #fff;
  border-radius: 50%;
  width: 22px;
  height: 22px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  flex-shrink: 0;
}

.doubt-text {
  flex: 1;
  min-width: 0;
  overflow-wrap: anywhere;
}

@media (max-width: 720px) {
  .doubts-grid {
    grid-template-columns: 1fr;
  }
}
</style>
