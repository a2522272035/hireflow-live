<template>
  <Teleport to="body">
    <div v-if="open" class="rsdk-backdrop" @click.self="emit('close')">
      <main class="resume-popup-shell" role="dialog" aria-modal="true" aria-label="简历解析">
        <button type="button" class="popup-close-btn" aria-label="关闭" @click="emit('close')">×</button>
        <div class="resume-analysis-popup">
          <div class="main-container">
            <section class="profile-header-section">
              <div class="profile-main">
                <div class="avatar-section">
                  <img v-if="avatarSrc" :src="avatarSrc" alt="头像" class="avatar-img" />
                  <div v-else class="avatar">{{ profileInitial }}</div>
                </div>
                <div class="profile-info">
                  <div class="name-position">
                    <h1 class="name mytext-primary">{{ valueOr(profile.name, '未知姓名') }}</h1>
                    <span
                      class="position-tag mybadge mybadge-primary mybadge-pill term-trigger"
                      @mouseenter="showTermCard($event, profile.position, '职位')"
                      @mouseleave="scheduleHideTermCard"
                      @click="pinTermCard($event, profile.position, '职位')"
                    >{{ valueOr(profile.position, '职位未识别') }}</span>
                  </div>
                  <div class="badges-row">
                    <span v-for="badge in highlightBadges" :key="`h-${badge}`" class="mybadge mybadge-primary">{{ badge }}</span>
                    <span v-if="salaryBadge" class="mybadge mybadge-info">{{ salaryBadge }}</span>
                    <span v-for="badge in riskBadges" :key="`r-${badge}`" class="mybadge mybadge-warning">{{ badge }}</span>
                  </div>
                  <div class="basic-info-row">
                    <span class="info-item"><span class="info-icon">⚥</span>{{ valueOr(profile.gender) }}</span>
                    <span class="info-item"><span class="info-icon">◷</span>{{ valueOr(profile.age) }}岁</span>
                    <span class="info-item"><span class="info-icon">⌖</span>{{ valueOr(profile.location) }}</span>
                    <span class="info-item"><span class="info-icon">▦</span>{{ valueOr(profile.workYear) }}年经验</span>
                  </div>
                  <div class="contact-row">
                    <span class="info-item"><span class="info-icon">▥</span>{{ valueOr(profile.college) }}</span>
                    <span class="info-item"><span class="info-icon">◒</span>{{ valueOr(profile.degree) }}</span>
                    <span class="info-item"><span class="info-icon">☎</span>{{ valueOr(profile.phone) }}</span>
                    <span class="info-item"><span class="info-icon">✉</span>{{ valueOr(profile.email, '暂无邮箱') }}</span>
                  </div>
                </div>
              </div>
            </section>

            <section class="tabs-section">
              <div class="tabs-nav">
                <button type="button" class="tab-item" :class="{ active: activeTab === 'parser' }" @click="activeTab = 'parser'">
                  <span class="tab-icon">▤</span> 简历解析
                </button>
                <button type="button" class="tab-item" :class="{ active: activeTab === 'profiler' }" @click="activeTab = 'profiler'">
                  <span class="tab-icon">◉</span> 简历画像
                </button>
              </div>

              <div v-show="activeTab === 'parser'" class="tab-content">
                <div class="content-section">
                  <div class="section-header row-bordered">
                    <span class="section-icon">▤</span>
                    <span class="mytext-primary">简历信息</span>
                  </div>
                  <table class="table-layout">
                    <tbody>
                      <tr>
                        <td class="mytext-muted">简历类型</td>
                        <td>{{ valueOr(profile.resumeType) }}</td>
                        <td class="mytext-muted">简历完整度</td>
                        <td>{{ valueOr(profile.integrity) }}</td>
                      </tr>
                      <tr>
                        <td class="mytext-muted">简历解析时间</td>
                        <td colspan="3">{{ valueOr(profile.parsedAt) }}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>

                <div class="content-section">
                  <div class="section-header row-bordered">
                    <span class="section-icon">◎</span>
                    <span class="mytext-primary">基本信息</span>
                  </div>
                  <table class="table-layout">
                    <tbody>
                      <tr v-for="(row, rowIndex) in basicRows" :key="`basic-${rowIndex}`">
                        <template v-for="item in row" :key="item.label">
                          <td class="mytext-muted">{{ item.label }}</td>
                          <td>{{ valueOr(item.value) }}</td>
                        </template>
                      </tr>
                    </tbody>
                  </table>
                </div>

                <div class="content-section">
                  <div class="section-header row-bordered">
                    <span class="section-icon">☎</span>
                    <span class="mytext-primary">联系方式</span>
                  </div>
                  <table class="table-layout">
                    <tbody>
                      <tr>
                        <td class="mytext-muted">联系电话</td>
                        <td colspan="3">{{ valueOr(profile.phone) }}</td>
                      </tr>
                      <tr>
                        <td class="mytext-muted">电子邮箱</td>
                        <td colspan="3">{{ valueOr(profile.email, '暂无') }}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>

                <div class="content-section">
                  <div class="section-header row-bordered">
                    <span class="section-icon">◎</span>
                    <span class="mytext-primary">期望工作</span>
                  </div>
                  <table class="table-layout">
                    <tbody>
                      <tr>
                        <td class="mytext-muted">期望职位</td>
                        <td>{{ valueOr(profile.expectJob) }}</td>
                        <td class="mytext-muted">期望薪资</td>
                        <td class="salary-highlight">{{ valueOr(profile.expectSalary) }}</td>
                      </tr>
                      <tr>
                        <td class="mytext-muted">期望月薪(下限)</td>
                        <td>{{ valueOr(profile.expectSalaryMin, '暂无') }}</td>
                        <td class="mytext-muted">期望月薪(上限)</td>
                        <td>{{ valueOr(profile.expectSalaryMax, '暂无') }}</td>
                      </tr>
                      <tr>
                        <td class="mytext-muted">期望工作地点</td>
                        <td>{{ valueOr(profile.expectLocation, '暂无') }}</td>
                        <td class="mytext-muted">期望工作地点(规范化)</td>
                        <td>{{ valueOr(profile.expectLocationNorm, '暂无') }}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>

                <div class="content-section">
                  <div class="section-header row-bordered">
                    <span class="section-icon">◒</span>
                    <span class="mytext-primary">教育经历</span>
                  </div>
                  <div class="r_content">
                    <template v-if="education.length">
                      <div v-for="(item, index) in education" :key="`edu-${index}`" class="timeline-lite-item">
                        <div class="timeline-lite-line">
                          <span class="r_circle mybg-primary"></span>
                          <span class="mytext-primary fw-bold">{{ valueOr(item.school) }}</span>
                          <span class="mx-2 mytext-muted">-</span>
                          <span class="fw-medium">{{ valueOr(item.major) }}</span>
                          <span class="r_small period-text">{{ valueOr(item.duration) }}</span>
                        </div>
                        <div class="r_indent2 mytext-muted">{{ valueOr(item.degree) }}{{ item.schoolType ? ` · ${item.schoolType}` : '' }}</div>
                      </div>
                    </template>
                    <div v-else class="empty-hint">暂无教育经历</div>
                  </div>
                </div>

                <div class="content-section">
                  <div class="section-header row-bordered">
                    <span class="section-icon">▦</span>
                    <span class="mytext-primary">工作经历</span>
                  </div>
                  <table class="table-layout work-table">
                    <tbody>
                      <template v-if="experiences.length">
                        <template v-for="(item, index) in experiences" :key="`job-${index}`">
                          <tr>
                            <td colspan="4"><span class="r_circle mybg-primary"></span> <span class="fw-bold">{{ valueOr(item.duration, '工作时间未识别') }}</span></td>
                          </tr>
                          <tr>
                            <td colspan="4"><span class="r_circle mybg-primary"></span> <strong>公司信息：名称:{{ valueOr(item.company, '未识别') }}</strong></td>
                          </tr>
                          <tr>
                            <td colspan="4"><span class="r_circle mybg-primary"></span> <strong>职位信息：名称:{{ valueOr(item.position, '未识别') }}{{ item.positionType ? ` | 职能类型:${item.positionType}` : '' }}</strong></td>
                          </tr>
                          <tr>
                            <td colspan="4">
                              <span class="r_circle mybg-primary"></span>
                              <strong>工作描述：</strong><br />
                              <div class="ml-4 description-text">{{ valueOr(item.description, '未识别') }}</div>
                            </td>
                          </tr>
                          <tr v-if="index < experiences.length - 1"><td colspan="4">&nbsp;</td></tr>
                        </template>
                      </template>
                      <tr v-else>
                        <td colspan="4"><div class="empty-hint">暂无工作经历</div></td>
                      </tr>
                    </tbody>
                  </table>
                </div>

                <div v-if="projects.length" class="content-section">
                  <div class="section-header row-bordered">
                    <span class="section-icon">◇</span>
                    <span class="mytext-primary">项目经历</span>
                  </div>
                  <div class="r_content">
                    <div v-for="(item, index) in projects" :key="`project-${index}`" class="timeline-lite-item">
                      <div class="timeline-lite-line">
                        <span class="r_circle mybg-info"></span>
                        <span class="fw-bold">{{ valueOr(item.name) }}</span>
                        <span class="r_small period-text">{{ valueOr(item.duration) }}</span>
                      </div>
                      <div class="description-text">{{ valueOr(item.description || item.responsibility, '未识别') }}</div>
                    </div>
                  </div>
                </div>

                <div class="content-section">
                  <div class="section-header row-bordered">
                    <span class="section-icon">▣</span>
                    <span class="mytext-primary">证书及奖项</span>
                  </div>
                  <div class="r_content">
                    <template v-if="certificates.length">
                      <div v-for="(cert, index) in certificates" :key="`cert-${index}`" class="mb-2">
                        <span class="r_circle mybg-warning"></span>
                        <span class="mytext-muted">证书{{ index + 1 }}：</span>
                        <span class="fw-medium">{{ cert }}</span>
                      </div>
                    </template>
                    <div v-else class="empty-hint">暂无证书信息</div>
                  </div>
                </div>

                <div class="content-section">
                  <div class="section-header row-bordered">
                    <span class="section-icon">▧</span>
                    <span class="mytext-primary">所获证书（文本）</span>
                  </div>
                  <div class="r_content">
                    <div class="mytext-muted">{{ certificateText }}</div>
                  </div>
                </div>

                <div class="content-section">
                  <div class="section-header row-bordered">
                    <span class="section-icon">⚙</span>
                    <span class="mytext-primary">技能列表</span>
                  </div>
                  <div class="skills-panel">
                    <template v-if="skillDisplayGroups.length">
                      <div class="skills-summary">
                        <span>识别技能 {{ skills.length }} 项</span>
                        <span>已按类型整理展示</span>
                      </div>
                      <div class="skill-group-list">
                        <section v-for="group in skillDisplayGroups" :key="group.label" class="skill-group-card">
                          <header class="skill-group-head">
                            <span>{{ group.label }}</span>
                            <b>{{ group.items.length }}</b>
                          </header>
                          <div class="skill-chip-grid">
                            <span
                              v-for="skill in group.items"
                              :key="`${group.label}-${skill}`"
                              class="skill-chip term-trigger"
                              :title="skill"
                              @mouseenter="showTermCard($event, skill, group.label)"
                              @mouseleave="scheduleHideTermCard"
                              @click="pinTermCard($event, skill, group.label)"
                            >{{ skill }}</span>
                          </div>
                        </section>
                      </div>
                    </template>
                    <div v-else class="empty-hint">暂无技能信息</div>
                  </div>
                </div>

                <div class="content-section">
                  <div class="section-header row-bordered">
                    <span class="section-icon">❝</span>
                    <span class="mytext-primary">自我评价</span>
                  </div>
                  <div class="ml-4 description-text">{{ valueOr(profile.summary, '暂无自我评价') }}</div>
                </div>
              </div>

              <div v-show="activeTab === 'profiler'" class="tab-content">
                <table class="w-100 profiler-reference-table">
                  <tbody>
                    <tr>
                      <td colspan="4"><h5 class="row-bordered font-weight-bold"><span class="mytext-primary r_indent2">▶</span>简历亮点</h5></td>
                    </tr>
                    <tr>
                      <td colspan="4">
                        <h6><span class="ml-3 mr-2 mytext-primary">👍</span>亮点信息 <span class="mybadge mybadge-pill mybadge-primary">{{ highlightItems.length }}</span></h6>
                        <div v-if="highlightItems.length">
                          <div v-for="item in highlightItems" :key="item" class="my-1 ml-4">
                            <i class="r_circle mx-2 my-1 mybg-primary"></i><span class="r_small" v-html="item"></span>
                          </div>
                        </div>
                        <div v-else class="my-1 ml-4">
                          <i class="r_circle mx-2 my-1 mybg-primary"></i><span class="r_small">暂无突出亮点</span>
                        </div>

                        <h6 class="mt-3"><span class="ml-3 mr-2 mytext-warning">ⓘ</span>风险信息 <span class="mybadge mybadge-pill mybadge-warning">{{ riskItems.length }}</span></h6>
                        <div v-if="riskItems.length">
                          <div v-for="item in riskItems" :key="item" class="my-1 ml-4">
                            <i class="r_circle mx-2 my-1 mybg-warning"></i><span class="r_small" v-html="item"></span>
                          </div>
                        </div>
                        <div v-else class="my-1 ml-4">
                          <i class="r_circle mx-2 my-1 mybg-warning"></i><span class="r_small">未发现明显风险</span>
                        </div>

                        <h6 class="mt-3"><span class="ml-3 mr-2 mytext-info">✎</span>智能评估 <span class="mybadge mybadge-pill mybadge-info">1</span></h6>
                        <div class="my-1 ml-4">
                          <i class="r_circle mx-2 my-1 mybg-info"></i><span class="r_small" v-html="assessmentLine"></span>
                        </div>
                      </td>
                    </tr>

                    <tr>
                      <td colspan="4"><h5 class="row-bordered font-weight-bold mt-3"><span class="mytext-primary r_indent2">▶</span>简历标签</h5></td>
                    </tr>
                    <tr v-for="tagCat in profileTagCategories" :key="tagCat.category">
                      <td colspan="4">
                        <h6 class="mt-3"><span class="ml-3 mr-2" :class="tagCat.iconClass">▷</span>{{ tagCat.category }}</h6>
                        <h5>
                          <div v-for="sub in tagCat.subs" :key="`${tagCat.category}-${sub.label}`" class="my-1 ml-4 profiler-tag-row">
                            <i class="r_circle mx-1" :class="`mybg-${tagCat.badgeColor}`"></i>
                            <span class="r_small_70">{{ sub.label }}：</span>
                            <span
                              v-for="item in sub.items"
                              :key="`${tagCat.category}-${sub.label}-${item.text}`"
                              class="mybadge term-trigger"
                              :class="`mybadge-${tagCat.badgeColor}`"
                              :title="item.tooltip || item.text"
                              @mouseenter="showTermCard($event, item.text, `${tagCat.category} / ${sub.label}`, item.tooltip)"
                              @mouseleave="scheduleHideTermCard"
                              @click="pinTermCard($event, item.text, `${tagCat.category} / ${sub.label}`, item.tooltip)"
                            >{{ item.text }}</span>
                          </div>
                        </h5>
                      </td>
                    </tr>

                    <tr>
                      <td colspan="4"><h5 class="row-bordered font-weight-bold mt-3"><span class="mytext-primary r_indent2">▶</span>综合评估</h5></td>
                    </tr>
                    <tr>
                      <td colspan="4"><h5 class="text-center mt-3">能力指数</h5></td>
                    </tr>
                    <tr>
                      <td colspan="4">
                        <div class="chart-container">
                          <RadarChart :items="abilityScores" />
                        </div>
                      </td>
                    </tr>
                    <tr>
                      <td colspan="4"><h5 class="text-center mt-3">一级行业</h5></td>
                    </tr>
                    <tr>
                      <td colspan="4">
                        <div class="chart-container">
                          <RadarChart :items="industryScores" variant="industry" />
                        </div>
                      </td>
                    </tr>
                    <tr>
                      <td colspan="4"><h5 class="text-center mt-3">二级行业</h5></td>
                    </tr>
                    <tr>
                      <td colspan="4">
                        <div class="chart-container pie-space">
                          <DonutChart :segments="secondaryIndustrySegments" label="二级行业" />
                        </div>
                      </td>
                    </tr>
                    <tr>
                      <td colspan="4"><h5 class="text-center mt-3">职位职能</h5></td>
                    </tr>
                    <tr>
                      <td colspan="4">
                        <div class="chart-container pie-space">
                          <DonutChart :segments="jobFunctionSegments" label="职位职能" half />
                        </div>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </section>
          </div>
        </div>
      </main>
      <aside
        v-if="termCard.visible"
        class="term-card"
        :class="{ pinned: termCard.pinned }"
        :style="{ left: `${termCard.x}px`, top: `${termCard.y}px` }"
        @mouseenter="keepTermCard"
        @mouseleave="scheduleHideTermCard"
      >
        <div class="term-card-head">
          <div>
            <span>{{ termCard.category || '术语解释' }}</span>
            <strong>{{ termCard.term }}</strong>
          </div>
          <button type="button" @click="hideTermCard">×</button>
        </div>
        <p>{{ termCard.explanation }}</p>
        <div v-if="termCard.aiAnswer" class="term-ai-answer">{{ termCard.aiAnswer }}</div>
        <button type="button" class="term-ai-btn" :disabled="termCard.loading" @click="askAiForTerm">
          {{ termCard.loading ? 'AI解释中...' : '继续问 AI' }}
        </button>
      </aside>
    </div>
  </Teleport>
</template>

<script setup>
import { computed, defineComponent, h, ref, watch } from 'vue'

const props = defineProps({
  open: {
    type: Boolean,
    default: false
  },
  resume: {
    default: () => ({})
  }
})

const emit = defineEmits(['close'])
const activeTab = ref('parser')
const termCard = ref({
  visible: false,
  pinned: false,
  loading: false,
  term: '',
  category: '',
  context: '',
  explanation: '',
  aiAnswer: '',
  x: 0,
  y: 0
})
let termHideTimer = null

watch(
  () => props.open,
  (value) => {
    if (value) {
      activeTab.value = 'parser'
    } else {
      hideTermCard()
    }
  }
)

const SectionRow = defineComponent({
  props: { title: { type: String, required: true } },
  setup(sectionProps) {
    return () => h('tr', [
      h('td', { colspan: 4 }, [
        h('h5', { class: 'row-bordered font-weight-bold' }, [
          h('span', { class: 'section-triangle' }, '▶'),
          sectionProps.title
        ])
      ])
    ])
  }
})

const FieldLine = defineComponent({
  props: {
    label: { type: String, required: true },
    value: { default: '' }
  },
  setup(fieldProps) {
    return () => h('div', { class: 'r_content' }, [
      h('span', { class: 'mytext-muted' }, `${fieldProps.label}:`),
      ` ${valueOr(fieldProps.value)}`
    ])
  }
})

const FieldPairRow = defineComponent({
  props: { items: { type: Array, default: () => [] } },
  setup(rowProps) {
    return () => h('tr', [0, 1].map((index) => {
      const item = rowProps.items[index] || { label: '', value: '' }
      return h('td', { colspan: 2 }, item.label
        ? h(FieldLine, { label: item.label, value: item.value })
        : null)
    }))
  }
})

const ProfilerLine = defineComponent({
  props: {
    tone: { type: String, default: 'primary' },
    html: { type: String, default: '' }
  },
  setup(lineProps) {
    return () => h('div', { class: 'profiler-line' }, [
      h('i', { class: ['r_circle', `mybg-${lineProps.tone}`] }),
      h('span', { class: 'r_small', innerHTML: lineProps.html })
    ])
  }
})

const TagBlock = defineComponent({
  props: {
    title: { type: String, required: true },
    tone: { type: String, default: 'primary' },
    groups: { type: Array, default: () => [] }
  },
  setup(blockProps) {
    const limit = blockProps.title === '技能标签' ? 16 : 12
    return () => h('div', { class: 'tag-block' }, [
      h('h6', { class: 'tag-title' }, [
        h('span', { class: ['tag-title-icon', `mytext-${blockProps.tone}`] }, '▷'),
        h('span', blockProps.title),
        h('em', `${blockProps.groups.reduce((sum, group) => sum + group.items.length, 0)}`)
      ]),
      h('div', { class: 'tag-group-grid' }, blockProps.groups.map((group) => {
        const visibleItems = group.items.slice(0, limit)
        const hiddenItems = group.items.slice(limit)
        return h('section', { class: 'tag-line' }, [
        h('i', { class: ['r_circle', `mybg-${blockProps.tone}`] }),
        h('span', { class: 'r_small_70 tag-line-label' }, [
          `${group.label}：`,
          h('em', `${group.items.length}`)
        ]),
        h('div', { class: 'tag-badges' }, [
          ...visibleItems.map((item) => h('span', {
          class: ['mybadge', `mybadge-${blockProps.tone}`],
          title: item.tooltip || item.text
          }, item.text)),
          hiddenItems.length ? h('span', {
            class: ['mybadge', 'mybadge-more'],
            title: hiddenItems.map((item) => item.text).join('、')
          }, `+${hiddenItems.length}`) : null
        ])
      ])
      }))
    ])
  }
})

const RadarChart = defineComponent({
  props: {
    items: { type: Array, required: true },
    variant: { type: String, default: '' }
  },
  setup(chartProps) {
    return () => {
      const radar = makeRadar(chartProps.items)
      const isIndustry = chartProps.variant === 'industry'
      const lineColor = isIndustry ? '#42BA96' : '#335EEA'
      const areaColor = isIndustry ? 'rgba(66, 186, 150, 0.2)' : 'rgba(51, 94, 234, 0.25)'
      return h('svg', { class: 'rsdk-radar', viewBox: '0 0 540 360', role: 'img' }, [
        h('g', { transform: 'translate(150,55) scale(1)' }, [
          ...radar.grid.map((polygon) => h('polygon', {
            points: polygon,
            fill: 'none',
            stroke: 'rgba(51, 94, 234, 0.15)',
            'stroke-width': 1
          })),
          ...radar.axes.map((axis) => h('line', {
            x1: 120,
            y1: 120,
            x2: axis.x,
            y2: axis.y,
            stroke: 'rgba(51, 94, 234, 0.15)',
            'stroke-width': 1
          })),
          h('polygon', {
            points: radar.area,
            fill: areaColor,
            stroke: lineColor,
            'stroke-width': 2
          }),
          ...radar.points.map((point) => h('circle', {
            cx: point.x,
            cy: point.y,
            r: 3,
            fill: lineColor
          })),
          ...radar.axes.map((axis) => h('text', {
            x: axis.labelX,
            y: axis.labelY,
            fill: '#4a5568',
            'font-size': 11,
            'text-anchor': 'middle'
          },
            axis.labelLines.map((line, index) => h('tspan', { x: axis.labelX, dy: index === 0 ? 0 : 13, fill: '#4a5568' }, line))
          ))
        ])
      ])
    }
  }
})

const DonutChart = defineComponent({
  props: {
    segments: { type: Array, required: true },
    label: { type: String, default: '' },
    half: { type: Boolean, default: false }
  },
  setup(chartProps) {
    return () => {
      const arcs = buildArcSegments(chartProps.segments, chartProps.half)
      return h('div', { class: ['donut-wrap', chartProps.half ? 'half-wrap' : ''] }, [
        h('svg', {
          class: ['donut-svg', chartProps.half ? 'half' : ''],
          viewBox: chartProps.half ? '0 0 360 235' : '0 0 360 300',
          role: 'img'
        }, [
          ...arcs.map((arc) => h('path', {
            d: arc.path,
            fill: 'none',
            stroke: arc.color || '#335EEA',
            'stroke-linecap': 'round',
            'stroke-width': chartProps.half ? 38 : 42
          })),
          h('text', {
            x: 180,
            y: chartProps.half ? 166 : 140,
            fill: '#7a8799',
            'font-size': 13,
            'font-weight': 600,
            'text-anchor': 'middle'
          }, chartProps.label)
        ]),
        h('div', { class: 'legend-row' }, arcs.map((item) => h('span', [
          h('i', { style: { background: item.color } }),
          `${item.label} (${item.value})`
        ])))
      ])
    }
  }
})

const resumeData = computed(() => props.resume || {})
const raw = computed(() => resumeData.value.raw_result || resumeData.value.raw || {})
const evalData = computed(() => resumeData.value.eval || {})
const tagsData = computed(() => resumeData.value.tags || {})
const profilerSource = computed(() => {
  const candidates = [
    resumeData.value.profile,
    resumeData.value.profiler,
    resumeData.value.portrait,
    resumeData.value.resume_profile,
    raw.value.profile,
    raw.value.profiler,
    raw.value.portrait,
    raw.value.resume_profile,
    raw.value.profile_result,
    raw.value.profiler_result
  ]
  return candidates.find((item) => item && typeof item === 'object') || {}
})

function valueByKeys(...keys) {
  for (const key of keys) {
    const value = resumeData.value?.[key]
    if (value !== undefined && value !== null && value !== '') return value
    const rawValue = raw.value?.[key]
    if (rawValue !== undefined && rawValue !== null && rawValue !== '') return rawValue
  }
  return ''
}

function valueOr(value, fallback = '未识别') {
  if (Array.isArray(value)) return value.length ? value.join('、') : fallback
  if (value === undefined || value === null || value === '') return fallback
  return String(value)
}

function asArray(value) {
  if (Array.isArray(value)) return value.filter(Boolean)
  if (!value) return []
  if (typeof value === 'string') {
    return value.split(/[、,，;；\n]/).map((item) => item.trim()).filter(Boolean)
  }
  return [value]
}

function groupSkills(values) {
  const categories = [
    { label: '财务/会计', pattern: /会计|财务|总账|账务|核算|报表|成本|费用|利润|凭证|明细账|现金流|资产负债/ },
    { label: '税务/审计', pattern: /税|纳税|申报|汇算|审计|内控|合规|风控|工商年检/ },
    { label: '票据/出纳', pattern: /票据|发票|出纳|收款|付款|报销|银行|现金|往来|应收|应付/ },
    { label: '技术/系统', pattern: /Java|Python|前端|后端|算法|数据库|SQL|Excel|ERP|SAP|金蝶|用友|软件|系统|平台|数据/ },
    { label: '运营/业务', pattern: /运营|销售|市场|客服|客户|供应链|物流|采购|项目|产品|渠道|商务/ },
    { label: '管理/协作', pattern: /管理|沟通|协调|团队|培训|组织|计划|流程|制度|复盘|汇报/ }
  ]
  const groups = categories.map((category) => ({ ...category, items: [] }))
  const other = { label: '其他技能', items: [] }

  values.forEach((value) => {
    const text = String(value || '').trim()
    if (!text) return
    const target = groups.find((group) => group.pattern.test(text)) || other
    target.items.push(text)
  })

  return [...groups, other]
    .filter((group) => group.items.length)
    .map((group) => ({
      label: group.label,
      items: uniq(group.items).slice(0, 36)
    }))
}

function uniq(values) {
  return Array.from(new Set(values.map((item) => String(item || '').trim()).filter(Boolean)))
}

function numberIn(value) {
  const match = String(value || '').match(/\d+(\.\d+)?/)
  return match ? Number(match[0]) : 0
}

function safeScore(value) {
  return Math.max(15, Math.min(100, Math.round(value)))
}

function escapeHtml(value) {
  return String(value || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function hi(value, tone = 'primary') {
  return `【<span class="mytext-${tone}">${escapeHtml(value)}</span>】`
}

function durationText(item) {
  return item.duration || item.job_duration || [item.start_date, item.end_date].filter(Boolean).join('~')
}

function showTermCard(event, term, category = '', context = '') {
  const cleanTerm = String(term || '').trim()
  if (!cleanTerm || cleanTerm === '未识别') return
  clearTermHideTimer()
  const rect = event.currentTarget?.getBoundingClientRect?.() || { left: 0, bottom: 0 }
  termCard.value = {
    visible: true,
    pinned: false,
    loading: false,
    term: cleanTerm,
    category,
    context: String(context || ''),
    explanation: localTermExplanation(cleanTerm, category, context),
    aiAnswer: '',
    x: Math.min(Math.max(rect.left, 16), window.innerWidth - 360),
    y: Math.min(rect.bottom + 8, window.innerHeight - 240)
  }
}

function pinTermCard(event, term, category = '', context = '') {
  showTermCard(event, term, category, context)
  termCard.value.pinned = true
}

function keepTermCard() {
  clearTermHideTimer()
}

function scheduleHideTermCard() {
  clearTermHideTimer()
  if (termCard.value.pinned) return
  termHideTimer = window.setTimeout(() => hideTermCard(), 180)
}

function clearTermHideTimer() {
  if (termHideTimer) {
    window.clearTimeout(termHideTimer)
    termHideTimer = null
  }
}

function hideTermCard() {
  clearTermHideTimer()
  termCard.value.visible = false
  termCard.value.pinned = false
  termCard.value.loading = false
}

const termGlossary = [
  {
    pattern: /mysql/i,
    text: 'MySQL 是一种常见的关系型数据库，用来存储和查询结构化数据，比如用户、订单、财务记录、商品信息。实际工作里通常会用 SQL 写查询、建表、做索引优化、处理事务和备份恢复。面试可追问：你最近一次用 MySQL 解决了什么业务问题？'
  },
  {
    pattern: /\bsql\b|结构化查询语言/i,
    text: 'SQL 是操作关系型数据库的查询语言，用来新增、查询、更新、删除数据，也能做统计汇总和多表关联。它常用于报表、数据核对、后台管理和业务分析。面试可追问：你会写到什么复杂度的 SQL，是否做过联表、分组统计或性能优化？'
  },
  {
    pattern: /redis/i,
    text: 'Redis 是一种内存型数据存储工具，特点是读写速度快，常用于缓存、验证码、登录状态、排行榜、消息队列等场景。它体现候选人对高并发和性能优化的理解。面试可追问：你用 Redis 存过什么数据，如何处理过期和一致性？'
  },
  {
    pattern: /oracle/i,
    text: 'Oracle 是企业级关系型数据库，常见于金融、政企、制造等对稳定性和权限控制要求较高的系统。它用于存储核心业务数据、财务数据和复杂事务。面试可追问：你主要负责查询、维护、性能调优，还是业务数据核对？'
  },
  {
    pattern: /mongodb/i,
    text: 'MongoDB 是文档型数据库，数据以类似 JSON 的文档保存，适合字段变化较多、结构不固定的业务，比如内容、日志、配置、画像数据。面试可追问：你为什么选择 MongoDB，而不是 MySQL 这类关系型数据库？'
  },
  {
    pattern: /python/i,
    text: 'Python 是一种通用编程语言，语法简洁，常用于数据处理、自动化脚本、接口服务、爬虫、AI 和报表生成。简历里出现 Python，通常说明候选人可能具备自动化或数据分析能力。面试可追问：你用 Python 写过什么可复用工具？'
  },
  {
    pattern: /java(?!script)/i,
    text: 'Java 是企业后端开发常用语言，适合构建稳定的业务系统、接口服务、后台管理和中大型应用。它常和 Spring Boot、数据库、缓存、消息队列一起使用。面试可追问：你负责过哪些后端模块，是否处理过性能或并发问题？'
  },
  {
    pattern: /javascript|typescript|前端脚本/i,
    text: 'JavaScript/TypeScript 是前端开发核心语言，用来实现网页交互、数据展示、表单校验和前后端通信。TypeScript 在 JavaScript 基础上增加类型约束，适合大型项目。面试可追问：你做过哪些复杂交互或组件封装？'
  },
  {
    pattern: /\bvue\b|vue\.js/i,
    text: 'Vue 是前端框架，用来构建页面组件、管理界面状态和实现单页应用。它常用于后台系统、数据看板、业务表单和中台页面。面试可追问：你是否独立封装过组件、处理过状态管理或性能问题？'
  },
  {
    pattern: /react/i,
    text: 'React 是前端框架，用组件方式构建用户界面，常用于中后台系统、官网、移动端 H5 和复杂交互页面。它强调状态驱动视图。面试可追问：你如何拆分组件，如何处理状态、性能和接口数据？'
  },
  {
    pattern: /spring\s*boot|springboot/i,
    text: 'Spring Boot 是 Java 后端框架，用来快速开发接口服务、业务系统和微服务。它能整合数据库、缓存、权限、定时任务等能力。面试可追问：你做过哪些接口模块，是否参与过权限、事务或异常处理设计？'
  },
  {
    pattern: /linux/i,
    text: 'Linux 是服务器常用操作系统，后端服务、数据库和部署环境大多运行在 Linux 上。相关能力通常包括命令行操作、日志排查、服务启动、权限和脚本。面试可追问：你是否独立排查过线上日志或部署过服务？'
  },
  {
    pattern: /docker/i,
    text: 'Docker 是容器化工具，可以把应用和运行环境打包在一起，方便部署、迁移和隔离。常用于开发测试环境、服务部署和持续集成。面试可追问：你是否写过 Dockerfile，是否处理过镜像、端口、挂载和日志问题？'
  },
  {
    pattern: /kubernetes|k8s/i,
    text: 'Kubernetes/K8s 是容器编排平台，用来管理大量容器服务的部署、扩容、重启、服务发现和配置。它偏运维和云原生方向。面试可追问：你是使用者还是维护者，负责过发布、扩容还是故障排查？'
  },
  {
    pattern: /\bgit\b|github|gitlab/i,
    text: 'Git 是代码版本管理工具，用来记录代码变更、多人协作、分支开发和回滚历史。GitHub/GitLab 是常见代码托管平台。面试可追问：你在团队里如何使用分支、合并请求和代码评审？'
  },
  {
    pattern: /excel|透视表|vlookup|函数/i,
    text: 'Excel 是办公和数据处理工具，常用于台账、统计、报表、核对和简单分析。熟练使用通常包括函数、透视表、数据校验、条件格式和图表。面试可追问：你是否做过自动化模板或复杂数据核对？'
  },
  {
    pattern: /power\s*bi|tableau|数据看板/i,
    text: 'Power BI/Tableau 是数据可视化和商业分析工具，用来把业务数据做成图表、看板和经营分析报表。它体现数据理解和指标表达能力。面试可追问：你做过哪些指标看板，数据来源和口径如何确定？'
  },
  {
    pattern: /账务处理|账务管理|账务|总账会计|全盘账务|明细账|账簿/i,
    text: '账务处理是把企业日常业务按会计规则记录到凭证、账簿和报表中的过程，包括凭证录入、审核、月结、总账和明细账核对。全盘账务/总账会计通常代表能独立处理完整账套。面试可追问：你是否独立负责过月结和总账调整？'
  },
  {
    pattern: /财务核算|核算|成本核算|税务成本|费用支出|费用报销单据/i,
    text: '财务核算是把收入、成本、费用、税费等业务数据按规则归集和计算，形成准确的财务结果。成本核算关注成本归集、分摊和差异分析，费用报销单据则关系到费用合规和入账依据。面试可追问：你如何确认核算口径和原始单据真实性？'
  },
  {
    pattern: /财务|会计|财务管理制度|财务对接|归档财务/i,
    text: '财务/会计工作负责记录、核算、监督企业资金和经营活动，常涉及凭证、账簿、报表、税务和内控制度。财务对接与归档财务体现跨部门沟通和资料规范管理能力。面试可追问：你负责过哪些财务流程，哪些环节由你最终复核？'
  },
  {
    pattern: /现金流量表|利润表|资产负债表/i,
    text: '现金流量表、利润表、资产负债表是企业核心财务报表，分别反映现金流入流出、盈利情况和资产负债结构。能处理这些报表通常说明候选人理解财务结果和报表勾稽关系。面试可追问：你是否独立出具或复核过三大报表？'
  },
  {
    pattern: /原始凭证审核|凭证|财务票据|票据管理|票据/i,
    text: '原始凭证和票据是财务入账的基础材料，如发票、收据、合同、付款单等。审核凭证/票据主要看真实性、合规性、金额和业务匹配关系。面试可追问：你遇到过哪些不合规票据，如何处理和留痕？'
  },
  {
    pattern: /纳税申报表|纳税申报|税务申报|缴纳税款|税务处理|所得税|企业所得税/i,
    text: '纳税申报是企业按税法要求计算并提交应缴税费的过程，涉及增值税、所得税、附加税等。纳税申报表是申报依据，缴纳税款是申报后的资金支付动作。面试可追问：你独立申报过哪些税种，异常数据如何核对？'
  },
  {
    pattern: /汇算清缴|税务筹划|税务合规|规避税务风险|税务机关/i,
    text: '汇算清缴通常指年度企业所得税的最终清算，税务筹划是在合法合规前提下优化税负和业务安排。税务合规与税务风险控制强调按税法、票据和申报口径处理业务。面试可追问：你参与过哪些汇算清缴调整事项？'
  },
  {
    pattern: /外部审计|内部审计|审计报告|审计/i,
    text: '审计是对财务数据、业务流程和内控有效性进行检查。外部审计通常由会计师事务所执行，内部审计更偏企业内部风险检查。审计报告记录审计结论和问题。面试可追问：你在审计中负责提供哪些资料，处理过哪些审计调整？'
  },
  {
    pattern: /工商年检|工商年报/i,
    text: '工商年检/工商年报是企业每年向市场监管部门报送基本经营信息、股东信息、资产状况等资料的合规事项。它体现候选人对企业基础合规流程的熟悉程度。面试可追问：你是否独立完成过年报填报和异常处理？'
  },
  {
    pattern: /发票管理|普通发票|发票/i,
    text: '发票管理包括发票开具、认证、抵扣、保管、作废和红冲等工作。普通发票是常见发票类型之一，主要用于记录交易和入账凭证。面试可追问：你是否处理过异常发票、红冲发票或进销项核对？'
  },
  {
    pattern: /出纳|应付账款|款项管理/i,
    text: '出纳负责现金、银行存款、收付款和资金日记账等基础资金工作。应付账款和款项管理关注企业对供应商、员工或其他往来方的付款义务和付款计划。面试可追问：你如何安排付款审批、对账和资金安全控制？'
  },
  {
    pattern: /客户对账|财务对接|账实相符/i,
    text: '对账是把企业内部账面数据与客户、供应商、银行或实物库存进行核对，确保金额、余额和业务事实一致。账实相符强调账面记录与实际资产或业务一致。面试可追问：你处理过哪些对账差异，如何追溯原因？'
  },
  {
    pattern: /结转|核销/i,
    text: '结转是把某类收入、成本、费用或余额按会计期间转入相应科目，核销是对已确认的往来、坏账、预付款等事项进行冲抵或关闭。它们都关系到期末账务准确性。面试可追问：你做过哪些期末结转和往来核销？'
  }
]

function localTermExplanation(term, category = '', context = '') {
  const text = String(term || '')
  const categoryText = String(category || '')
  const contextText = String(context || '')
  const glossaryHit = termGlossary.find((item) => item.pattern.test(text))
  if (glossaryHit) return glossaryHit.text
  if (
    contextText &&
    contextText.length >= 8 &&
    contextText !== text &&
    !/^(技能|职位|职业|职能|行业|证书|学校|专业|学历|标签|tooltip)$/i.test(contextText)
  ) {
    return contextText
  }
  const rules = [
    [/总账|总账会计/, '负责企业整体账务核算、凭证审核、月结年结、报表出具等工作。面试时可追问是否独立负责过月结、报表和账务调整。'],
    [/税务|纳税|报税|汇算|税控/, '与企业税费申报、税务合规、发票管理和年度汇算清缴有关。可追问申报税种、异常处理和税务风险控制经验。'],
    [/成本|费用|核算/, '关注成本归集、费用分摊、成本分析和预算执行。可追问核算口径、成本差异分析和跨部门数据来源。'],
    [/凭证|账务|明细账|账簿/, '属于会计基础核算工作，体现候选人的规范性和细致程度。可追问凭证审核规则、错账更正和归档流程。'],
    [/发票|票据/, '涉及发票开具、认证、抵扣、保管和票据合规。可追问异常发票处理、进销项管理和税控系统经验。'],
    [/审计|内控|合规|风控/, '体现风险控制和流程规范能力。可追问是否配合过内外部审计、发现过哪些风险点以及如何整改。'],
    [/ERP|SAP|金蝶|用友|系统/, '代表候选人使用企业管理或财务系统的经验。可追问具体模块、数据导出、权限流程和系统切换经历。'],
    [/Excel|数据|报表|统计/, '代表数据整理、分析和报表呈现能力。可追问常用函数、透视表、数据校验和自动化处理经验。'],
    [/运营|用户|活动|转化|留存/, '属于运营岗位核心词，通常和用户增长、内容活动、数据指标有关。可追问指标口径、策略制定和复盘结果。'],
    [/项目|流程|制度|复盘/, '体现项目推进和流程化能力。可追问候选人在项目中的角色、推进难点和复盘方法。'],
    [/沟通|协调|团队|协作/, '属于软素质标签，体现跨部门配合能力。可追问冲突处理、资源协调和向上汇报案例。'],
    [/大专|本科|学历|专业|学校/, '属于教育背景标签，用来辅助判断岗位基础匹配度，不应单独作为录用结论。可结合岗位要求继续核验。'],
    [/证书|资格|职称|初级|中级|CPA|会计师/, '代表候选人具备相关资质或考试经历。可追问证书取得时间、是否实际应用到工作中。']
  ]
  const matched = rules.find(([pattern]) => pattern.test(text) || pattern.test(categoryText) || pattern.test(contextText))
  if (matched) return matched[1]
  if (categoryText.includes('技能')) return `“${text}”是简历中的技能词。当前本地词典暂未收录它的固定科普解释，可以点击“继续问 AI”生成更具体说明。面试时先确认它是什么工具/方法、用来解决什么问题、候选人是否真的上手做过。`
  if (categoryText.includes('职业') || categoryText.includes('职位') || categoryText.includes('职能')) return `“${text}”是职业/职能相关标签，用于判断候选人与目标岗位的匹配度。建议追问职责边界、汇报对象和关键成果。`
  return `“${text}”是简历解析出的标签。当前本地词典暂未收录它的固定科普解释，可以点击“继续问 AI”让模型解释它是什么、通常用来做什么，以及和当前岗位有什么关系。`
}

async function askAiForTerm() {
  if (!termCard.value.term || termCard.value.loading) return
  termCard.value.loading = true
  termCard.value.aiAnswer = ''
  try {
    const response = await fetch('/api/explain-term', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        term: termCard.value.term,
        category: termCard.value.category,
        context: termCard.value.context,
        force_ai: true,
        resume: {
          name: profile.value.name,
          position: profile.value.position,
          workYear: profile.value.workYear,
          degree: profile.value.degree,
          major: profile.value.major,
          skills: skills.value.slice(0, 20),
          experiences: experiences.value.slice(0, 3)
        }
      })
    })
    if (!response.ok) throw new Error(await response.text())
    const data = await response.json()
    termCard.value.aiAnswer = data.explanation || 'AI 暂未返回更详细解释。'
  } catch (error) {
    termCard.value.aiAnswer = `AI解释失败：${error.message}`
  } finally {
    termCard.value.loading = false
  }
}

const profile = computed(() => ({
  name: valueByKeys('name'),
  gender: valueByKeys('gender'),
  age: valueByKeys('age'),
  phone: valueByKeys('phone'),
  email: valueByKeys('email'),
  location: valueByKeys('location', 'city', 'city_norm') || 'XX市',
  position: valueByKeys('work_position', 'current_position', 'expect_job'),
  college: valueByKeys('college'),
  degree: valueByKeys('degree'),
  major: valueByKeys('major'),
  schoolType: valueByKeys('college_type', 'school_type'),
  graduationTime: valueByKeys('graduation_time', 'graduate_time'),
  workYear: valueByKeys('work_year_norm', 'work_year'),
  workStartTime: valueByKeys('work_start_time'),
  workStartTimeInferred: valueByKeys('work_start_time_inferred'),
  workPosType: valueByKeys('work_pos_type_p'),
  workCompany: valueByKeys('work_company', 'current_company'),
  expectJob: valueByKeys('expect_job', 'expected_job'),
  expectSalary: valueByKeys('expect_salary'),
  expectSalaryMin: valueByKeys('expect_salary_min'),
  expectSalaryMax: valueByKeys('expect_salary_max'),
  expectLocation: valueByKeys('expect_jlocation'),
  expectLocationNorm: valueByKeys('expect_jlocation_norm', 'desired_location'),
  resumeType: valueByKeys('resume_type', 'language') || '中文',
  integrity: valueByKeys('resume_integrity'),
  parsedAt: valueByKeys('parsed_at'),
  summary: valueByKeys('summary', 'cont_my_desc')
}))

const profileInitial = computed(() => String(profile.value.name || '候').slice(0, 1))

const avatarSrc = computed(() => {
  const avatar = valueByKeys('avatar_data', 'avatar_url')
  if (!avatar) return ''
  const text = String(avatar)
  if (text.startsWith('data:image') || text.startsWith('http')) return text
  return `data:image/jpeg;base64,${text}`
})

const education = computed(() => asArray(resumeData.value.education || raw.value.education_objs).map((item) => ({
  school: item.school || item.edu_college || profile.value.college,
  major: item.major || item.edu_major || profile.value.major,
  degree: item.degree || item.edu_degree_norm || item.edu_degree || profile.value.degree,
  schoolType: item.schoolType || item.school_type || profile.value.schoolType,
  duration: item.duration || [item.start_date, item.end_date].filter(Boolean).join('~') || profile.value.graduationTime
})).filter((item) => item.school || item.major || item.degree))

const experiences = computed(() => asArray(resumeData.value.experiences || resumeData.value.work_experience || raw.value.job_exp_objs).map((item) => ({
  company: item.company || item.job_cpy || '',
  position: item.position || item.title || item.job_position || '',
  positionType: item.positionType || item.job_position_type || item.job_pos_type || profile.value.workPosType,
  industry: item.industry || item.job_industry || '',
  duration: durationText(item),
  description: item.description || item.job_content || ''
})).filter((item) => item.company || item.position || item.description))

const projects = computed(() => asArray(resumeData.value.projects || raw.value.proj_exp_objs).map((item) => ({
  name: item.name || item.proj_name || '',
  company: item.company || item.proj_cpy || '',
  position: item.position || item.proj_position || '',
  duration: item.duration || [item.start_date, item.end_date].filter(Boolean).join('~'),
  description: item.description || item.proj_content || '',
  responsibility: item.responsibility || item.proj_resp || ''
})).filter((item) => item.name || item.description || item.responsibility))

const skills = computed(() => {
  const normalized = asArray(resumeData.value.skills)
  const fromObjects = asArray(resumeData.value.skills_objs || raw.value.skills_objs).map((item) => {
    if (typeof item === 'string') return item
    return item.skills_name || item.name || item.text || ''
  })
  return uniq([...normalized, ...fromObjects]).slice(0, 90)
})

const skillDisplayGroups = computed(() => groupSkills(skills.value))

const certificates = computed(() => uniq([
  ...asArray(resumeData.value.certificates),
  ...asArray(raw.value.all_cert_objs).map((item) => typeof item === 'string' ? item : item.cert_name),
  ...asArray(resumeData.value.certificate_text)
]).slice(0, 24))

const certificateText = computed(() => certificates.value.length ? certificates.value.join('、') : '未识别')

const basicRows = computed(() => [
  [
    { label: '姓名', value: profile.value.name },
    { label: '性别', value: profile.value.gender }
  ],
  [
    { label: '年龄', value: profile.value.age },
    { label: '工作年限(规范化)', value: profile.value.workYear }
  ],
  [
    { label: '毕业时间', value: profile.value.graduationTime },
    { label: '毕业学校', value: profile.value.college }
  ],
  [
    { label: '毕业学校类型', value: profile.value.schoolType },
    { label: '所学专业', value: profile.value.major }
  ],
  [
    { label: '学历', value: profile.value.degree },
    { label: '参加工作时间', value: profile.value.workStartTime }
  ],
  [
    { label: '参加工作时间(推断)', value: profile.value.workStartTimeInferred },
    { label: '当前职位', value: profile.value.position }
  ],
  [
    { label: '当前职能类型', value: profile.value.workPosType },
    { label: '当前单位', value: profile.value.workCompany }
  ]
])

const expectRows = computed(() => [
  { label: '期望职位', value: profile.value.expectJob },
  { label: '期望薪资', value: profile.value.expectSalary },
  { label: '期望月薪(下限)', value: profile.value.expectSalaryMin },
  { label: '期望月薪(上限)', value: profile.value.expectSalaryMax },
  { label: '期望工作地点', value: profile.value.expectLocation },
  { label: '期望工作地点(规范化)', value: profile.value.expectLocationNorm }
])

const certificateColumns = computed(() => {
  const list = certificates.value.length ? certificates.value : ['未识别', '']
  return list.slice(0, 2)
})

const skillRows = computed(() => {
  const numbered = (skills.value.length ? skills.value : ['未识别']).map((text, index) => ({ index: index + 1, text }))
  const rows = []
  const split = Math.ceil(numbered.length / 2)
  const left = numbered.slice(0, split)
  const right = numbered.slice(split)
  for (let i = 0; i < split; i += 1) {
    rows.push({ key: `skill-${i}`, left: left[i], right: right[i] })
  }
  return rows
})

const salaryBadge = computed(() => {
  if (profilerSource.value.salaryBadge) return String(profilerSource.value.salaryBadge)
  const salary = profile.value.expectSalary || [profile.value.expectSalaryMin, profile.value.expectSalaryMax].filter(Boolean).join('-')
  if (!salary) return ''
  const text = String(salary).replace(/元\/月|\/月|月/g, '')
  return text.includes('K') ? text : `${text}`
})

const highlightBadges = computed(() => {
  if (Array.isArray(profilerSource.value.highlightBadges) && profilerSource.value.highlightBadges.length) {
    return profilerSource.value.highlightBadges.map(String)
  }
  const badges = []
  if (experiences.value.length >= 1) badges.push('工作稳定')
  if (skills.value.length >= 5) badges.push('技能丰富')
  return badges.length ? badges : ['已解析']
})

const riskBadges = computed(() => {
  if (Array.isArray(profilerSource.value.riskBadges) && profilerSource.value.riskBadges.length) {
    return profilerSource.value.riskBadges.map(String)
  }
  const badges = []
  if (String(profile.value.schoolType || profile.value.degree).includes('专') || String(profile.value.schoolType).includes('职业')) badges.push('职业教育')
  if (!experiences.value.length) badges.push('经历缺失')
  if (!profile.value.phone && !profile.value.email) badges.push('联系方式缺失')
  return badges
})

const highlightItems = computed(() => {
  const apiItems = profilerItems('highlights')
  if (apiItems.length) return apiItems
  const items = []
  const avgMonths = Math.max(12, Math.round((numberIn(profile.value.workYear) * 12 || experiences.value.length * 18) / Math.max(experiences.value.length, 1)))
  if (experiences.value.length) {
    items.push(`${hi('工作稳定')}：平均每段工作经历持续${hi(avgMonths)}个月，且存在${hi(Math.max(1, experiences.value.length))}段工作经历；`)
  }
  if (profile.value.position || profile.value.workPosType) {
    items.push(`在${hi(profile.value.position || profile.value.workPosType)}职能领域里有${hi(experiences.value.length >= 2 ? '较丰富' : '相关')}工作经历；`)
  }
  if (skills.value.length) {
    items.push(`${hi(skills.value.length >= 12 ? '很丰富' : '较丰富')}的${hi(skills.value[0])}经验：在${escapeHtml(skills.value.slice(0, 26).join('、'))}等技能上有深入的理解；`)
  }
  if (certificates.value.length) {
    items.push(`持有${hi(certificates.value.slice(0, 4).join('、'))}等证书或资质；`)
  }
  return items.length ? items : ['简历已完成结构化解析；']
})

const riskItems = computed(() => {
  const apiItems = profilerItems('risks')
  if (apiItems.length) return apiItems
  const items = []
  if (riskBadges.value.includes('职业教育')) items.push(`毕业于${hi(profile.value.schoolType || profile.value.degree, 'warning')}院校；`)
  if (!profile.value.workStartTime && profile.value.graduationTime) items.push(`参加工作时间未完整识别，需核验是否存在${hi('空档期', 'warning')}；`)
  if (!experiences.value.length) items.push(`${hi('工作经历', 'warning')}未识别，需核对简历原文；`)
  if (!profile.value.phone && !profile.value.email) items.push(`${hi('联系方式', 'warning')}未识别；`)
  return items.length ? items : ['暂无明显风险信息；']
})

const assessmentLine = computed(() => {
  const assessment = profilerSource.value.assessment
  if (assessment?.html) return String(assessment.html)
  if (assessment?.text) return escapeHtml(assessment.text)
  const salary = salaryBadge.value || '未识别'
  return `综合工作经历、教育背景、工作年限、行业地域等因素，该候选人的市场薪资约为 <span class="mytext-info underline font-weight-bold">${escapeHtml(salary)}</span> /月；`
})

const basicTagGroups = computed(() => {
  const apiGroups = tagGroupsByCategory('基本标签')
  if (apiGroups.length) return apiGroups
  return [{
    label: '基本',
    items: [
      profile.value.gender && { text: profile.value.gender, tooltip: 'gender' },
      profile.value.age && { text: `${ageBucket(profile.value.age)}岁`, tooltip: 'age' },
      profile.value.workYear && { text: `${experienceBucket(profile.value.workYear)}经验`, tooltip: 'experience' },
      salaryBadge.value && { text: `期望${salaryBadge.value}`, tooltip: 'expect_salary' }
    ].filter(Boolean)
  }]
})

const educationTagGroups = computed(() => {
  const apiGroups = tagGroupsByCategory('教育标签')
  if (apiGroups.length) return apiGroups
  return [
    { label: '基本', items: [profile.value.degree && { text: `${profile.value.degree}学历`, tooltip: '学历标签' }].filter(Boolean) },
    { label: '专业', items: [profile.value.major && { text: `${profile.value.major}专业`, tooltip: '专业标签' }].filter(Boolean) },
    { label: '学校', items: [profile.value.college && { text: profile.value.college, tooltip: '学校标签' }].filter(Boolean) }
  ].filter((group) => group.items.length)
})

const careerTagGroups = computed(() => {
  const apiGroups = tagGroupsByCategory('职业标签')
  if (apiGroups.length) return apiGroups
  return [
    {
      label: '职位',
      items: uniq([profile.value.position, profile.value.expectJob, ...experiences.value.map((item) => item.position)])
        .slice(0, 8)
        .map((text) => ({ text, tooltip: '职位标签' }))
    },
    {
      label: '职能',
      items: uniq([profile.value.workPosType, ...experiences.value.map((item) => item.positionType)])
        .slice(0, 8)
        .map((text) => ({ text, tooltip: '职能类型标签' }))
    },
    {
      label: '行业',
      items: uniq(experiences.value.map((item) => item.industry)).slice(0, 8).map((text) => ({ text, tooltip: '行业标签' }))
    }
  ].filter((group) => group.items.length)
})

const otherTagGroups = computed(() => {
  const apiGroups = tagGroupsByCategory('其他标签')
  if (apiGroups.length) return apiGroups
  return [
    { label: '证书', items: certificates.value.slice(0, 12).map((text) => ({ text, tooltip: '证书' })) }
  ].filter((group) => group.items.length)
})

const skillTagGroups = computed(() => {
  const apiGroups = tagGroupsByCategory('技能标签')
  if (apiGroups.length) return apiGroups
  return [
    { label: '软素质', items: softSkills.value.map((text) => ({ text, tooltip: '软素质' })) },
    { label: '技能', items: skills.value.slice(0, 48).map((text) => ({ text, tooltip: '技能' })) }
  ].filter((group) => group.items.length)
})

const profileTagCategories = computed(() => [
  {
    category: '基本标签',
    iconClass: 'mytext-warning',
    badgeColor: 'primary',
    subs: basicTagGroups.value
  },
  {
    category: '教育标签',
    iconClass: 'text-success',
    badgeColor: 'success',
    subs: educationTagGroups.value
  },
  {
    category: '职业标签',
    iconClass: 'mytext-info',
    badgeColor: 'info',
    subs: careerTagGroups.value
  },
  {
    category: '其他标签',
    iconClass: 'mytext-warning',
    badgeColor: 'warning',
    subs: otherTagGroups.value
  },
  {
    category: '技能标签',
    iconClass: 'mytext-danger',
    badgeColor: 'danger',
    subs: skillTagGroups.value
  }
].filter((item) => item.subs.length))

const softSkills = computed(() => {
  const text = `${profile.value.summary} ${skills.value.join(' ')}`
  const candidates = ['责任心强', '良好的沟通', '协调能力', '团队协作', '严谨细致', '学习能力']
  const found = candidates.filter((item) => text.includes(item.replace('良好的', '')))
  return found.length ? found : candidates.slice(0, 4)
})

const abilityScores = computed(() => {
  const evalScores = evalData.value?.capacity || evalData.value?.ability || evalData.value?.abilities || {}
  const fromEval = [
    ['教育背景', evalScores.edu || evalScores.education || evalData.value.edu_score],
    ['工作能力', evalScores.work || evalScores.work_ability || evalData.value.work_score],
    ['管理能力', evalScores.manage || evalScores.management || evalData.value.management_score],
    ['社会能力', evalScores.social || evalData.value.social_score],
    ['语言能力', evalScores.language || evalData.value.language_score],
    ['荣誉指数', evalScores.honor || evalData.value.honor_score]
  ].map(([label, value]) => ({ label, value: normalizeChartValue(value, 0) }))
    .filter((item) => item.value > 0)
  if (fromEval.length >= 4) return fromEval

  return [
    { label: '教育背景', value: safeScore(profile.value.degree ? 62 + (profile.value.schoolType ? 5 : 0) : 35) },
    { label: '工作能力', value: safeScore(55 + numberIn(profile.value.workYear) * 4 + Math.min(skills.value.length, 16)) },
    { label: '管理能力', value: safeScore(45 + (allProfileText.value.includes('管理') ? 18 : 0) + numberIn(profile.value.workYear) * 2) },
    { label: '社会能力', value: safeScore(52 + experiences.value.length * 8) },
    { label: '语言能力', value: safeScore(45 + asArray(resumeData.value.languages).length * 15) },
    { label: '荣誉指数', value: safeScore(45 + certificates.value.length * 10) }
  ]
})

const industryScores = computed(() => {
  const fromTags = weightedTagItems('industries').slice(0, 11).map((item) => ({
    label: item.label,
    value: normalizeChartValue(item.weight, 40)
  }))
  if (fromTags.length >= 3) return fromTags

  return [
    { label: '物流/运输', value: safeScore(40 + keywordWeight('物流|运输|供应链')) },
    { label: '专业服务/教育/培训', value: safeScore(42 + keywordWeight('专业服务|咨询|教育|培训|财会')) },
    { label: '计算机/互联网/通信/电子', value: safeScore(46 + keywordWeight('平台|运营|互联网|数据|电子')) },
    { label: '政府/非营利组织/其他', value: safeScore(35 + keywordWeight('行政|政府|公益')) },
    { label: '广告/媒体', value: safeScore(35 + keywordWeight('广告|媒体|内容')) },
    { label: '能源/环保/化工', value: safeScore(35 + keywordWeight('能源|环保|化工')) },
    { label: '房地产/建筑', value: safeScore(35 + keywordWeight('房地产|建筑')) },
    { label: '贸易/消费/制造/营运', value: safeScore(42 + keywordWeight('贸易|消费|制造|营运|运营')) },
    { label: '制药/医疗', value: safeScore(38 + keywordWeight('医药|医疗')) },
    { label: '会计/金融/银行/保险', value: safeScore(42 + keywordWeight('会计|财务|税务|金融|银行|保险')) },
    { label: '服务业', value: safeScore(42 + keywordWeight('服务')) }
  ]
})

const secondaryIndustrySegments = computed(() => {
  const fromTags = weightedTagItems('industries').slice(0, 5)
  if (fromTags.length) return toSegments(fromTags)
  return toSegments([
    { label: '计算机软件', weight: keywordWeight('软件|平台|数据') || 7 },
    { label: '专业服务', weight: keywordWeight('专业服务|财会|咨询') || 7 },
    { label: '交通/运输/物流', weight: keywordWeight('交通|运输|物流|供应链') || 7 }
  ])
})

const jobFunctionSegments = computed(() => {
  const fromTags = weightedTagItems('pos_types').slice(0, 5)
  if (fromTags.length) return toSegments(fromTags)
  const position = profile.value.position || '当前职位'
  const type = profile.value.workPosType || '职能类型'
  return toSegments([
    { label: position, weight: Math.max(6, numberIn(profile.value.workYear) * 5 || 12) },
    { label: type, weight: Math.max(4, experiences.value.length * 6 || 8) },
    { label: profile.value.expectJob || '期望职位', weight: Math.max(3, Math.min(skills.value.length, 12)) },
    { label: '待核验', weight: Math.max(2, riskItems.value.length * 3) }
  ])
})

const allProfileText = computed(() => [
  profile.value.position,
  profile.value.workPosType,
  profile.value.workCompany,
  profile.value.summary,
  skills.value.join(' '),
  experiences.value.map((item) => `${item.company} ${item.position} ${item.positionType} ${item.industry} ${item.description}`).join(' ')
].join(' '))

function ageBucket(age) {
  const value = numberIn(age)
  if (!value) return valueOr(age)
  const low = Math.floor(value / 5) * 5
  return `${low}-${low + 5}`
}

function experienceBucket(years) {
  const value = numberIn(years)
  if (!value) return valueOr(years)
  if (value >= 10) return '10年以上'
  if (value >= 5) return '5-10年'
  if (value >= 3) return '3-5年'
  return `${value}年`
}

function keywordWeight(pattern) {
  const regex = new RegExp(pattern, 'g')
  const matches = allProfileText.value.match(regex)
  return matches ? Math.min(matches.length * 8, 55) : 0
}

function profilerItems(key) {
  const section = profilerSource.value?.[key]
  if (!section) return []
  if (Array.isArray(section)) return section.map((item) => String(item))
  if (Array.isArray(section.items)) {
    return section.items.map((item) => {
      if (typeof item === 'string') return item
      return item.html || item.text || item.content || item.label || ''
    }).filter(Boolean).map(String)
  }
  return []
}

function tagGroupsByCategory(category) {
  const tags = profilerSource.value?.tags
  if (!Array.isArray(tags)) return []
  const matched = tags.find((item) => item?.category === category)
  if (!matched) return []
  const subs = Array.isArray(matched.subs) ? matched.subs : []
  return subs.map((sub) => ({
    label: sub.label || sub.name || '',
    items: asArray(sub.items).map((item) => {
      if (typeof item === 'string') return { text: item, tooltip: item }
      return {
        text: item.text || item.label || item.name || '',
        tooltip: item.tooltip || item.title || item.text || item.label || ''
      }
    }).filter((item) => item.text)
  })).filter((group) => group.items.length)
}

const chartPalette = ['#5b75d6', '#82c66f', '#f8c64d', '#ef5b65', '#7c69ef', '#42ba96', '#f59e0b']

function weightedTagItems(key) {
  const list = tagsData.value?.[key]
  if (!Array.isArray(list)) return []
  return list.map((item) => ({
    label: item.tag_name || item.name || item.label || '',
    weight: item.tag_weight ?? item.weight ?? item.value ?? 0
  })).filter((item) => item.label && Number(item.weight) > 0)
}

function normalizeChartValue(value, fallback = 35) {
  const number = Number(value)
  if (!Number.isFinite(number) || number <= 0) return fallback
  return safeScore(number <= 1 ? number * 100 : number)
}

function toSegments(items) {
  return items.map((item, index) => ({
    label: item.label,
    value: Math.max(1, Math.round(Number(item.weight) <= 1 ? Number(item.weight) * 100 : Number(item.weight))),
    color: item.color || chartPalette[index % chartPalette.length]
  })).filter((item) => item.label && item.value > 0)
}

function makeRadar(items) {
  const center = 120
  const radius = 86
  const pointsAt = (scale) => items.map((_, index) => radarPoint(index, items.length, radius * scale, center))
  return {
    grid: [0.25, 0.5, 0.75, 1].map((scale) => pointsAt(scale).map(pointText).join(' ')),
    axes: items.map((item, index) => {
      const point = radarPoint(index, items.length, radius, center)
      const label = radarPoint(index, items.length, radius + 28, center)
      return { ...point, labelX: label.x, labelY: label.y + 4, label: item.label, labelLines: splitChartLabel(item.label) }
    }),
    area: items.map((item, index) => pointText(radarPoint(index, items.length, radius * (item.value / 100), center))).join(' '),
    points: items.map((item, index) => radarPoint(index, items.length, radius * (item.value / 100), center))
  }
}

function splitChartLabel(label) {
  const text = String(label || '')
  if (text.length <= 7) return [text]
  const chunks = []
  let current = ''
  for (const char of text) {
    current += char
    if (current.length >= 6 || '/、'.includes(char)) {
      chunks.push(current)
      current = ''
    }
  }
  if (current) chunks.push(current)
  return chunks.slice(0, 3)
}

function radarPoint(index, total, radius, center) {
  const angle = -Math.PI / 2 + (Math.PI * 2 * index) / total
  return {
    x: Number((center + Math.cos(angle) * radius).toFixed(2)),
    y: Number((center + Math.sin(angle) * radius).toFixed(2))
  }
}

function pointText(point) {
  return `${point.x},${point.y}`
}

function buildArcSegments(segments, half = false) {
  const cleaned = segments.filter((item) => item && Number(item.value) > 0)
  const total = cleaned.reduce((sum, item) => sum + Number(item.value), 0) || 1
  const center = { x: 180, y: half ? 170 : 140 }
  const radius = half ? 104 : 92
  const totalAngle = half ? 180 : 360
  const startBase = half ? 270 : 0
  const gap = cleaned.length > 1 ? (half ? 3 : 2) : 0
  let cursor = 0
  return cleaned.map((item) => {
    const span = (Number(item.value) / total) * totalAngle
    const start = startBase + cursor + gap / 2
    const end = startBase + cursor + Math.max(span - gap / 2, span * 0.72)
    cursor += span
    return {
      ...item,
      path: describeArc(center.x, center.y, radius, start, end)
    }
  })
}

function describeArc(cx, cy, radius, startAngle, endAngle) {
  const start = polarToCartesian(cx, cy, radius, endAngle)
  const end = polarToCartesian(cx, cy, radius, startAngle)
  const largeArcFlag = endAngle - startAngle <= 180 ? 0 : 1
  return `M ${start.x} ${start.y} A ${radius} ${radius} 0 ${largeArcFlag} 0 ${end.x} ${end.y}`
}

function polarToCartesian(cx, cy, radius, angle) {
  const radians = (angle - 90) * Math.PI / 180
  return {
    x: Number((cx + radius * Math.cos(radians)).toFixed(2)),
    y: Number((cy + radius * Math.sin(radians)).toFixed(2))
  }
}
</script>

<style scoped>
.rsdk-backdrop {
  align-items: center;
  background: rgba(15, 23, 42, 0.58);
  bottom: 0;
  display: flex;
  justify-content: center;
  left: 0;
  overflow: hidden;
  padding: 24px;
  position: fixed;
  right: 0;
  top: 0;
  z-index: 60;
}

.resume-modal {
  background: #fff;
  border: 1px solid rgba(148, 163, 184, 0.28);
  border-radius: 14px;
  box-shadow: 0 24px 80px rgba(15, 23, 42, 0.28);
  color: #2b3548;
  display: flex;
  flex-direction: column;
  font-family: Arial, "Microsoft YaHei", "PingFang SC", sans-serif;
  max-height: min(92vh, 1080px);
  max-width: min(1080px, calc(100vw - 48px));
  overflow: hidden;
  width: 100%;
}

.resume-modal-header {
  align-items: center;
  border-bottom: 1px solid #e2e8f0;
  display: flex;
  flex: 0 0 auto;
  justify-content: space-between;
  padding: 16px 20px;
}

.resume-modal-header p {
  color: #64748b;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0;
  margin: 0 0 4px;
}

.resume-modal-header h2 {
  color: #172033;
  font-size: 18px;
  line-height: 1.25;
  margin: 0;
}

.resume-modal-header h2 span {
  color: #64748b;
  font-size: 14px;
  font-weight: 600;
  margin-left: 8px;
}

.close-btn {
  align-items: center;
  background: #fff;
  border: 1px solid #dbe4f0;
  border-radius: 8px;
  color: #475569;
  cursor: pointer;
  display: inline-flex;
  font-size: 24px;
  height: 36px;
  justify-content: center;
  padding: 0;
  width: 36px;
}

.close-btn:hover {
  background: #f8fafc;
  color: #0f172a;
}

.resume-modal-body {
  background: #f8fafc;
  flex: 1 1 auto;
  overflow: auto;
  padding: 24px 0 42px;
}

.rsdk-container {
  margin: 0 auto;
  max-width: 940px;
}

.mycard {
  background: #fff;
  border: 1px solid #d9e0ea;
  border-radius: 4px;
  margin-bottom: 48px;
  overflow: hidden;
}

.mycard-header {
  border-bottom: 1px solid #e2e7ef;
  padding: 16px 28px 14px;
}

.mybg-white {
  background: #fff;
}

.header-grid {
  align-items: flex-start;
  display: grid;
  gap: 18px;
  grid-template-columns: 1fr 96px;
}

.text-center {
  text-align: center;
}

.candidate-title {
  color: #2b3548;
  font-family: Georgia, "Times New Roman", "Microsoft YaHei", serif;
  font-size: 24px;
  line-height: 1.25;
  margin: 0 0 6px;
}

.candidate-title span {
  color: #5f6b7f;
  font-weight: 300;
  margin-left: 10px;
}

.candidate-title small {
  font-size: 18px;
}

.badge-line,
.profile-line {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  justify-content: center;
  margin-top: 4px;
}

.profile-line {
  color: #2f3b50;
  gap: 14px;
}

.r_small {
  font-size: 13px;
  line-height: 1.7;
}

.r_small_70 {
  color: #2b3548;
  font-size: 13px;
}

.header-avatar {
  min-height: 112px;
}

.header_img,
.avatar-placeholder {
  border: 1px solid #dde4ef;
  height: 112px;
  object-fit: cover;
  width: 92px;
}

.avatar-placeholder {
  align-items: center;
  background: #eef4ff;
  color: #2f63f2;
  display: flex;
  font-size: 34px;
  font-weight: 900;
  justify-content: center;
}

.mycard-body {
  padding: 22px 24px 46px;
}

.nav-pills {
  display: flex;
  gap: 8px;
  list-style: none;
  margin: 0 0 20px;
  padding: 0;
}

.nav-link {
  background: #fff;
  border: 0;
  border-radius: 4px;
  color: #1677ff;
  cursor: pointer;
  font-size: 15px;
  padding: 11px 18px;
}

.nav-link.active {
  background: #1677ff;
  color: #fff;
}

.w-100 {
  border-collapse: collapse;
  table-layout: fixed;
  width: 100%;
}

.parser-table {
  font-size: 90%;
}

td {
  vertical-align: top;
}

.row-bordered {
  border-bottom: 1px solid #cfd8e3;
  color: #263449;
  font-family: Georgia, "Times New Roman", "Microsoft YaHei", serif;
  font-size: 18px;
  margin: 15px 0 10px;
  padding-bottom: 7px;
}

.font-weight-bold {
  font-weight: 800;
}

.section-triangle {
  color: #1677ff;
  font-size: 15px;
  margin-right: 8px;
}

.r_content {
  color: #2f3b50;
  font-size: 14px;
  line-height: 1.75;
  margin: 2px 0 2px 18px;
  overflow-wrap: anywhere;
  padding-left: 14px;
  position: relative;
  white-space: pre-wrap;
}

.r_content::before {
  background: #1677ff;
  border-radius: 50%;
  content: "";
  height: 5px;
  left: 0;
  position: absolute;
  top: 10px;
  width: 5px;
}

.mytext-muted {
  color: #617189;
}

.mytext-primary {
  color: #1677ff;
}

.mytext-warning {
  color: #f6a800;
}

.mytext-info {
  color: #0ea5e9;
}

.mytext-success {
  color: #22a954;
}

.mytext-danger {
  color: #e3324e;
}

.underline {
  text-decoration: underline;
}

.work-desc {
  padding-bottom: 14px;
}

.free-text {
  color: #2f3b50;
  font-size: 14px;
  line-height: 1.9;
  margin: 0 0 0 36px;
  overflow-wrap: anywhere;
  white-space: pre-wrap;
}

.mybadge {
  border-radius: 3px;
  color: #fff;
  display: inline-flex;
  font-size: 12px;
  font-weight: 800;
  line-height: 1;
  margin: 2px 2px;
  padding: 4px 7px;
  vertical-align: middle;
}

.mybadge-pill {
  border-radius: 999px;
  min-width: 18px;
  justify-content: center;
}

.mybadge-primary {
  background: #1677ff;
}

.mybadge-info {
  background: #0ea5e9;
}

.mybadge-warning {
  background: #f6b500;
  color: #1f2937;
}

.mybadge-success {
  background: #22a954;
}

.mybadge-danger {
  background: #e3324e;
}

.profiler-line {
  align-items: flex-start;
  display: flex;
  gap: 8px;
  margin: 6px 0 6px 32px;
}

.r_circle {
  border-radius: 50%;
  display: inline-flex;
  flex: 0 0 auto;
  height: 6px;
  margin-top: 9px;
  width: 6px;
}

.mybg-primary {
  background: #1677ff;
}

.mybg-warning {
  background: #f6b500;
}

.mybg-info {
  background: #0ea5e9;
}

.mybg-success {
  background: #22a954;
}

.mybg-danger {
  background: #e3324e;
}

h6 {
  color: #263449;
  font-size: 14px;
  margin: 10px 0 6px;
}

.mt-3 {
  margin-top: 18px;
}

.tag-block {
  margin-top: 14px;
}

.tag-title {
  margin-left: 18px;
}

.tag-title-icon {
  margin-right: 8px;
}

.tag-line {
  align-items: flex-start;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 7px 0 7px 32px;
}

.tag-line-label {
  align-items: center;
  display: inline-flex;
  flex: 0 0 92px;
  gap: 5px;
  line-height: 26px;
}

.tag-line-label em {
  background: #eef1f5;
  border-radius: 999px;
  color: #8695a8;
  font-size: 11px;
  font-style: normal;
  min-width: 20px;
  padding: 1px 6px;
  text-align: center;
}

.tag-badges {
  display: flex;
  flex: 1 1 0;
  flex-wrap: wrap;
  gap: 6px;
  max-height: 156px;
  min-width: 0;
  overflow: auto;
  padding-right: 4px;
}

.chart-title {
  color: #596579;
  font-family: Georgia, "Times New Roman", "Microsoft YaHei", serif;
  font-size: 18px;
  font-weight: 500;
  margin: 45px 0 0;
  text-align: center;
}

.chart-cell {
  text-align: center;
}

.rsdk-radar {
  height: 360px;
  max-width: 540px;
  width: 100%;
}

.radar-grid,
.radar-axis {
  fill: none;
  stroke: #e3eaf4;
  stroke-width: 1;
}

.radar-area {
  fill: rgba(91, 117, 214, 0.2);
  stroke: #5b75d6;
  stroke-width: 2;
}

.radar-area.industry {
  fill: rgba(91, 117, 214, 0.18);
}

.radar-dot {
  fill: #5b75d6;
}

.radar-label {
  fill: #a8b2c2;
  font-size: 11px;
}

.donut-wrap {
  align-items: center;
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin: 16px auto 20px;
  min-height: 320px;
}

.donut-chart {
  align-items: center;
  border-radius: 50%;
  display: flex;
  height: 245px;
  justify-content: center;
  position: relative;
  width: 245px;
}

.donut-chart::after {
  background: #fff;
  border-radius: 50%;
  content: "";
  height: 128px;
  position: absolute;
  width: 128px;
}

.donut-chart span {
  color: #7a8799;
  font-size: 13px;
  font-weight: 800;
  position: relative;
  z-index: 1;
}

.donut-chart.half {
  clip-path: inset(0 0 48% 0);
  margin-bottom: -70px;
}

.legend-row {
  color: #657287;
  display: flex;
  flex-wrap: wrap;
  font-size: 12px;
  gap: 14px;
  justify-content: center;
  max-width: 650px;
}

.legend-row i {
  border-radius: 2px;
  display: inline-block;
  height: 10px;
  margin-right: 5px;
  width: 20px;
}

@media (max-width: 760px) {
  .rsdk-backdrop {
    align-items: stretch;
    padding: 10px;
  }

  .resume-modal {
    border-radius: 10px;
    max-height: calc(100vh - 20px);
    max-width: none;
  }

  .rsdk-container {
    padding: 0 10px;
  }

  .header-grid {
    grid-template-columns: 1fr;
    justify-items: center;
  }

  .mycard-body {
    padding: 18px 12px 36px;
  }

  .r_content {
    margin-left: 4px;
  }

  .free-text {
    margin-left: 18px;
  }

  .rsdk-radar {
    height: 300px;
  }
}
.resume-popup-shell {
  background: #f5f7fb;
  border: 1px solid rgba(226, 232, 240, 0.9);
  border-radius: 18px;
  box-shadow: 0 24px 80px rgba(15, 23, 42, 0.28);
  max-height: min(92vh, 1080px);
  max-width: min(1040px, calc(100vw - 48px));
  overflow: hidden;
  position: relative;
  width: 100%;
}

.popup-close-btn {
  align-items: center;
  background: #fff;
  border: 1px solid #dbe4f0;
  border-radius: 50%;
  box-shadow: 0 8px 18px rgba(15, 23, 42, 0.14);
  color: #475569;
  cursor: pointer;
  display: inline-flex;
  font-size: 24px;
  height: 34px;
  justify-content: center;
  line-height: 1;
  padding: 0;
  position: absolute;
  right: 18px;
  top: 18px;
  width: 34px;
  z-index: 5;
}

.popup-close-btn:hover {
  background: #f8fafc;
  color: #0f172a;
}

.resume-analysis-popup {
  background: #f5f7fb;
  max-height: min(92vh, 1080px);
  overflow: auto;
}

.main-container {
  margin: 0 auto;
  max-width: 960px;
  padding: 32px 20px 60px;
  transition: margin-right 0.3s ease, transform 0.3s ease;
}

.profile-header-section {
  background: #fff;
  border: 1px solid #eef1f5;
  border-radius: 16px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
  margin-bottom: 20px;
  padding: 28px 32px;
}

.profile-main {
  align-items: flex-start;
  display: flex;
  gap: 24px;
}

.avatar-section .avatar,
.avatar-section .avatar-img {
  border-radius: 50%;
  height: 88px;
  width: 88px;
}

.avatar-section .avatar {
  align-items: center;
  background: linear-gradient(135deg, #335eea 0%, #1a3fa0 100%);
  box-shadow: 0 4px 12px rgba(51, 94, 234, 0.25);
  color: #fff;
  display: flex;
  font-size: 36px;
  font-weight: 600;
  justify-content: center;
}

.avatar-section .avatar-img {
  border: 3px solid #eef1f5;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
  object-fit: cover;
}

.profile-info {
  flex: 1;
  min-width: 0;
}

.name-position {
  align-items: center;
  display: flex;
  gap: 12px;
  margin-bottom: 12px;
}

.name-position .name {
  color: #1a2332;
  font-family: Arial, "Microsoft YaHei", "PingFang SC", sans-serif;
  font-size: 26px;
  font-weight: 700;
  letter-spacing: 1px;
  line-height: 1.25;
  margin: 0;
}

.position-tag {
  background: rgba(51, 94, 234, 0.08);
  border: 1px solid rgba(51, 94, 234, 0.15);
  border-radius: 20px;
  color: #335eea;
  font-size: 13px;
  font-weight: 500;
  padding: 4px 14px;
}

.badges-row,
.basic-info-row,
.contact-row {
  display: flex;
  flex-wrap: wrap;
}

.badges-row {
  gap: 8px;
  margin-bottom: 14px;
}

.basic-info-row,
.contact-row {
  gap: 20px;
  margin-bottom: 6px;
}

.info-item {
  align-items: center;
  color: #5a6a7e;
  display: flex;
  font-size: 13px;
  gap: 6px;
  line-height: 1.6;
}

.info-icon {
  color: #9aabbf;
  font-size: 14px;
}

.tabs-section {
  background: #fff;
  border: 1px solid #eef1f5;
  border-radius: 16px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
  overflow: hidden;
}

.tabs-nav {
  background: #fafbfc;
  border-bottom: 1px solid #eef1f5;
  display: flex;
}

.tab-item {
  align-items: center;
  background: transparent;
  border: 0;
  border-bottom: 2px solid transparent;
  color: #5a6a7e;
  cursor: pointer;
  display: flex;
  flex: 1 1 0;
  font-size: 14px;
  font-weight: 600;
  gap: 8px;
  justify-content: center;
  margin-bottom: -1px;
  padding: 14px 28px;
  transition: all 0.2s;
}

.tab-item:hover {
  background: rgba(51, 94, 234, 0.03);
  color: #335eea;
}

.tab-item.active {
  background: rgba(51, 94, 234, 0.04);
  border-bottom-color: #335eea;
  color: #335eea;
}

.tab-icon,
.section-icon {
  display: inline-flex;
  font-size: 16px;
  line-height: 1;
}

.tab-content {
  padding: 24px 28px;
}

.content-section {
  margin-bottom: 20px;
}

.content-section:last-child {
  margin-bottom: 0;
}

.section-header {
  align-items: center;
  color: #1a2332;
  display: flex;
  font-size: 15px;
  font-weight: 600;
  gap: 8px;
  margin-bottom: 16px;
  padding-bottom: 10px;
}

.section-icon {
  color: #335eea;
}

.row-bordered {
  border-bottom: 1px solid #e9ecef;
  color: #495057;
  font-family: Arial, "Microsoft YaHei", "PingFang SC", sans-serif;
  font-size: 15px;
  font-weight: 600;
  margin: 0 0 16px;
  padding-bottom: 8px;
}

.table-layout {
  border-collapse: collapse;
  table-layout: auto;
  width: 100%;
}

.table-layout td {
  border-bottom: 1px solid #e9ecef;
  color: #1a2332;
  font-size: 14px;
  line-height: 1.6;
  padding: 8px 12px;
  vertical-align: top;
}

.table-layout tr:last-child td {
  border-bottom: 0;
}

.table-layout td.mytext-muted {
  color: #6c757d;
  white-space: nowrap;
  width: 120px;
}

.work-table td {
  border-bottom: 0;
  padding: 5px 12px;
}

.salary-highlight {
  color: #df4759;
  font-weight: 700;
}

.description-text {
  color: #5a6a7e;
  font-size: 14px;
  line-height: 1.7;
  overflow-wrap: anywhere;
  white-space: pre-wrap;
}

.timeline-lite-item {
  margin-bottom: 16px;
}

.timeline-lite-line {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 8px;
}

.period-text {
  margin-left: auto;
}

.empty-hint {
  color: #9aabbf;
  font-size: 13px;
  font-style: italic;
  padding: 8px 0;
}

.skills-panel {
  border-left: 2px solid #e9ecef;
  margin-left: 16px;
  padding-left: 12px;
}

.skills-summary {
  align-items: center;
  color: #6c757d;
  display: flex;
  flex-wrap: wrap;
  font-size: 13px;
  gap: 10px;
  margin-bottom: 12px;
}

.skills-summary span {
  background: #f8f9fb;
  border: 1px solid #eef1f5;
  border-radius: 999px;
  padding: 4px 10px;
}

.skill-group-list {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.skill-group-card {
  background: #fafbfc;
  border: 1px solid #eef1f5;
  border-radius: 10px;
  min-width: 0;
  padding: 12px;
}

.skill-group-head {
  align-items: center;
  color: #1a2332;
  display: flex;
  font-size: 13px;
  font-weight: 700;
  justify-content: space-between;
  margin-bottom: 9px;
}

.skill-group-head b {
  background: rgba(124, 105, 239, 0.1);
  border-radius: 999px;
  color: #5a4abd;
  font-size: 12px;
  min-width: 24px;
  padding: 2px 8px;
  text-align: center;
}

.skill-chip-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
}

.skill-chip {
  background: #fff;
  border: 1px solid rgba(124, 105, 239, 0.18);
  border-radius: 7px;
  color: #4f46a5;
  display: inline-flex;
  font-size: 12px;
  line-height: 1.35;
  max-width: 100%;
  overflow-wrap: anywhere;
  padding: 5px 9px;
  word-break: break-word;
}

.term-trigger {
  cursor: help;
  position: relative;
  transition: box-shadow 0.18s ease, transform 0.18s ease;
}

.term-trigger:hover {
  box-shadow: 0 0 0 3px rgba(51, 94, 234, 0.12);
  transform: translateY(-1px);
}

.term-card {
  background: rgba(255, 255, 255, 0.98);
  border: 1px solid #dbe5f3;
  border-radius: 10px;
  box-shadow: 0 18px 42px rgba(20, 32, 54, 0.18);
  color: #1a2332;
  max-width: 340px;
  padding: 12px;
  position: fixed;
  width: min(340px, calc(100vw - 32px));
  z-index: 10020;
}

.term-card.pinned {
  border-color: #335eea;
}

.term-card-head {
  align-items: flex-start;
  display: flex;
  gap: 10px;
  justify-content: space-between;
  margin-bottom: 8px;
}

.term-card-head span {
  color: #64748b;
  display: block;
  font-size: 12px;
  font-weight: 800;
  margin-bottom: 3px;
}

.term-card-head strong {
  color: #173b8f;
  display: block;
  font-size: 15px;
  line-height: 1.35;
}

.term-card-head button {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 50%;
  color: #64748b;
  cursor: pointer;
  flex: 0 0 auto;
  height: 24px;
  line-height: 1;
  width: 24px;
}

.term-card p,
.term-ai-answer {
  color: #475569;
  font-size: 13px;
  line-height: 1.65;
  margin: 0;
  white-space: pre-wrap;
}

.term-ai-answer {
  background: #f6fffa;
  border: 1px solid #cdeedc;
  border-radius: 8px;
  margin-top: 9px;
  padding: 9px;
}

.term-ai-btn {
  background: #335eea;
  border: 0;
  border-radius: 7px;
  color: #fff;
  cursor: pointer;
  font-size: 12px;
  font-weight: 800;
  margin-top: 10px;
  padding: 7px 10px;
}

.term-ai-btn:disabled {
  cursor: default;
  opacity: 0.72;
}

.mybadge {
  align-items: center;
  border-radius: 6px;
  display: inline-flex;
  font-size: 13px;
  font-weight: 500;
  gap: 4px;
  line-height: 1.4;
  margin: 2px 4px 2px 0;
  max-width: 100%;
  overflow-wrap: anywhere;
  padding: 5px 14px;
  white-space: normal;
  word-break: break-word;
}

.mybadge.mybadge-primary {
  background: rgba(51, 94, 234, 0.1);
  border: 1px solid rgba(51, 94, 234, 0.2);
  color: #335eea;
}

.mybadge.mybadge-success {
  background: rgba(66, 186, 150, 0.1);
  border: 1px solid rgba(66, 186, 150, 0.2);
  color: #2a8e6e;
}

.mybadge.mybadge-warning {
  background: rgba(245, 158, 11, 0.1);
  border: 1px solid rgba(245, 158, 11, 0.2);
  color: #b8860b;
}

.mybadge.mybadge-info {
  background: rgba(124, 105, 239, 0.1);
  border: 1px solid rgba(124, 105, 239, 0.2);
  color: #5a4abd;
}

.mybadge.mybadge-danger {
  background: rgba(223, 71, 89, 0.1);
  border: 1px solid rgba(223, 71, 89, 0.2);
  color: #c0392b;
}

.mybadge-pill {
  border-radius: 50px;
  font-size: 12px;
  min-height: 20px;
  padding: 1px 8px;
}

.mytext-primary {
  color: #335eea !important;
}

.mytext-muted {
  color: #6c757d !important;
}

.mytext-warning {
  color: #f59e0b !important;
}

.mytext-info {
  color: #7c69ef !important;
}

.mytext-danger {
  color: #c0392b !important;
}

.mytext-success,
.text-success {
  color: #42ba96 !important;
}

.r_content {
  border-left: 2px solid #e9ecef;
  color: #1a2332;
  font-size: 14px;
  line-height: 1.7;
  margin-left: 16px;
  overflow-wrap: anywhere;
  padding-left: 8px;
  white-space: normal;
}

.r_content::before {
  display: none;
}

.r_circle {
  border-radius: 50%;
  display: inline-block;
  flex-shrink: 0;
  height: 8px;
  margin: -2px 8px 0 0;
  vertical-align: middle;
  width: 8px;
}

.r_circle.mybg-primary,
.mybg-primary {
  background-color: #1d4ed8 !important;
}

.r_circle.mybg-warning,
.mybg-warning {
  background-color: #d97706 !important;
}

.r_circle.mybg-info,
.mybg-info {
  background-color: #6d28d9 !important;
}

.r_circle.mybg-success,
.mybg-success {
  background-color: #047857 !important;
}

.r_circle.mybg-danger,
.mybg-danger {
  background-color: #b91c1c !important;
}

.r_small {
  color: #6c757d;
  font-size: 14px;
  line-height: 1.7;
}

.r_small_70 {
  color: #6c757d;
  font-size: 13px;
  font-weight: 500;
  margin-right: 4px;
}

.profiler-line {
  align-items: flex-start;
  display: flex;
  gap: 2px;
  margin: 4px 0 4px 24px;
}

h6 {
  color: #1a2332;
  font-size: 14px;
  font-weight: 600;
  margin: 10px 0 6px;
}

.headline-icon {
  display: inline-flex;
  margin: 0 8px 0 12px;
}

.tag-block {
  background: #fafbfc;
  border: 1px solid #eef1f5;
  border-radius: 12px;
  margin-top: 14px;
  padding: 14px 16px 16px;
}

.tag-title {
  align-items: center;
  border-bottom: 1px solid #eef1f5;
  color: #1a2332;
  display: flex;
  font-size: 14px;
  font-weight: 700;
  gap: 8px;
  justify-content: flex-start;
  margin: 0 0 12px;
  padding-bottom: 10px;
}

.tag-title > em {
  background: #eef1f5;
  border-radius: 999px;
  color: #8695a8;
  font-size: 12px;
  font-style: normal;
  margin-left: auto;
  min-width: 28px;
  padding: 2px 8px;
  text-align: center;
}

.tag-title-icon {
  font-size: 14px;
}

.tag-group-grid {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.tag-line {
  align-items: flex-start;
  background: #fff;
  border: 1px solid #eef1f5;
  border-radius: 10px;
  display: grid;
  gap: 8px;
  grid-template-columns: 8px minmax(72px, 90px) minmax(0, 1fr);
  margin: 0;
  min-width: 0;
  padding: 10px 12px;
}

.tag-line .r_circle {
  margin-top: 8px;
}

.tag-line-label {
  align-items: center;
  color: #5a6a7e;
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  line-height: 24px;
}

.tag-line-label em {
  background: #f0f2f5;
  border-radius: 999px;
  color: #8695a8;
  font-size: 11px;
  font-style: normal;
  min-width: 20px;
  padding: 1px 6px;
  text-align: center;
}

.tag-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  min-width: 0;
}

.mybadge-more {
  background: #f1f5f9 !important;
  border: 1px solid #dbe4ef !important;
  color: #64748b !important;
  font-weight: 700;
}

.chart-container {
  height: 360px;
  margin: 0 auto;
  max-width: 540px;
  width: 100%;
}

.chart-container.pie-space {
  height: auto;
  min-height: 340px;
}

.chart-title {
  color: #596579;
  font-family: Arial, "Microsoft YaHei", "PingFang SC", sans-serif;
  font-size: 16px;
  font-weight: 500;
  margin: 22px 0 10px;
  text-align: center;
}

.profiler-reference-table {
  border-collapse: collapse;
  font-size: 90%;
  table-layout: auto;
  width: 100%;
}

.profiler-reference-table td {
  padding: 4px 8px;
  vertical-align: top;
}

.profiler-reference-table .row-bordered {
  border-bottom: 1px solid #e9ecef;
  color: #495057;
  font-size: 18px;
  margin: 15px 0 10px;
  padding-bottom: 8px;
}

.profiler-reference-table h5 {
  margin-bottom: 0;
}

.profiler-reference-table h6 {
  color: #1a2332;
  font-size: 14px;
  font-weight: 600;
  margin: 10px 0 6px;
}

.profiler-tag-row {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  line-height: 1.8;
}

.profiler-tag-row .mybadge {
  border-radius: 4px;
  font-size: 12px;
  line-height: 1.25;
  margin: 1px 2px;
  padding: 4px 8px;
}

.text-center {
  text-align: center;
}

.rsdk-radar {
  height: 100%;
  width: 100%;
}

.radar-grid,
.radar-axis {
  fill: none;
  stroke: rgba(51, 94, 234, 0.15);
  stroke-width: 1;
}

.radar-area {
  fill: rgba(51, 94, 234, 0.25);
  stroke: #335eea;
  stroke-width: 2;
}

.radar-area.industry {
  fill: rgba(66, 186, 150, 0.2);
  stroke: #42ba96;
}

.radar-dot {
  fill: #335eea;
}

.radar-label {
  fill: #4a5568;
  font-size: 11px;
}

.donut-wrap {
  align-items: center;
  display: flex;
  flex-direction: column;
  gap: 16px;
  justify-content: center;
  min-height: 320px;
}

.donut-wrap.half-wrap {
  min-height: 260px;
}

.donut-svg {
  display: block;
  height: 300px;
  margin: 0 auto;
  max-width: 360px;
  overflow: visible;
  width: 100%;
}

.donut-svg.half {
  height: 225px;
}

.donut-center {
  fill: #7a8799;
  font-size: 13px;
  font-weight: 600;
}

.donut-chart {
  align-items: center;
  border-radius: 50%;
  display: flex;
  height: 245px;
  justify-content: center;
  position: relative;
  width: 245px;
}

.donut-chart::after {
  background: #fff;
  border-radius: 50%;
  content: "";
  height: 128px;
  position: absolute;
  width: 128px;
}

.donut-chart span {
  color: #7a8799;
  font-size: 13px;
  font-weight: 600;
  position: relative;
  z-index: 1;
}

.donut-chart.half {
  clip-path: inset(0 0 48% 0);
  margin-bottom: -70px;
}

.legend-row {
  color: #657287;
  display: flex;
  flex-wrap: wrap;
  font-size: 12px;
  gap: 14px;
  justify-content: center;
  max-width: 650px;
}

.legend-row i {
  border-radius: 2px;
  display: inline-block;
  height: 10px;
  margin-right: 5px;
  width: 20px;
}

.ml-4 {
  margin-left: 1.5rem !important;
}

.mb-2 {
  margin-bottom: 0.5rem !important;
}

.mt-3 {
  margin-top: 1rem !important;
}

.mx-2 {
  margin-left: 0.5rem !important;
  margin-right: 0.5rem !important;
}

.r_indent2 {
  margin-left: 32px;
}

.fw-bold,
.font-weight-bold {
  font-weight: 700 !important;
}

.fw-medium {
  font-weight: 500 !important;
}

@media (max-width: 768px) {
  .rsdk-backdrop {
    align-items: stretch;
    padding: 10px;
  }

  .resume-popup-shell,
  .resume-analysis-popup {
    border-radius: 12px;
    max-height: calc(100vh - 20px);
    max-width: none;
  }

  .main-container {
    padding: 16px;
  }

  .profile-header-section {
    padding: 20px;
  }

  .profile-main {
    align-items: center;
    flex-direction: column;
    text-align: center;
  }

  .name-position {
    flex-direction: column;
  }

  .basic-info-row,
  .contact-row {
    justify-content: center;
  }

  .tab-item {
    font-size: 13px;
    padding: 12px 18px;
  }

  .tab-content {
    padding: 16px;
  }

  .table-layout {
    table-layout: fixed;
  }

  .table-layout td {
    padding: 7px 8px;
    word-break: break-word;
  }

  .table-layout td.mytext-muted {
    width: auto;
  }

  .skill-group-list {
    grid-template-columns: 1fr;
  }

  .tag-group-grid {
    grid-template-columns: 1fr;
  }

  .tag-line {
    grid-template-columns: 8px 1fr;
    margin-left: 0;
  }

  .tag-line-label {
    grid-column: 2;
  }

  .tag-badges {
    grid-column: 1 / -1;
  }

  .period-text {
    margin-left: 0;
    width: 100%;
  }
}
</style>
