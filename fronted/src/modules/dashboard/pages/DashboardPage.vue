<script setup lang="ts">
import {
  ArrowRight,
  DataAnalysis,
  Files,
  Location,
  RefreshRight,
} from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onMounted, ref } from 'vue'

import { featureFlags } from '@/config/feature-flags'
import { getErrorMessage } from '@/core/http/error-normalizer'
import { authenticateWithWebAuthn } from '@/modules/auth/services/webauthn'
import { useAuthStore } from '@/modules/auth/stores/auth.store'
import { fetchRagOverview } from '@/modules/document-generation/api/document-generation.api'
import type {
  KnowledgeCorpusUploadStatus,
  RagOperations,
  RagOverview,
  RagSectionCoverage,
} from '@/modules/document-generation/document-generation.types'
import {
  createLocationReportChallenge,
  fetchAdminLatestLocations,
  fetchMyLatestLocation,
  reportLocation,
} from '@/modules/locations/api/locations.api'
import PersonnelLocationMap from '@/modules/locations/components/PersonnelLocationMap.vue'
import type { LocationReportPayload, LocationSnapshot } from '@/modules/locations/locations.types'
import { locateCurrentUser } from '@/modules/locations/services/location-provider'
import {
  getAttentionLocations,
  getLocationDisplayAddress,
  getLocationStatusLabel,
  getLocationStatusTagType,
} from '@/modules/locations/utils/location-status'
import { formatDateTime } from '@/shared/utils/format'
import { fetchDashboardCounts } from '../api/dashboard.api'

interface StatusItem {
  label: string
  value: string
}

const authStore = useAuthStore()
const isSystemAdmin = computed(() => authStore.isSystemAdmin)
const ragEnabled = featureFlags.documentAgent

const statusItems = ref<StatusItem[]>([
  { label: '可见资料', value: '--' },
  { label: '我的项目', value: '--' },
  { label: '未读通知', value: '--' },
  { label: '活跃授权', value: '--' },
])

const loading = ref(false)
const locationLoading = ref(false)
const reportLoading = ref(false)
const myLocation = ref<LocationSnapshot | null>(null)
const personnelLoading = ref(false)
const personnelError = ref('')
const personnelLocations = ref<LocationSnapshot[]>([])
const ragLoading = ref(false)
const ragError = ref('')
const ragOverview = ref<RagOverview | null>(null)

const attentionLocations = computed(() => getAttentionLocations(personnelLocations.value))
const normalLocationCount = computed(
  () => personnelLocations.value.filter((snapshot) => snapshot.location_status === 'normal').length,
)
const maxSectionChunks = computed(
  () => Math.max(1, ...(ragOverview.value?.section_coverage.map((item) => item.chunk_count) ?? [1])),
)

onMounted(async () => {
  const tasks: Array<Promise<void>> = [
    loadDashboardCounts(),
    loadMyLocation(true),
  ]
  if (ragEnabled) {
    tasks.push(loadRagOverview())
  }
  if (isSystemAdmin.value) {
    tasks.push(loadPersonnelLocations())
  }
  await Promise.all(tasks)
})

async function loadDashboardCounts(): Promise<void> {
  loading.value = true
  try {
    const counts = await fetchDashboardCounts()
    statusItems.value = [
      { label: '可见资料', value: String(counts.visibleDocuments) },
      { label: '我的项目', value: String(counts.myProjects) },
      { label: '未读通知', value: String(counts.unreadNotifications) },
      { label: '活跃授权', value: String(counts.activeGrants) },
    ]
  } catch {
    // 请求失败时保持默认的 -- 占位
  } finally {
    loading.value = false
  }
}

async function loadMyLocation(showPrompt: boolean): Promise<void> {
  locationLoading.value = true
  try {
    myLocation.value = await fetchMyLatestLocation()
    if (showPrompt && myLocation.value.should_report) {
      void promptLocationReport()
    }
  } catch {
    // 首页概览不因位置状态接口失败阻断。
  } finally {
    locationLoading.value = false
  }
}

async function loadPersonnelLocations(): Promise<void> {
  personnelLoading.value = true
  personnelError.value = ''
  try {
    personnelLocations.value = await fetchAdminLatestLocations()
  } catch (error) {
    personnelError.value = getErrorMessage(error)
  } finally {
    personnelLoading.value = false
  }
}

async function loadRagOverview(): Promise<void> {
  ragLoading.value = true
  ragError.value = ''
  try {
    ragOverview.value = await fetchRagOverview()
  } catch (error) {
    ragError.value = getErrorMessage(error)
  } finally {
    ragLoading.value = false
  }
}

async function promptLocationReport(): Promise<void> {
  try {
    await ElMessageBox.confirm(
      '距离上次上报已超过 4 小时，或今天尚未成功上报当前位置。',
      '位置上报提醒',
      {
        confirmButtonText: '上报当前位置',
        cancelButtonText: '稍后处理',
        type: 'warning',
      },
    )
  } catch {
    return
  }

  await reportCurrentLocation()
}

async function reportCurrentLocation(): Promise<void> {
  reportLoading.value = true
  try {
    const result = await locateCurrentUser()
    if (!result.ok) {
      if (result.shouldReportFailure) {
        await submitLocationFailure(result.message)
      } else {
        ElMessage.warning(result.message)
      }
      return
    }

    await submitVerifiedLocationReport({
      longitude: result.longitude,
      latitude: result.latitude,
      accuracy: result.accuracy,
      address: result.address,
    })
    ElMessage.success('当前位置已上报！')
    await loadMyLocation(false)
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    reportLoading.value = false
  }
}

async function submitLocationFailure(reason: string): Promise<void> {
  try {
    await submitVerifiedLocationReport({
      report_status: 'locate_failed',
      failure_reason: reason,
    })
    ElMessage.warning('定位失败，已记录本次上报结果，联系管理员或重新定位！')
    await loadMyLocation(false)
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  }
}

async function submitVerifiedLocationReport(payload: LocationReportPayload): Promise<void> {
  const challenge = await createLocationReportChallenge(payload)
  const credential = await authenticateWithWebAuthn(challenge.options)
  await reportLocation({
    ...payload,
    webauthn: {
      challenge_token: challenge.token,
      credential,
    },
  })
}

function formatAccuracy(value: string | null | undefined): string {
  return value ? `${value} 米` : '-'
}

function ragSectionWidth(section: RagSectionCoverage): string {
  if (section.chunk_count === 0) {
    return '0%'
  }
  return `${Math.max(6, (section.chunk_count / maxSectionChunks.value) * 100)}%`
}

function operationStatusLabel(operations: RagOperations): string {
  return {
    healthy: '运行正常',
    processing: '正在处理',
    attention: '需要关注',
  }[operations.status]
}

function operationStatusType(
  operations: RagOperations,
): 'success' | 'warning' | 'danger' {
  if (operations.status === 'healthy') {
    return 'success'
  }
  if (operations.status === 'processing') {
    return 'warning'
  }
  return 'danger'
}

function workerStatusLabel(status: RagOperations['worker_status']): string {
  return {
    idle: '空闲',
    busy: '处理中',
    offline: '离线',
    unknown: '未知',
  }[status]
}

function uploadStatusLabel(status: KnowledgeCorpusUploadStatus | null): string {
  if (!status) {
    return '暂无记录'
  }
  return {
    queued: '等待处理',
    processing: '正在处理',
    succeeded: '已入库',
    failed: '处理失败',
  }[status]
}
</script>

<template>
  <section class="dashboard-page">
    <div class="dashboard-page__metrics" aria-label="首页概览">
      <article
        v-for="item in statusItems"
        :key="item.label"
        class="dashboard-page__metric"
      >
        <span>{{ item.label }}</span>
        <strong>{{ loading ? '...' : item.value }}</strong>
      </article>
    </div>

    <div
      class="dashboard-location-row"
      :class="{ 'dashboard-location-row--single': !isSystemAdmin }"
    >
      <section class="dashboard-location-panel">
        <header>
          <div>
            <h2>我的位置上报</h2>
            <p>每天建议上报 2～3 次，位置仅以主动上报时间为准。</p>
          </div>
          <el-button
            :loading="reportLoading"
            type="primary"
            @click="reportCurrentLocation"
          >
            上报当前位置
          </el-button>
        </header>

        <el-skeleton v-if="locationLoading && !myLocation" :rows="4" animated />

        <el-descriptions v-else-if="myLocation" border :column="1">
          <el-descriptions-item label="位置状态">
            <el-tag :type="getLocationStatusTagType(myLocation.location_status)">
              {{ getLocationStatusLabel(myLocation.location_status) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="最近上报位置">
            {{ getLocationDisplayAddress(myLocation) }}
          </el-descriptions-item>
          <el-descriptions-item label="上报时间">
            {{ formatDateTime(myLocation.latest_report?.reported_at) }}
          </el-descriptions-item>
          <el-descriptions-item label="定位精度">
            {{ formatAccuracy(myLocation.latest_report?.accuracy) }}
          </el-descriptions-item>
          <el-descriptions-item label="上报结果">
            {{ myLocation.latest_report?.failure_reason || '已记录' }}
          </el-descriptions-item>
        </el-descriptions>
      </section>

      <article v-if="isSystemAdmin" class="dashboard-personnel-panel">
        <header>
          <div>
            <span class="dashboard-panel-kicker">
              <el-icon><Location /></el-icon>
              人员动态
            </span>
            <h2>人员位置概览</h2>
            <p>以员工最近一次主动上报位置为准。</p>
          </div>
          <el-tag type="warning" effect="light">
            {{ attentionLocations.length }} 人需关注
          </el-tag>
        </header>

        <div v-if="personnelError" class="dashboard-inline-state">
          <el-icon><Location /></el-icon>
          <strong>人员位置暂不可用</strong>
          <span>{{ personnelError }}</span>
          <el-button :icon="RefreshRight" link type="primary" @click="loadPersonnelLocations">
            重新加载
          </el-button>
        </div>

        <RouterLink
          v-else
          class="dashboard-personnel-panel__map-link"
          :to="{ name: 'admin-locations' }"
          aria-label="查看人员位置目录"
        >
          <PersonnelLocationMap
            :loading="personnelLoading"
            :snapshots="personnelLocations"
            variant="overview"
          />
          <span class="dashboard-personnel-panel__cta">
            查看人员位置
            <el-icon><ArrowRight /></el-icon>
          </span>
        </RouterLink>

        <footer>
          <span><i class="status-dot status-dot--success" />正常 {{ normalLocationCount }}</span>
          <span><i class="status-dot status-dot--warning" />需关注 {{ attentionLocations.length }}</span>
          <strong>共 {{ personnelLocations.length }} 人</strong>
        </footer>
      </article>
    </div>

    <section v-if="ragEnabled" class="dashboard-rag-panel">
      <header class="dashboard-rag-panel__header">
        <div>
          <span class="dashboard-panel-kicker">
            <el-icon><DataAnalysis /></el-icon>
            入场资料 Agent
          </span>
          <h2>RAG 知识库概览</h2>
          <p>展示当前已批准且与正式 Embedding 配置匹配的参考知识。</p>
        </div>
        <div class="dashboard-rag-panel__header-actions">
          <el-tag
            v-if="ragOverview"
            :type="ragOverview.knowledge_status === 'ready' ? 'success' : 'info'"
            effect="light"
            round
          >
            {{ ragOverview.knowledge_status === 'ready' ? '知识库已就绪' : '暂无可用知识' }}
          </el-tag>
          <RouterLink class="dashboard-text-link" :to="{ name: 'document-generation' }">
            进入入场资料 Agent
            <el-icon><ArrowRight /></el-icon>
          </RouterLink>
        </div>
      </header>

      <el-skeleton v-if="ragLoading && !ragOverview" :rows="5" animated />

      <div v-else-if="ragError" class="dashboard-inline-state dashboard-inline-state--wide">
        <el-icon><DataAnalysis /></el-icon>
        <strong>RAG 概览暂不可用</strong>
        <span>{{ ragError }}</span>
        <el-button :icon="RefreshRight" link type="primary" @click="loadRagOverview">
          重新加载
        </el-button>
      </div>

      <div
        v-else-if="ragOverview"
        class="dashboard-rag-panel__body"
        :class="{ 'dashboard-rag-panel__body--business-only': !ragOverview.operations }"
      >
        <div class="dashboard-rag-business">
          <div class="dashboard-rag-metrics">
            <article>
              <el-icon><DataAnalysis /></el-icon>
              <span>知识块</span>
              <strong>{{ ragOverview.knowledge_chunks }}</strong>
            </article>
            <article>
              <el-icon><Files /></el-icon>
              <span>源资料</span>
              <strong>{{ ragOverview.source_documents }}</strong>
            </article>
            <article>
              <el-icon><DataAnalysis /></el-icon>
              <span>章节覆盖</span>
              <strong>
                {{ ragOverview.covered_section_count }}
                <small>/ {{ ragOverview.total_section_count }}</small>
              </strong>
            </article>
            <article>
              <el-icon><RefreshRight /></el-icon>
              <span>最近更新</span>
              <strong class="dashboard-rag-metrics__time">
                {{ formatDateTime(ragOverview.last_indexed_at) }}
              </strong>
            </article>
          </div>

          <div class="dashboard-rag-coverage">
            <div class="dashboard-rag-coverage__heading">
              <div>
                <h3>章节知识覆盖</h3>
                <p>{{ ragOverview.embedding_model_alias }} · {{ ragOverview.embedding_dimension }} 维</p>
              </div>
              <span>知识块数量</span>
            </div>
            <div class="dashboard-rag-coverage__grid">
              <article
                v-for="section in ragOverview.section_coverage"
                :key="section.code"
                :class="{ 'is-empty': section.chunk_count === 0 }"
              >
                <span>{{ section.name }}</span>
                <strong>{{ section.chunk_count }}</strong>
                <div aria-hidden="true">
                  <i :style="{ width: ragSectionWidth(section) }" />
                </div>
              </article>
            </div>
          </div>
        </div>

        <aside v-if="ragOverview.operations" class="dashboard-rag-operations">
          <header>
            <div>
              <span>运行状态</span>
              <h3>队列与入库</h3>
            </div>
            <el-tag
              :type="operationStatusType(ragOverview.operations)"
              effect="light"
            >
              {{ operationStatusLabel(ragOverview.operations) }}
            </el-tag>
          </header>

          <dl>
            <div>
              <dt>Redis</dt>
              <dd>
                <i
                  class="status-dot"
                  :class="ragOverview.operations.redis_status === 'ok'
                    ? 'status-dot--success'
                    : 'status-dot--danger'"
                />
                {{ ragOverview.operations.redis_status === 'ok' ? '正常' : '不可用' }}
              </dd>
            </div>
            <div>
              <dt>Worker</dt>
              <dd>{{ workerStatusLabel(ragOverview.operations.worker_status) }}</dd>
            </div>
            <div>
              <dt>等待任务</dt>
              <dd>{{ ragOverview.operations.queue_depth }}</dd>
            </div>
            <div>
              <dt>处理中入库</dt>
              <dd>{{ ragOverview.operations.processing_uploads }}</dd>
            </div>
            <div>
              <dt>失败入库</dt>
              <dd :class="{ 'is-danger': ragOverview.operations.failed_uploads > 0 }">
                {{ ragOverview.operations.failed_uploads }}
              </dd>
            </div>
          </dl>

          <div class="dashboard-rag-operations__latest">
            <span>最近入库</span>
            <strong>{{ uploadStatusLabel(ragOverview.operations.latest_upload_status) }}</strong>
            <small>{{ formatDateTime(ragOverview.operations.latest_upload_at) }}</small>
          </div>
        </aside>
      </div>
    </section>
  </section>
</template>

<style scoped>
.dashboard-location-row {
  display: grid;
  grid-template-columns: minmax(0, 1.05fr) minmax(360px, 0.95fr);
  gap: 20px;
  align-items: stretch;
}

.dashboard-location-row--single {
  grid-template-columns: minmax(0, 1fr);
}

.dashboard-location-row .dashboard-location-panel {
  max-width: none;
}

.dashboard-location-panel,
.dashboard-personnel-panel,
.dashboard-rag-panel {
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-1);
  background: var(--color-bg-surface);
}

.dashboard-location-panel,
.dashboard-personnel-panel {
  min-height: 420px;
}

.dashboard-location-panel {
  align-content: start;
  padding: 20px;
}

.dashboard-personnel-panel {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) auto;
  gap: 14px;
  padding: 20px;
  overflow: hidden;
}

.dashboard-personnel-panel > header,
.dashboard-rag-panel__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.dashboard-personnel-panel h2,
.dashboard-rag-panel h2,
.dashboard-rag-panel h3 {
  margin: 0;
  color: var(--color-text-primary);
}

.dashboard-personnel-panel h2,
.dashboard-rag-panel h2 {
  margin-top: 4px;
  font-size: 18px;
}

.dashboard-personnel-panel p,
.dashboard-rag-panel p {
  margin: 4px 0 0;
  color: var(--color-text-secondary);
  font-size: 13px;
}

.dashboard-panel-kicker {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--color-brand);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.04em;
}

.dashboard-personnel-panel__map-link {
  position: relative;
  display: block;
  min-height: 280px;
  overflow: hidden;
  border: 1px solid var(--color-border-light);
  border-radius: calc(var(--radius-md) - 2px);
  color: inherit;
  background: var(--color-bg-surface-secondary);
  text-decoration: none;
}

.dashboard-personnel-panel__map-link::after {
  position: absolute;
  inset: 0;
  border: 2px solid transparent;
  border-radius: inherit;
  content: '';
  pointer-events: none;
  transition: border-color var(--duration-base) var(--ease-standard);
}

.dashboard-personnel-panel__map-link:hover::after,
.dashboard-personnel-panel__map-link:focus-visible::after {
  border-color: var(--color-brand);
}

.dashboard-personnel-panel__cta {
  position: absolute;
  right: 14px;
  bottom: 14px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  border: 1px solid rgb(255 255 255 / 42%);
  border-radius: 999px;
  box-shadow: 0 8px 18px rgb(15 36 55 / 22%);
  color: #fff;
  background: rgb(16 42 67 / 84%);
  backdrop-filter: blur(10px);
  font-size: 13px;
  font-weight: 700;
}

.dashboard-personnel-panel footer {
  display: flex;
  align-items: center;
  gap: 16px;
  color: var(--color-text-secondary);
  font-size: 12px;
}

.dashboard-personnel-panel footer span {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.dashboard-personnel-panel footer strong {
  margin-left: auto;
  color: var(--color-text-primary);
}

.status-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-text-secondary);
}

.status-dot--success {
  background: var(--color-success);
}

.status-dot--warning {
  background: var(--color-warning);
}

.status-dot--danger {
  background: var(--color-danger);
}

.dashboard-rag-panel {
  display: grid;
  gap: 20px;
  padding: 22px;
}

.dashboard-rag-panel__header-actions {
  display: flex;
  align-items: center;
  gap: 14px;
}

.dashboard-text-link {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: var(--color-brand-active);
  font-size: 13px;
  font-weight: 700;
  text-decoration: none;
}

.dashboard-text-link:hover,
.dashboard-text-link:focus-visible {
  color: var(--color-brand);
  text-decoration: underline;
  text-underline-offset: 3px;
}

.dashboard-rag-panel__body {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 300px;
  gap: 20px;
}

.dashboard-rag-panel__body--business-only {
  grid-template-columns: minmax(0, 1fr);
}

.dashboard-rag-business {
  display: grid;
  min-width: 0;
  gap: 18px;
}

.dashboard-rag-metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.dashboard-rag-metrics article {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 4px 10px;
  min-height: 104px;
  align-content: center;
  padding: 15px;
  border: 1px solid var(--color-border-light);
  border-radius: calc(var(--radius-md) - 2px);
  background:
    linear-gradient(145deg, var(--color-brand-glow), transparent 62%),
    var(--color-bg-surface-secondary);
}

.dashboard-rag-metrics .el-icon {
  grid-row: span 2;
  align-self: center;
  color: var(--color-brand);
  font-size: 22px;
}

.dashboard-rag-metrics span {
  color: var(--color-text-secondary);
  font-size: 12px;
}

.dashboard-rag-metrics strong {
  color: var(--color-text-primary);
  font-size: 24px;
  font-variant-numeric: tabular-nums;
  line-height: 1.15;
}

.dashboard-rag-metrics strong small {
  color: var(--color-text-secondary);
  font-size: 13px;
  font-weight: 500;
}

.dashboard-rag-metrics .dashboard-rag-metrics__time {
  font-size: 14px;
  line-height: 1.35;
}

.dashboard-rag-coverage {
  display: grid;
  gap: 14px;
  padding: 18px;
  border: 1px solid var(--color-border-light);
  border-radius: calc(var(--radius-md) - 2px);
}

.dashboard-rag-coverage__heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.dashboard-rag-coverage__heading h3 {
  font-size: 15px;
}

.dashboard-rag-coverage__heading > span {
  color: var(--color-text-tertiary);
  font-size: 12px;
}

.dashboard-rag-coverage__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px 18px;
}

.dashboard-rag-coverage__grid article {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 7px 12px;
}

.dashboard-rag-coverage__grid article > span {
  overflow: hidden;
  color: var(--color-text-secondary);
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.dashboard-rag-coverage__grid article > strong {
  color: var(--color-text-primary);
  font-size: 12px;
  font-variant-numeric: tabular-nums;
}

.dashboard-rag-coverage__grid article > div {
  grid-column: 1 / -1;
  height: 5px;
  overflow: hidden;
  border-radius: 999px;
  background: var(--color-bg-surface-active);
}

.dashboard-rag-coverage__grid article i {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, var(--color-brand), var(--color-brand-2));
}

.dashboard-rag-coverage__grid article.is-empty {
  opacity: 0.58;
}

.dashboard-rag-operations {
  display: grid;
  align-content: start;
  gap: 18px;
  padding: 18px;
  border: 1px solid var(--color-border-light);
  border-radius: calc(var(--radius-md) - 2px);
  background: var(--color-bg-surface-secondary);
}

.dashboard-rag-operations > header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.dashboard-rag-operations header span,
.dashboard-rag-operations__latest span {
  color: var(--color-text-secondary);
  font-size: 12px;
}

.dashboard-rag-operations h3 {
  margin-top: 3px;
  font-size: 16px;
}

.dashboard-rag-operations dl {
  display: grid;
  gap: 0;
  margin: 0;
}

.dashboard-rag-operations dl > div {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 10px 0;
  border-bottom: 1px solid var(--color-divider);
}

.dashboard-rag-operations dt {
  color: var(--color-text-secondary);
  font-size: 13px;
}

.dashboard-rag-operations dd {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  margin: 0;
  color: var(--color-text-primary);
  font-size: 13px;
  font-weight: 700;
}

.dashboard-rag-operations dd.is-danger {
  color: var(--color-danger);
}

.dashboard-rag-operations__latest {
  display: grid;
  gap: 4px;
  padding: 13px;
  border-radius: var(--radius-sm);
  background: var(--color-bg-surface);
}

.dashboard-rag-operations__latest strong {
  color: var(--color-text-primary);
  font-size: 14px;
}

.dashboard-rag-operations__latest small {
  color: var(--color-text-tertiary);
  font-size: 12px;
}

.dashboard-inline-state {
  display: grid;
  min-height: 250px;
  align-content: center;
  justify-items: center;
  gap: 8px;
  padding: 24px;
  border: 1px dashed var(--color-border);
  border-radius: calc(var(--radius-md) - 2px);
  color: var(--color-text-secondary);
  background: var(--color-bg-surface-secondary);
  text-align: center;
}

.dashboard-inline-state--wide {
  min-height: 220px;
}

.dashboard-inline-state > .el-icon {
  color: var(--color-brand);
  font-size: 30px;
}

.dashboard-inline-state strong {
  color: var(--color-text-primary);
}

.dashboard-inline-state span {
  max-width: 520px;
  font-size: 12px;
}

@media (max-width: 1100px) {
  .dashboard-location-row,
  .dashboard-rag-panel__body {
    grid-template-columns: 1fr;
  }

  .dashboard-location-panel,
  .dashboard-personnel-panel {
    min-height: auto;
  }
}

@media (max-width: 760px) {
  .dashboard-personnel-panel > header,
  .dashboard-rag-panel__header,
  .dashboard-rag-panel__header-actions {
    align-items: flex-start;
    flex-direction: column;
  }

  .dashboard-rag-metrics,
  .dashboard-rag-coverage__grid {
    grid-template-columns: 1fr 1fr;
  }
}

@media (max-width: 520px) {
  .dashboard-location-row,
  .dashboard-rag-panel {
    gap: 14px;
  }

  .dashboard-location-panel,
  .dashboard-personnel-panel,
  .dashboard-rag-panel {
    padding: 16px;
  }

  .dashboard-rag-metrics,
  .dashboard-rag-coverage__grid {
    grid-template-columns: 1fr;
  }

  .dashboard-personnel-panel footer {
    flex-wrap: wrap;
  }

  .dashboard-personnel-panel footer strong {
    width: 100%;
    margin-left: 0;
  }
}
</style>
