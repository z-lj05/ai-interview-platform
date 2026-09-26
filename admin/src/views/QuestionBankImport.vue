<template>
  <div>
    <div class="page-header">
      <h1>📥 批量导入题目</h1>
      <router-link to="/question-bank"><button class="btn-secondary">← 返回题库</button></router-link>
    </div>

    <!-- ── 方式一：上传文件（后端切题）────────────────────────────── -->
    <div class="card">
      <h2 class="card-title">方式一：上传文件（推荐）</h2>
      <div class="hint">
        <p><b>支持格式</b>：PDF / DOCX / MD / TXT。后端按文档长相选切题规则——
          <b>问句式</b>（题面 = 以问号结尾的短行）／<b>标题式</b>（题面 = <code>### </code> 标题行；
          Word 的「标题 1/2/3」样式会当成同样的标记）</p>
        <p><b>两步走</b>：先「解析预览」看清切出多少题、长什么样，确认无误再「确认导入」。
          预览不写库，切错了不会有残留。</p>
      </div>

      <div class="file-row">
        <input ref="fileInput" type="file" accept=".pdf,.docx,.md,.markdown,.txt" @change="onPickFile" />
        <span v-if="file" class="file-name">{{ file.name }}</span>
      </div>

      <div class="param-row">
        <label>分类
          <select v-model="params.category">
            <option value="technical">技术</option>
            <option value="behavioral">行为</option>
            <option value="system_design">系统设计</option>
            <option value="project">项目</option>
          </select>
        </label>
        <label>岗位
          <select v-model="params.position_tag">
            <option value="python_backend">Python 后端</option>
            <option value="java_backend">Java 后端</option>
            <option value="vue_frontend">Vue 前端</option>
            <option value="react_frontend">React 前端</option>
            <option value="fullstack">全栈</option>
          </select>
        </label>
        <label>难度
          <select v-model="params.difficulty">
            <option value="easy">简单</option>
            <option value="medium">中等</option>
            <option value="hard">困难</option>
          </select>
        </label>
        <label>来源标记
          <input v-model="params.source" placeholder="file-import" />
        </label>
      </div>

      <div class="actions">
        <button class="btn-primary" @click="parsePreview" :disabled="!file || parsing">
          {{ parsing ? '解析中…' : '解析预览' }}
        </button>
        <button class="btn-secondary" @click="resetFile" :disabled="parsing">清空</button>
      </div>

      <!-- 预览结果 -->
      <div v-if="preview" class="preview-box">
        <div class="preview-head">
          <span class="badge badge-green">切出 {{ preview.count }} 题</span>
          <span class="meta">切题方式：{{ preview.strategy }}</span>
          <span class="meta">平均答案 {{ preview.stats.avg_answer_len }} 字 · 最长 {{ preview.stats.max_answer_len }} 字</span>
          <span v-if="preview.stats.empty_answer" class="meta warn-text">
            {{ preview.stats.empty_answer }} 题没切到答案
          </span>
        </div>

        <div v-if="preview.warn" class="alert-warn">⚠️ {{ preview.warn }}</div>

        <div class="samples">
          <div class="samples-title">题目样例（首 5 题 + 末题）</div>
          <ol>
            <li v-for="(q, i) in preview.preview.head" :key="i">{{ q }}</li>
          </ol>
          <div v-if="preview.preview.tail" class="tail">
            <span class="tail-tag">末题</span>{{ preview.preview.tail }}
          </div>
        </div>

        <div class="actions">
          <button class="btn-primary" @click="confirmImport"
                  :disabled="importing || preview.count === 0 || preview.count > 500">
            {{ importing ? '导入中…' : `确认导入 ${preview.count} 条` }}
          </button>
          <span class="meta">导入后自动提交后台向量化任务，稍等几秒再检索</span>
        </div>
      </div>

      <div v-if="imported !== null" class="result-box">
        <span class="badge badge-green">导入成功</span>
        <span>共 {{ imported }} 条，向量化任务已提交</span>
      </div>
    </div>

    <!-- ── 方式二：粘贴 JSON（原样保留）───────────────────────────── -->
    <div class="card">
      <h2 class="card-title">方式二：粘贴 / 上传 JSON</h2>
      <div class="hint">
        <p><b>导入格式</b>：JSON 数组，每个元素含字段 <code>category / position_tag / difficulty / question / reference_answer / key_points / tags</code></p>
        <p><b>说明</b>：导入后题目会先入库（embedding 为 NULL），再由后台 Celery 异步批量向量化。</p>
      </div>

      <div style="display:flex;gap:12px;margin-bottom:14px">
        <input type="file" accept=".json" @change="loadFile" />
        <button class="btn-secondary" @click="loadSample">加载示例数据</button>
      </div>

      <div class="form-item">
        <label>JSON 内容（可直接粘贴或上传文件后预览）</label>
        <textarea v-model="jsonText" rows="20" spellcheck="false"></textarea>
      </div>

      <div class="actions">
        <button class="btn-primary" @click="submit" :disabled="loading">
          {{ loading ? '导入中...' : `导入 ${parseCount} 条` }}
        </button>
        <button class="btn-secondary" @click="jsonText = ''">清空</button>
      </div>

      <div v-if="result" class="result-box">
        <span class="badge badge-green">导入成功</span>
        <span>共 {{ result.inserted_count }} 条，向量化任务已提交</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { questionBankApi } from '../api'

// ── 方式一：文件导入 ─────────────────────────────────────────────
const fileInput = ref(null)
const file = ref(null)
const parsing = ref(false)
const preview = ref(null)
const importing = ref(false)
const imported = ref(null)

const params = ref({
  category: 'technical',
  position_tag: 'python_backend',
  difficulty: 'medium',
  source: 'file-import'
})

function onPickFile(e) {
  file.value = e.target.files?.[0] || null
  preview.value = null      // 换文件就作废旧预览：防止拿 A 的预览导 B 的题
  imported.value = null
}

function resetFile() {
  file.value = null
  preview.value = null
  imported.value = null
  if (fileInput.value) fileInput.value.value = ''   // 清掉原生 input 的文件名显示
}

async function parsePreview() {
  if (!file.value) return
  parsing.value = true
  preview.value = null
  imported.value = null
  try {
    const fd = new FormData()
    fd.append('file', file.value)
    fd.append('category', params.value.category)
    fd.append('position_tag', params.value.position_tag)
    fd.append('difficulty', params.value.difficulty)
    fd.append('source', params.value.source)
    preview.value = await questionBankApi.parseFile(fd)
  } catch (e) {
    alert('解析失败: ' + e.message)
  } finally {
    parsing.value = false
  }
}

async function confirmImport() {
  if (!preview.value?.items?.length) return
  importing.value = true
  try {
    // 原样打给老的批量导入端点：解析和落库共用同一个落库口，前端不做二次加工
    const res = await questionBankApi.batchImport(preview.value.items)
    // 导入成功才清场：失败时保留预览，用户能重试而不用重新解析一遍
    file.value = null
    preview.value = null
    if (fileInput.value) fileInput.value.value = ''
    imported.value = res.inserted_count
  } catch (e) {
    alert('导入失败: ' + e.message)
  } finally {
    importing.value = false
  }
}

// ── 方式二：JSON 粘贴 ────────────────────────────────────────────
const jsonText = ref('')
const loading = ref(false)
const result = ref(null)

const parseCount = computed(() => {
  try {
    const arr = JSON.parse(jsonText.value)
    return Array.isArray(arr) ? arr.length : 0
  } catch { return 0 }
})

function loadFile(e) {
  const f = e.target.files?.[0]
  if (!f) return
  const reader = new FileReader()
  reader.onload = ev => { jsonText.value = ev.target.result }
  reader.readAsText(f)
}

function loadSample() {
  const sample = [
    {
      category: 'technical',
      position_tag: 'python_backend',
      difficulty: 'medium',
      question: '请解释 Python 中的 GIL（全局解释器锁）机制及其影响',
      reference_answer: 'GIL 是 CPython 解释器中的一个互斥锁，保证同一时刻只有一个线程执行 Python 字节码。这导致多线程在 CPU 密集型任务中无法真正并行，但 IO 密集型任务影响较小。绕过 GIL 的方式包括使用 multiprocessing、C 扩展释放 GIL、或改用 Jython/PyPy。',
      key_points: ['GIL 是互斥锁', '同一时刻一个线程执行字节码', 'CPU 密集多进程 IO 密集多线程', '原因是引用计数线程安全'],
      tags: ['GIL', '并发', 'Python']
    },
    {
      category: 'technical',
      position_tag: 'python_backend',
      difficulty: 'hard',
      question: '深入说明 asyncio 的事件循环原理，以及 async/await 是如何工作的',
      reference_answer: 'asyncio 基于事件循环（Event Loop）+ 协程（Coroutine）。async 函数调用返回协程对象，await 处会挂起当前协程并把控制权交回事件循环。事件循环不断从就绪队列取协程恢复执行，遇到 IO 等待时挂起、IO 完成后回到就绪队列。底层用 selector 监听 fd 事件，单线程实现高并发 IO。',
      key_points: ['事件循环驱动', 'await 让出控制权', '协程是可暂停的函数', 'selector 监听 IO 事件', '单线程高并发'],
      tags: ['asyncio', '协程', 'Python']
    }
  ]
  jsonText.value = JSON.stringify(sample, null, 2)
}

async function submit() {
  let items
  try {
    items = JSON.parse(jsonText.value)
  } catch (e) { alert('JSON 格式错误：' + e.message); return }

  if (!Array.isArray(items) || !items.length) { alert('请提供非空的 JSON 数组'); return }

  loading.value = true
  result.value = null
  try {
    result.value = await questionBankApi.batchImport(items)
  } catch (e) { alert('导入失败: ' + e.message) }
  finally { loading.value = false }
}
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.page-header h1 { font-size: 20px; }
.btn-secondary { background: #e5e7eb; color: #374151; padding: 8px 14px; }

.card { margin-bottom: 20px; }
.card-title { font-size: 15px; font-weight: 600; margin-bottom: 12px; color: #111827; }

.hint { background: #eff6ff; color: #1e40af; padding: 12px 16px; border-radius: 6px; margin-bottom: 16px; font-size: 13px; line-height: 1.7; }
.hint code { background: white; padding: 1px 6px; border-radius: 3px; font-family: monospace; }
.hint p { margin: 4px 0; }

.file-row { display: flex; align-items: center; gap: 12px; margin-bottom: 14px; }
.file-name { font-size: 13px; color: #374151; }

.param-row { display: flex; flex-wrap: wrap; gap: 16px; margin-bottom: 4px; }
.param-row label { display: flex; flex-direction: column; gap: 6px; font-size: 13px; color: #374151; font-weight: 500; }
.param-row input { width: 160px; font-size: 13px; }

.form-item label { display: block; font-size: 13px; color: #374151; margin-bottom: 6px; font-weight: 500; }
.form-item textarea { width: 100%; padding: 10px 12px; border: 1px solid #d1d5db; border-radius: 6px; font-size: 13px; font-family: 'Consolas', monospace; resize: vertical; }
.form-item textarea:focus { border-color: #4f46e5; outline: none; }

.actions { display: flex; align-items: center; gap: 8px; margin-top: 14px; }
.result-box { margin-top: 16px; padding: 12px 16px; background: #f0fdf4; border-radius: 6px; display: flex; align-items: center; gap: 10px; }

/* 预览区 */
.preview-box { margin-top: 18px; padding: 16px; background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 8px; }
.preview-head { display: flex; flex-wrap: wrap; align-items: center; gap: 14px; margin-bottom: 12px; }
.meta { font-size: 13px; color: #6b7280; }
.warn-text { color: #b45309; }

.alert-warn { background: #fffbeb; border-left: 3px solid #f59e0b; color: #92400e; padding: 10px 14px; border-radius: 4px; font-size: 13px; margin-bottom: 12px; }

.samples { background: white; border: 1px solid #e5e7eb; border-radius: 6px; padding: 12px 16px; }
.samples-title { font-size: 13px; font-weight: 600; color: #374151; margin-bottom: 8px; }
.samples ol { margin: 0; padding-left: 20px; }
.samples li { font-size: 13px; color: #374151; line-height: 1.9; }
.tail { margin-top: 10px; padding-top: 10px; border-top: 1px dashed #e5e7eb; font-size: 13px; color: #374151; }
.tail-tag { display: inline-block; background: #e0e7ff; color: #4338ca; font-size: 11px; padding: 1px 7px; border-radius: 3px; margin-right: 8px; }
</style>
