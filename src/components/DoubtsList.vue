<template>
  <section class="doubts-list">
    <div class="doubts-head">
      <span>存疑内容</span>
      <small>{{ doubts.length }} 条</small>
    </div>

    <div v-if="doubts.length" ref="doubtsTimelineRef" class="doubts-timeline">
      <article
        v-for="doubt in doubts"
        :key="doubt.id"
        class="doubt-item"
      >
        <span class="doubt-number">{{ doubt.index }}</span>
        <div>
          <time v-if="doubt.time">{{ doubt.time }}</time>
          <p>{{ doubt.text }}</p>
        </div>
      </article>
    </div>
    <div v-else class="empty-board">等待风险核验</div>
  </section>
</template>

<script setup>
import { nextTick, ref, watch } from 'vue'

const props = defineProps({
  doubts: {
    type: Array,
    default: () => []
  }
})

const doubtsTimelineRef = ref(null)

function scrollDoubtsToBottom() {
  const el = doubtsTimelineRef.value
  if (!el) return

  if (typeof el.scrollTo === 'function') {
    el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
    return
  }

  el.scrollTop = el.scrollHeight
}

watch(
  () => props.doubts.map((item) => `${item.id ?? ''}:${item.time ?? ''}:${item.text ?? ''}`).join('|'),
  async () => {
    await nextTick()
    scrollDoubtsToBottom()
  },
  { flush: 'post', immediate: true }
)
</script>

<style scoped>
.doubts-list {
  background: #fffaf0;
  border: 1px solid #fde4a7;
  border-radius: 10px;
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  overflow: hidden;
  padding: 10px;
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

.doubts-head small {
  color: #a16207;
  font-weight: 800;
}

.doubts-timeline {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 8px;
  min-height: 0;
  overflow: auto;
  padding-right: 2px;
}

.doubt-item {
  align-items: flex-start;
  background: #ffffff;
  border: 1px solid #fde68a;
  border-radius: 8px;
  color: #92400e;
  display: flex;
  font-size: 13px;
  font-weight: 650;
  gap: 8px;
  line-height: 1.4;
  min-width: 0;
  padding: 8px 10px;
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

.doubt-item div {
  flex: 1;
  min-width: 0;
}

.doubt-item time {
  color: #b45309;
  display: block;
  font-size: 11px;
  font-weight: 900;
  margin-bottom: 5px;
}

.doubt-item p {
  margin: 0;
  overflow-wrap: anywhere;
}

.empty-board {
  align-items: center;
  border: 1px dashed #f4cf80;
  border-radius: 8px;
  color: #a16207;
  display: flex;
  flex: 1;
  font-size: 13px;
  font-weight: 700;
  justify-content: center;
  min-height: 140px;
}
</style>
