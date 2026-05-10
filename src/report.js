function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function formatVerdict(value) {
  if (value === true) return '回答合理'
  if (value === false) return '存在风险'
  return '无法判定'
}

function renderList(items) {
  if (!items || items.length === 0) return '<p class="muted">暂无</p>'
  return `<ol>${items.map((item) => `<li>${escapeHtml(item)}</li>`).join('')}</ol>`
}

function renderResume(resume) {
  if (!resume) return '<p class="muted">未导入简历</p>'
  const rows = [
    ['姓名', resume.name],
    ['电话', resume.phone],
    ['邮箱', resume.email]
  ].filter(([, value]) => value)

  return `
    <dl class="meta-grid">
      ${rows.map(([label, value]) => `<dt>${label}</dt><dd>${escapeHtml(value)}</dd>`).join('')}
    </dl>
  `
}

function renderTranscript(finals) {
  if (!finals || finals.length === 0) {
    return '<p class="muted">暂无转写内容</p>'
  }
  return finals.map((item, index) => `
    <article class="entry">
      <div class="entry-meta">#${index + 1} · ${escapeHtml(item.time || '')}</div>
      <p>${escapeHtml(item.text)}</p>
    </article>
  `).join('')
}

function renderAnalyses(analyses, messages) {
  if (analyses && analyses.length > 0) {
    return analyses.map((item, index) => `
      <article class="entry">
        <div class="entry-meta">#${index + 1} · ${escapeHtml(item.time || '')} · ${formatVerdict(item.is_correct)}</div>
        <p>${escapeHtml(item.analysis)}</p>
        <h3>存疑点</h3>
        ${renderList(item.doubts)}
        <h3>建议追问</h3>
        ${renderList(item.questions)}
      </article>
    `).join('')
  }

  const aiMessages = (messages || []).filter((message) => message.type === 'ai')
  if (aiMessages.length === 0) return '<p class="muted">暂无 AI 评估内容</p>'
  return aiMessages.map((message, index) => `
    <article class="entry">
      <div class="entry-meta">#${index + 1} · ${escapeHtml(message.time || '')}</div>
      <p>${escapeHtml(message.content)}</p>
    </article>
  `).join('')
}

export function openInterviewReport(snapshot) {
  const title = `HireFlow 面试报告 ${snapshot.endedAtText || ''}`.trim()
  const reportWindow = window.open('', '_blank', 'noopener,noreferrer,width=980,height=1200')
  if (!reportWindow) {
    throw new Error('浏览器阻止了报告窗口，请允许弹窗后重试。')
  }

  const html = `<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <title>${escapeHtml(title)}</title>
  <style>
    * { box-sizing: border-box; }
    body {
      color: #111827;
      font-family: "Microsoft YaHei", "PingFang SC", Arial, sans-serif;
      line-height: 1.7;
      margin: 0;
      padding: 32px;
    }
    h1 { font-size: 26px; margin: 0 0 8px; }
    h2 {
      border-bottom: 1px solid #d7deeb;
      font-size: 18px;
      margin: 28px 0 14px;
      padding-bottom: 8px;
    }
    h3 { font-size: 14px; margin: 14px 0 6px; }
    p { margin: 0; white-space: pre-wrap; }
    ol { margin: 6px 0 0 20px; padding: 0; }
    .summary {
      color: #4b5567;
      display: flex;
      flex-wrap: wrap;
      gap: 10px 18px;
      margin-bottom: 18px;
    }
    .summary span {
      background: #f3f6fb;
      border: 1px solid #e2e8f0;
      border-radius: 6px;
      padding: 4px 8px;
    }
    .meta-grid {
      display: grid;
      grid-template-columns: 90px 1fr;
      margin: 0;
      row-gap: 6px;
    }
    .meta-grid dt { color: #647086; font-weight: 700; }
    .meta-grid dd { margin: 0; }
    .entry {
      break-inside: avoid;
      border: 1px solid #e5eaf2;
      border-radius: 8px;
      margin-bottom: 12px;
      padding: 12px 14px;
    }
    .entry-meta {
      color: #647086;
      font-size: 12px;
      font-weight: 700;
      margin-bottom: 6px;
    }
    .muted { color: #8a94a8; }
    @page { margin: 18mm; }
    @media print {
      body { padding: 0; }
      .entry { border-color: #d7deeb; }
    }
  </style>
</head>
<body>
  <h1>HireFlow AI 面试报告</h1>
  <div class="summary">
    <span>面试官：${escapeHtml(snapshot.interviewer || '李明')}</span>
    <span>岗位：${escapeHtml(snapshot.jobTitle || '运营专员（平台运营方向）')}</span>
    <span>开始：${escapeHtml(snapshot.startedAtText || '')}</span>
    <span>结束：${escapeHtml(snapshot.endedAtText || '')}</span>
    <span>时长：${escapeHtml(snapshot.elapsedTime || '')}</span>
  </div>

  <h2>候选人简历</h2>
  ${renderResume(snapshot.resume)}

  <h2>全程转写</h2>
  ${renderTranscript(snapshot.finals)}

  <h2>AI 评估</h2>
  ${renderAnalyses(snapshot.analyses, snapshot.messages)}
</body>
</html>`

  reportWindow.document.open()
  reportWindow.document.write(html)
  reportWindow.document.close()
  reportWindow.focus()
  window.setTimeout(() => reportWindow.print(), 350)
}
