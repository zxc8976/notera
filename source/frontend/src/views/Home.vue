<template>
  <DefaultLayout>
    
    <div class="home-content">
      <!-- 左側邊欄 -->
      <aside class="app-sidebar">
        <!-- 處理設置面板 -->
        <div class="collapsible-panel">
          <div class="collapsible-title" @click="showProcessingPanel = !showProcessingPanel">
            <div class="title-with-icon">
              <svg class="title-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="3" />
                <path d="M12 1v6m0 6v6m11-7h-6m-6 0H1" />
              </svg>
              <span>{{ t('processingSettings') }}</span>
            </div>
            <span class="collapse-arrow" :class="{ open: showProcessingPanel }">⌃</span>
          </div>
          <div class="settings-panel" v-show="showProcessingPanel">

            <div class="setting-group">
              <label class="setting-label">{{ t('modelSelection') }}</label>
              <select v-model="selectedModel" class="setting-select" :disabled="!modelList.length">
                <option v-for="model in modelList" :key="model" :value="model">{{ model }}</option>
              </select>
              <div class="setting-hint" v-if="!modelList.length">暫無可用模型，請刷新 LLM</div>
              <div class="provider-summary" v-if="availableProviders.length">
                <div class="provider-row provider-selector" v-if="availableProviders.length > 1">
                  <span class="provider-label">選擇引擎</span>
                  <select
                    class="provider-select"
                    v-model="selectedProvider"
                    @change="handleProviderSwitch"
                    :disabled="switchingProvider || llmStatus === 'loading'"
                  >
                    <option v-for="provider in availableProviders" :key="provider.name" :value="provider.name">
                      {{ provider.title }}
                    </option>
                  </select>
                </div>
                <div class="provider-row" v-if="activeProviderTitle">
                  <span class="provider-label">目前引擎</span>
                  <span class="provider-value">{{ activeProviderTitle }}</span>
                </div>
                <div class="provider-row" v-if="activeProviderEndpoint">
                  <span class="provider-label">Endpoint</span>
                  <span class="provider-value">{{ activeProviderEndpoint }}</span>
                </div>
                <div class="provider-actions">
                  <button class="btn btn-secondary btn-sm refresh-llm" @click="refreshLlmProviders(true)" :disabled="llmStatus === 'loading'">
                    🔄 刷新 LLM 狀態
                  </button>
                  <span class="provider-hint" v-if="availableProviders.length > 1">
                    若要永久切換，可在 `config.yaml` 中更新 `llm.provider`。
                  </span>
                </div>
                <p v-if="llmStatus === 'error' && llmErrorMessage" class="provider-warning">
                  ⚠️ {{ llmErrorMessage }}
                </p>
              </div>
            </div>

            <div class="setting-group">
              <label class="setting-label">{{ t('noteStyle') }}</label>
              <select v-model="noteStyle" class="setting-select">
                <option value="lecture">{{ t('lectureMode') || '上課內容（講義重點）' }}</option>
                <option value="meeting">{{ t('meetingMode') || '會議整理（重點與待辦）' }}</option>
              </select>
            </div>

            <div class="setting-group">
              <label class="setting-label">{{ t('computeDevice') }}</label>
              <select v-model="device" class="setting-select">
                <option value="gpu">{{ t('gpuAcceleration') }}</option>
                <option value="cpu">{{ t('cpuComputing') }}</option>
              </select>
            </div>

            <div class="setting-group">
              <label class="setting-label">{{ t('notes') }}</label>
              <textarea v-model="note" class="setting-textarea" :placeholder="t('notesPlaceholder')"></textarea>
            </div>

            <div class="setting-group">
              <label class="setting-label">{{ t('bilingualNotes') }}</label>
              <div class="toggle-group">
                <label class="toggle-switch">
                  <input type="checkbox" v-model="includeJapanese">
                  <span class="toggle-slider"></span>
                </label>
                <span class="toggle-text">{{ t('includeJapaneseContent') }}</span>
              </div>
              <div class="setting-hint">{{ t('bilingualNotesHint') }}</div>
            </div>

            <div class="setting-group">
              <label class="setting-label">語音辨識</label>
              <div class="toggle-group">
                <label class="toggle-switch">
                  <input type="checkbox" v-model="parseAudio">
                  <span class="toggle-slider"></span>
                </label>
                <span class="toggle-text">{{ parseAudio ? t('parseAudio') : t('dontParseAudio') }}</span>
              </div>
              <div class="setting-hint">雜訊多或語音混亂時可關閉，避免辨識錯誤影響流程穩定性</div>
            </div>
          </div>
        </div>

        <div class="collapsible-panel">
          <div class="collapsible-title" @click="showSystemMetrics = !showSystemMetrics">
            <div class="title-with-icon">
              <svg class="title-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10" />
                <path d="M12 6v6l3 3" />
              </svg>
              <span>{{ t('systemMetricsPanel') }}</span>
            </div>
            <span class="collapse-arrow" :class="{ open: showSystemMetrics }">⌃</span>
          </div>
          <SystemMetricsPanel
            v-if="showSystemMetrics"
            :t="t"
            :processing-filename="currentProcessingFilename"
            @diagnose="runDiagnose"
          />
        </div>

        <!-- Ollama 服務狀態監控面板 -->
        <div class="collapsible-panel">
          <div
            class="collapsible-title"
            @click="showOllamaPanel = !showOllamaPanel"
            :class="{'panel-error': ollamaStatus.status === 'error', 'panel-warning': ollamaStatus.status === 'warning'}"
          >
            <div class="title-with-icon">
              <svg class="title-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10" />
                <path d="M12 16v-4m0-4h.01" />
              </svg>
              <span>Ollama 服務狀態</span>
            </div>
            <span class="collapse-arrow" :class="{ open: showOllamaPanel }">⌃</span>
          </div>

          <div class="settings-panel" v-show="showOllamaPanel">
            <div class="setting-group">
            <div class="ollama-status-container">
              <div class="status-indicator" :class="ollamaStatus.status">
                <span class="status-dot"></span>
                <span class="status-text">{{ ollamaStatus.message || '檢查中...' }}</span>
              </div>
              
              <div class="ollama-actions">
                <button 
                  class="btn btn-secondary" 
                  @click="checkOllamaHealth"
                  :disabled="checkingOllama"
                >
                  {{ checkingOllama ? '⏳ 檢查中...' : '🔍 檢查狀態' }}
                </button>
                
                <button 
                  v-if="ollamaStatus.status === 'error' || ollamaStatus.can_restart"
                  class="btn btn-warning" 
                  @click="restartOllama"
                  :disabled="restartingOllama"
                >
                  {{ restartingOllama ? '⏳ 重啟中...' : '🔄 重啟 Ollama' }}
                </button>
              </div>

              <div class="ollama-models" v-if="ollamaStatus.models && ollamaStatus.models.length">
                <div class="models-label">已載入模型:</div>
                <div class="models-list">
                  <span 
                    v-for="model in ollamaStatus.models" 
                    :key="model" 
                    class="model-tag"
                  >
                    {{ model }}
                  </span>
                </div>
              </div>

              <div class="ollama-hint" v-if="ollamaStatus.status === 'error'">
                ⚠️ LLM 分析功能需要 Ollama 正常運行。請點擊"重啟 Ollama"按鈕修復。
              </div>
              </div>
            </div>
          </div>
        </div>

        <!-- {{ t('pathManagementPanel') }} -->
        <div class="collapsible-panel">
          <div class="collapsible-title" @click="showPathPanel = !showPathPanel">
            <div class="title-with-icon">
              <svg class="title-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M3 7v10a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2z" />
                <path d="M8 21l-2-2" />
              </svg>
              <span>{{ t('pathManagement') }}</span>
            </div>
            <span class="collapse-arrow" :class="{ open: showPathPanel }">⌃</span>
          </div>
          <div class="settings-panel" v-show="showPathPanel">

          <div class="setting-group">
            <label class="setting-label">{{ t('videoFolderPath') }}</label>
            <div class="path-input-group">
              <input 
                v-model="videoFolderPath" 
                class="setting-input" 
                :placeholder="t('videoPathPlaceholder')"
                @change="updateVideoPath"
              />
              <button class="btn btn-secondary path-btn" @click="openPathDialog('video')" :title="t('browseFolder')">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
                </svg>
                {{ t('setPath') }}
              </button>
            </div>
            <div class="path-status" v-if="videoPathStatus">
              <span :class="videoPathStatus.type">{{ videoPathStatus.message }}</span>
            </div>
          </div>

          <div class="setting-group">
            <label class="setting-label">{{ t('imageFolderPath') }}</label>
            <div class="path-input-group">
              <input 
                v-model="imageFolderPath" 
                class="setting-input" 
                :placeholder="t('imagePathPlaceholder')"
                @change="updateImagePath"
              />
              <button class="btn btn-secondary path-btn" @click="openPathDialog('image')" :title="t('browseFolder')">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
                </svg>
                {{ t('setPath') }}
              </button>
            </div>
            <div class="path-status" v-if="imagePathStatus">
              <span :class="imagePathStatus.type">{{ imagePathStatus.message }}</span>
            </div>
          </div>

          <div class="setting-group">
            <label class="setting-label">{{ t('quickPaths') }}</label>
            <div class="quick-paths">
              <button 
                v-for="path in quickPaths" 
                :key="path.name" 
                class="btn btn-info quick-path-btn"
                @click="setQuickPath(path)"
                :title="path.description"
              >
                {{ path.name }}
              </button>
            </div>
          </div>
        </div>
        </div>

        <!-- 資料夾樹狀結構 -->
        <div class="collapsible-panel">
          <div class="collapsible-title" @click="showFolderPanel = !showFolderPanel">
            <div class="title-with-icon">
              <svg class="title-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M3 7v10a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2z" />
                <path d="M8 21l-2-2" />
              </svg>
              <span>{{ t('folderTreeStructure') }}</span>
            </div>
            <span class="collapse-arrow" :class="{ open: showFolderPanel }">⌃</span>
          </div>
          <div class="folder-panel" v-show="showFolderPanel">

          <div class="folder-path">
            <svg class="path-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M3 7v10a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2z" />
              <path d="M8 21l-2-2" />
            </svg>
            <span class="path-text">{{ videoFolder }}</span>
          </div>

          <div class="folder-tree">
            <el-tree 
              :data="folderTree" 
              :props="treeProps" 
              node-key="key" 
              highlight-current 
              @node-click="onFolderSelect"
              :default-expanded-keys="[selectedFolderKey]" 
              :expand-on-click-node="false" 
            />
          </div>

          <div class="folder-options">
            <label class="option-toggle">
              <input type="checkbox" v-model="includeSubfolders" @change="filterVideos">
              <span class="toggle-text">{{ t('includeSubfoldersText') }}</span>
            </label>
          </div>
        </div>
        </div>
      </aside>

      <!-- 右側主內容 -->
      <div class="app-content">
        <!-- 影片處理區塊 -->
        <section class="content-section">
          <div class="section-header">
            <div class="section-title">
              <svg class="section-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polygon points="23 7 16 12 23 17 23 7" />
                <rect x="1" y="5" width="15" height="14" rx="2" ry="2" />
              </svg>
              <h2>{{ t('videoProcessing') }}</h2>
            </div>
            <div class="section-actions">
              <button class="collapse-btn" @click="videoSectionCollapsed = !videoSectionCollapsed" :title="videoSectionCollapsed ? t('expandVideoArea') : t('collapseVideoArea')">
                <svg v-if="videoSectionCollapsed" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <polyline points="6 9 12 15 18 9" />
                </svg>
                <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <polyline points="18 15 12 9 6 15" />
                </svg>
              </button>
              <button class="refresh-btn" @click="refreshVideoList" :title="t('refreshVideoList')">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <polyline points="23 4 23 10 17 10" />
                  <path d="m3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
                </svg>
                <span class="refresh-label">{{ t('refreshVideoList') }}</span>
              </button>
            </div>
          </div>

          <div class="collapsible-content" v-show="!videoSectionCollapsed">
            <!-- 統計信息欄 -->
            <div class="stats-bar" v-if="filteredVideos && filteredVideos.length">
              <div class="stats-info">
                <span class="stat-item">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polygon points="23 7 16 12 23 17 23 7" />
                    <rect x="1" y="5" width="15" height="14" rx="2" ry="2" />
                  </svg>
                  {{ t('totalVideosCount', { count: filteredVideos.length }) }}
                </span>
                <span class="stat-item success">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                  {{ t('processedCount', { count: processedVideoCount }) }}
                </span>
                <span class="stat-item pending">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="12" cy="12" r="10" />
                    <path d="M12 6v6l4 2" />
                  </svg>
                  {{ t('pendingCount', { count: unprocessedVideoCount }) }}
                </span>
              </div>
              <div class="stats-actions">
                <button 
                  v-if="unprocessedVideoCount > 0" 
                  class="btn btn-warning batch-process-btn" 
                  @click="processAllVideos"
                  :disabled="isProcessing"
                >
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="9 11 12 14 22 4" />
                    <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
                  </svg>
                  {{ t('batchProcess') }} ({{ unprocessedVideoCount }})
                </button>
              </div>
            </div>

            <!-- 影片網格 -->
            <div class="media-grid" v-if="filteredVideos && filteredVideos.length">
              <div 
                v-for="video in filteredVideos" 
                :key="video.path" 
                class="media-card"
                :class="{ 
                  'has-result': video.hasResult,
                  'processing': video.isProcessing,
                  'failed': video.hasFailed,
                  'cancelled': video.isCancelled
                }"
              >
                <div class="card-header">
                  <h3 class="media-title">{{ video.name }}</h3>
                  <div class="media-status">
                    <div v-if="video.hasResult" class="status-indicator completed">
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="20 6 9 17 4 12"></polyline>
                      </svg>
                      {{ t('completed') }}
                    </div>
                    <div v-else-if="video.isProcessing" class="status-indicator processing">
                      <div class="loading-spinner"></div>
                      {{ t('processing') }}
                    </div>
                    <div v-else-if="video.isCancelled" class="status-indicator cancelled">
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <rect x="6" y="6" width="12" height="12"></rect>
                      </svg>
                      {{ t('taskCancelled') || '已取消' }}
                    </div>
                    <div v-else-if="video.hasFailed" class="status-indicator failed">
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <circle cx="12" cy="12" r="10"></circle>
                        <line x1="15" y1="9" x2="9" y2="15"></line>
                        <line x1="9" y1="9" x2="15" y2="15"></line>
                      </svg>
                      {{ t('failed') }}
                    </div>
                    <div v-else class="status-indicator pending">
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <circle cx="12" cy="12" r="10"></circle>
                        <polyline points="12 6 12 12 16 14"></polyline>
                      </svg>
                      {{ t('pending') }}
                    </div>
                  </div>
                </div>
                
                <div class="card-body">
                  <div class="media-info">
                    <div class="info-item">
                      <span class="info-label">檔案:</span>
                      <span class="info-value">{{ video.filename || video.name }}</span>
                    </div>
                    <div class="info-item">
                      <span class="info-label">{{ t('path') }}:</span>
                      <span class="info-value">{{ video.path }}</span>
                    </div>
                    <div class="info-item" v-if="video.duration">
                      <span class="info-label">{{ t('duration') }}:</span>
                      <span class="info-value">{{ formatDuration(video.duration) }}</span>
                    </div>
                    <div class="info-item" v-if="video.size">
                      <span class="info-label">{{ t('fileSize') }}:</span>
                      <span class="info-value">{{ formatFileSize(video.size) }}</span>
                    </div>
                  </div>
                </div>

                <!-- 進度條顯示（影片） -->
                <div v-if="video.isProcessing" class="progress-container">
                  <div class="progress-info">
                    <span class="progress-text">{{ t('processing') }}</span>
                    <span class="progress-percent">{{ video.progress || 0 }}%</span>
                  </div>
                  <div v-if="video.detail || video.current_file" class="current-file">{{ video.detail || video.current_file }}</div>
                  <div class="progress-bar">
                    <div class="progress-fill" :style="{ width: (video.progress || 0) + '%' }"></div>
                  </div>
                  <div v-if="video.elapsed_time" class="elapsed-time">
                    ⏱️ 已用時: {{ formatElapsedTime(video.elapsed_time) }}
                  </div>
                  <ProcessingProgressPanel
                    v-if="progressTimeline[video.filename]"
                    :events="progressTimeline[video.filename]"
                    :job-id="video.filename"
                    :is-streaming="progressStreamHealthy"
                    :fallback-active="isProgressPolling"
                  />
                </div>

                <div class="card-actions">
                  <!-- 單卡刷新按鈕（僅在已啟動過/處理中的未完成影片顯示） -->
                  <button 
                    v-if="!video.hasResult && (video.isProcessing || video.hasTmp)" 
                    class="btn btn-secondary" 
                    @click="refreshSingleVideo(video)">
                    🔄 {{ t('refresh') || '刷新' }}
                  </button>
                  <button 
                    v-if="!video.hasResult && !video.isProcessing" 
                    class="btn btn-primary"
                    @click="processVideo(video)"
                  >
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <polygon points="5 3 19 12 5 21 5 3" />
                    </svg>
                    {{ t('startProcessing') }}
                  </button>
                  
                  <button 
                    v-if="video.hasResult" 
                    class="btn btn-success"
                    @click="loadVideoResult(video)"
                  >
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                      <polyline points="14 2 14 8 20 8" />
                      <line x1="16" y1="13" x2="8" y2="13" />
                      <line x1="16" y1="17" x2="8" y2="17" />
                      <polyline points="10 9 9 9 8 9" />
                    </svg>
                    {{ t('loadResult') }}
                  </button>

                  <!-- 重新處理影片（完成後顯示） -->
                  <button 
                    v-if="video.hasResult && !video.isProcessing" 
                    class="btn btn-warning"
                    @click="processVideo(video)"
                  >
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <polyline points="23 4 23 10 17 10" />
                      <path d="m3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
                    </svg>
                    {{ t('reprocess') }}
                  </button>

                  <button 
                    v-if="video.isProcessing" 
                    class="btn btn-warning"
                    @click="checkProgress(video)"
                  >
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <circle cx="12" cy="12" r="10" />
                      <path d="M12 6v6l4 2" />
                    </svg>
                    {{ t('checkProgress') }}
                  </button>
                  <button 
                    v-if="video.isProcessing" 
                    class="btn btn-danger"
                    @click="cancelVideoProcessing(video)"
                  >
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <rect x="6" y="6" width="12" height="12" />
                    </svg>
                    {{ t('cancelProcessing') }}
                  </button>

                  <button 
                    v-if="video.hasFailed" 
                    class="btn btn-danger"
                    @click="retryVideo(video)"
                  >
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <polyline points="23 4 23 10 17 10" />
                      <path d="m3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
                    </svg>
                    {{ t('retry') }}
                  </button>

                  <button 
                    class="btn btn-secondary"
                    @click="showVideoDetails(video)"
                  >
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <circle cx="12" cy="12" r="3" />
                      <path d="M12 1v6m0 6v6m11-7h-6m-6 0H1" />
                    </svg>
                    {{ t('details') }}
                  </button>
                </div>
              </div>
            </div>

            <!-- 空狀態 -->
            <div v-else class="empty-state">
              <div class="empty-icon">📹</div>
              <h3>{{ t('noVideoFiles') }}</h3>
              <p class="empty-hint">{{ t('putVideoFiles') }}</p>
              <button class="btn btn-primary" @click="refreshVideoList">
                {{ t('rescanVideos') }}
              </button>
            </div>
          </div>
        </section>

        <!-- 圖片處理區塊 -->
        <section class="content-section">
          <div class="section-header">
            <div class="section-title">
              <svg class="section-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <rect x="3" y="5" width="18" height="14" rx="2" ry="2" />
                <circle cx="8.5" cy="11" r="1.5" />
                <polyline points="21 16 16 11 12 15 9 12 3 18" />
              </svg>
              <h2>{{ t('imageProcessing') }}</h2>
            </div>
            <div class="section-actions">
              <button
                class="collapse-btn"
                @click="imageSectionCollapsed = !imageSectionCollapsed"
                :title="imageSectionCollapsed ? t('expandImageArea') : t('collapseImageArea')"
              >
                <svg
                  v-if="imageSectionCollapsed"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                >
                  <polyline points="6 9 12 15 18 9" />
                </svg>
                <svg
                  v-else
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                >
                  <polyline points="18 15 12 9 6 15" />
                </svg>
              </button>
              <button
                class="refresh-btn"
                @click="refreshImageFolders"
                :title="t('refreshImageFolders')"
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <polyline points="23 4 23 10 17 10" />
                  <path d="m3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
                </svg>
                <span class="refresh-label">{{ t('refreshImageFolders') }}</span>
              </button>
            </div>
          </div>

          <div class="collapsible-content" v-show="!imageSectionCollapsed">
            <!-- 統計信息欄 -->
            <div class="stats-bar" v-if="imageFolders && imageFolders.length">
              <div class="stats-info">
                <span class="stat-item">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <rect x="3" y="5" width="18" height="14" rx="2" ry="2" />
                    <polyline points="21 16 16 11 12 15 9 12 3 18" />
                  </svg>
                  {{ t('totalFoldersCount', { count: imageFolders.length }) }}
                </span>
                <span class="stat-item success">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                  {{ t('processedCount', { count: processedFolderCount }) }}
                </span>
                <span class="stat-item pending">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="12" cy="12" r="10" />
                    <path d="M12 6v6l4 2" />
                  </svg>
                  {{ t('pendingCount', { count: unprocessedFolderCount }) }}
                </span>
              </div>
              <div class="stats-actions">
                <button 
                  v-if="unprocessedFolderCount > 0" 
                  class="btn btn-warning batch-process-btn" 
                  @click="processAllFolders"
                  :disabled="isProcessingFolders"
                >
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="9 11 12 14 22 4" />
                    <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
                  </svg>
                  {{ t('batchProcess') }} ({{ unprocessedFolderCount }})
                </button>
              </div>
            </div>

            <!-- 載入狀態 -->
            <div v-if="imageLoading" class="loading-state">
              <div class="loading-spinner"></div>
              <p>{{ t('loadingImageList') }}</p>
            </div>

            <!-- 資料夾網格 -->
            <div class="media-grid" v-else-if="imageFolders && imageFolders.length">
              <div 
                v-for="folder in imageFolders" 
                :key="folder.path" 
                class="media-card"
                :class="{ 
                  'has-result': folder.hasResult || folder.status === 'completed',
                  'processing': folder.isProcessing || folder.status === 'processing',
                  'failed': folder.hasFailed || folder.status === 'failed'
                }"
              >
                <div class="card-header">
                  <h3 class="media-title">{{ folder.name }}</h3>
                  <div class="media-status">
                    <div v-if="folder.hasResult || folder.status === 'completed'" class="status-indicator completed">
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="20 6 9 17 4 12"></polyline>
                      </svg>
                      {{ t('completed') }}
                    </div>
                    <div v-else-if="folder.isProcessing || folder.status === 'processing'" class="status-indicator processing">
                      <div class="loading-spinner"></div>
                      {{ t('processing') }}
                    </div>
                    <div v-else-if="folder.hasFailed || folder.status === 'failed'" class="status-indicator failed">
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <circle cx="12" cy="12" r="10"></circle>
                        <line x1="15" y1="9" x2="9" y2="15"></line>
                        <line x1="9" y1="9" x2="15" y2="15"></line>
                      </svg>
                      {{ t('failed') }}
                    </div>
                    <div v-else class="status-indicator pending">
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <circle cx="12" cy="12" r="10"></circle>
                        <polyline points="12 6 12 12 16 14"></polyline>
                      </svg>
                      {{ t('pending') }}
                    </div>
                  </div>
                </div>
                
                <div class="card-body">
                  <div class="media-info">
                    <div class="info-item">
                      <span class="info-label">{{ t('folderName') }}:</span>
                      <span class="info-value">{{ folder.name }}</span>
                    </div>
                    <div class="info-item" v-if="folder.path">
                      <span class="info-label">{{ t('path') }}:</span>
                      <span class="info-value">{{ folder.path }}</span>
                    </div>
                    <div class="info-item" v-if="folder.image_count">
                      <span class="info-label">{{ t('imageCount') }}:</span>
                      <span class="info-value">{{ folder.image_count }} {{ t('imagesCount') }}</span>
                    </div>
                  </div>
                </div>

                <!-- 進度條顯示 -->
                <div v-if="folder.isProcessing || folder.status === 'processing'" class="progress-container">
                  <div class="progress-info">
                    <span class="progress-text">{{ folder.progressDetail || t('processing') }}</span>
                    <span class="progress-percent">{{ folder.progress || 0 }}%</span>
                  </div>
                  <div v-if="folder.current_file" class="current-file">{{ folder.current_file }}</div>
                  <div class="progress-bar">
                    <div class="progress-fill" :style="{ width: (folder.progress || 0) + '%' }"></div>
                  </div>
                  <div v-if="folder.elapsed_time" class="elapsed-time">
                    ⏱️ 已用時: {{ formatElapsedTime(folder.elapsed_time) }}
                  </div>
                  <ProcessingProgressPanel
                    v-if="folder.taskId && progressTimeline[folder.taskId]"
                    :events="progressTimeline[folder.taskId]"
                    :job-id="folder.taskId"
                    :is-streaming="progressStreamHealthy"
                    :fallback-active="isProgressPolling"
                  />
                </div>

                <div class="card-actions">
                  <!-- 主要處理按鈕 -->
                  <button 
                    v-if="!folder.isProcessing && folder.status !== 'processing'" 
                    class="btn"
                    :class="folder.hasResult || folder.status === 'completed' ? 'btn-warning' : 'btn-primary'"
                    @click="processFolder(folder)"
                  >
                    <template v-if="folder.hasResult || folder.status === 'completed'">
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="23 4 23 10 17 10" />
                        <path d="m3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
                      </svg>
                      {{ t('reprocess') }}
                    </template>
                    <template v-else>
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polygon points="5 3 19 12 5 21 5 3" />
                      </svg>
                      {{ t('process') }}
                    </template>
                  </button>
                  
                  <!-- 載入結果按鈕 -->
                  <button 
                    v-if="folder.hasResult || folder.status === 'completed'" 
                    class="btn btn-success"
                    @click="loadFolderResult(folder)"
                  >
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                      <polyline points="14 2 14 8 20 8" />
                      <line x1="16" y1="13" x2="8" y2="13" />
                      <line x1="16" y1="17" x2="8" y2="17" />
                      <polyline points="10 9 9 9 8 9" />
                    </svg>
                    {{ t('loadResult') }}
                  </button>

                  <!-- 進度檢查按鈕 -->
                  <button 
                    v-if="folder.isProcessing || folder.status === 'processing'" 
                    class="btn btn-warning"
                    @click="checkFolderProgress(folder)"
                  >
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <circle cx="12" cy="12" r="10" />
                      <path d="M12 6v6l4 2" />
                    </svg>
                    {{ t('checkProgress') }} ({{ folder.progress || 0 }}%)
                  </button>

                  <!-- 詳細信息按鈕 -->
                  <button 
                    class="btn btn-secondary"
                    @click="showFolderDetails(folder)"
                  >
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <circle cx="12" cy="12" r="3" />
                      <path d="M12 1v6m0 6v6m11-7h-6m-6 0H1" />
                    </svg>
                    {{ t('details') }}
                  </button>
                </div>
              </div>
            </div>

            <!-- 空狀態 -->
            <div v-else class="empty-state">
              <div class="empty-icon">📁</div>
              <h3>{{ t('noImageFolders') }}</h3>
              <p class="empty-hint">{{ t('putImageFolders') }}</p>
              <button class="btn btn-primary" @click="refreshImageFolders">
                {{ t('rescanFolders') }}
              </button>
            </div>
          </div>
        </section>

        <!-- 結果顯示區域 -->
        <section v-if="summaryResult" class="result-section" ref="resultSectionEl">
          <div class="section-header">
            <h3>{{ t('processingResults') }}</h3>
            <div class="result-actions">
              <button class="btn btn-success" @click="openSaveDialog">
                {{ t('saveNote') }}
              </button>
              <button class="btn btn-secondary" @click="clearResults">
                {{ t('clearResults') }}
              </button>
              <button class="btn btn-secondary" @click="rerenderMarkdown" title="只在前端重新排版，不重跑後端">
                🔄 前端重新渲染
              </button>
            </div>
            <div class="result-diagnostics" v-if="markdownDiagnostics">
              <span>渲染 {{ markdownDiagnostics.renderMs?.toFixed(1) || 0 }} ms</span>
              <span>程式碼 {{ markdownDiagnostics.codeBlocks }}</span>
              <span>複製按鈕 {{ markdownDiagnostics.injectedButtons }}</span>
            </div>
          </div>
          
          <div class="result-content">
            <!-- ✨ 內嵌 Markdown 渲染器 (整合自 BilingualMarkdownRenderer) -->
            <div class="bilingual-markdown-renderer" v-if="summaryResult">
              <div
                ref="fallbackContainer"
                class="fallback-markdown summary-result"
                v-html="fallbackHtml"
              ></div>
            </div>
          </div>
        </section>
      </div>
    </div>

    <!-- 筆記保存對話框 -->
    <NoteSaveDialog 
      v-model="showSaveDialog" 
      :content="summaryResult" 
      :tmp-filename="currentProcessedVideo?.path"
      :tmp-info="currentProcessedVideo?.tmpInfo" 
      @saved="onNoteSaved"
    />
    
    <!-- BiliNote 檢視對話框 -->
    <el-dialog v-model="showBiliNoteDialog" title="BiliNote 檢視" width="400px">
      <el-form>
        <el-form-item label="Doc ID">
          <el-input v-model="biliNoteId" placeholder="輸入 doc_id" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showBiliNoteDialog = false">取消</el-button>
        <el-button type="primary" @click="goToBiliNote">前往檢視</el-button>
      </template>
    </el-dialog>
  </DefaultLayout>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import { ElMessage, ElLoading, ElMessageBox } from 'element-plus'

import DefaultLayout from '../layouts/DefaultLayout.vue'
import NoteSaveDialog from '../components/NoteSaveDialog.vue'
import SystemMetricsPanel from '../components/SystemMetricsPanel.vue'
import ProcessingProgressPanel from '../components/ProcessingProgressPanel.vue'
import { useLanguage } from '../composables/useLanguage.js'
import { useTheme } from '../composables/useTheme.js'
import { useLlmProviders } from '../composables/useLlmProviders.js'
import { useMarkdownRenderer } from '../composables/useMarkdownRenderer.js'

const DEBUG_MODE = (import.meta.env?.VITE_APP_DEBUG ?? '').toString().toLowerCase() === 'true'
const createDebugLogger = (level) => {
  const method = typeof console[level] === 'function' ? console[level].bind(console) : console.log.bind(console)
  return (...args) => {
    if (!DEBUG_MODE) return
    method(...args)
  }
}
const debugLog = createDebugLogger('log')
const debugInfo = createDebugLogger('info')
const debugWarn = createDebugLogger('warn')
const debugError = createDebugLogger('error')
import '../styles/modal.css'
import '../styles/note.css'
import '../styles/home-markdown.css'
import '../assets/print-ready.css'

// 基本狀態
const selectedModel = ref('')
const noteStyle = ref('lecture')
const device = ref('gpu')
const note = ref('')
const includeJapanese = ref(true)
const parseAudio = ref(true)
const videoFolderPath = ref('/mnt/f/上課影片')
const imageFolderPath = ref('/mnt/f/講義圖片')
const videoPathStatus = ref(null)
const imagePathStatus = ref(null)
const summaryResult = ref('')
const resultSectionEl = ref(null)
const currentNoteStyle = ref('detailed') // 改為使用新的卡片式渲染，不再使用 legacy 雙語模式
const showSaveDialog = ref(false)
const showBiliNoteDialog = ref(false)
const biliNoteId = ref('')
const currentProcessedVideo = ref(null)
const markdownDiagnostics = ref(null)
// 只前端重渲染用的 key，避免觸發後端計算
const rerenderTick = ref(0)

const normalizeNoteStyle = (rawStyle) => {
  const normalized = String(rawStyle || '').trim().toLowerCase()
  if (['meeting', 'summary', 'minutes', 'meetingmode'].includes(normalized)) return 'meeting'
  if (['lecture', 'detailed', 'class', 'classroom', 'lecturemode'].includes(normalized)) return 'lecture'
  return 'lecture'
}

// 使用語言系統（必須在 useMarkdownRenderer 之前）
const { currentLanguage, t, switchLanguage } = useLanguage()
const languageMode = computed(() => (includeJapanese.value ? 'bilingual' : 'ja-only'))
const effectiveLanguage = computed(() => (
  languageMode.value === 'ja-only' ? 'ja' : currentLanguage.value
))

// 使用統一的主題系統
const { isDark } = useTheme()

// ========== Markdown 渲染器 (使用 composable) ==========
const {
  fallbackContainer,
  fallbackHtml,
  updateMarkdownFallback
} = useMarkdownRenderer({
  translate: t,
  onDiagnostics: (payload) => {
    markdownDiagnostics.value = payload
  }
})

// Legacy language configuration (kept for UI compatibility)
const languageConfig = {
  ja: { label: '日文', mainColor: '#ffc107', bgColor: '#fff9e6', borderColor: '#ffc107' },
  'zh-TW': { label: '繁體中文', mainColor: '#4a90e2', bgColor: '#eaf4ff', borderColor: '#4a90e2' },
  'zh-CN': { label: '简体中文', mainColor: '#5470c6', bgColor: '#e8f0ff', borderColor: '#5470c6' },
  en: { label: 'English', mainColor: '#28a745', bgColor: '#e6f7ea', borderColor: '#28a745' },
  ko: { label: '한국어', mainColor: '#e83e8c', bgColor: '#ffe6f3', borderColor: '#e83e8c' },
  vi: { label: 'Tiếng Việt', mainColor: '#17a2b8', bgColor: '#e3f7f9', borderColor: '#17a2b8' },
  my: { label: 'မြန်မာ', mainColor: '#fd7e14', bgColor: '#fff3e6', borderColor: '#fd7e14' },
  mn: { label: 'Монгол', mainColor: '#6f42c1', bgColor: '#f0e8ff', borderColor: '#6f42c1' }
}

const primaryLang = 'ja'
const primaryConfig = computed(() => languageConfig[primaryLang])
const primaryLangLabel = computed(() => primaryConfig.value.label)
const primaryStyle = computed(() => ({
  '--lang-main-color': primaryConfig.value.mainColor,
  '--lang-bg-color': primaryConfig.value.bgColor,
  '--lang-border-color': primaryConfig.value.borderColor
}))

const detectSecondaryLang = (text = '') => {
  const sample = String(text || '')
  if (/[ -\u007f]/.test(sample) && /[ㄱ-ㅎㅏ-ㅣ가-힣]/.test(sample)) return 'ko'
  if (/[ăâđêôơưÁÀÂÃÈÉÊÌÍÒÓÔÕÙÚÝáàâãèéêìíòóôõùúýĐđ]/.test(sample)) return 'vi'
  if (/[A-Za-z]/.test(sample) && !/[\u3040-\u30ff\u31f0-\u31ff\u4e00-\u9fff]/.test(sample)) return 'en'
  return null
}

const secondaryLang = computed(() => {
  const uiLang = currentLanguage.value || 'zh-TW'
  if (!summaryResult.value) return uiLang
  const sample = summaryResult.value.slice(0, 2000)
  const detected = detectSecondaryLang(sample)
  return detected || uiLang
})

const secondaryConfig = computed(() => languageConfig[secondaryLang.value] || languageConfig['zh-TW'])
const secondaryLangLabel = computed(() => secondaryConfig.value.label)
const secondaryStyle = computed(() => ({
  '--lang-main-color': secondaryConfig.value.mainColor,
  '--lang-bg-color': secondaryConfig.value.bgColor,
  '--lang-border-color': secondaryConfig.value.borderColor
}))

const hasStructuredSections = computed(() => currentNoteStyle.value === 'legacy' && parsedSections.value.length > 0)
const parsedSections = computed(() => {
  if (currentNoteStyle.value && currentNoteStyle.value !== 'legacy') return []
  if (!summaryResult.value) return []
  const sections = []
  const lines = summaryResult.value.split('\n')
  let currentSection = null
  let inCodeBlock = false
  let inDetailsBlock = false

  for (const line of lines) {
    const trimmedLine = line.trim()
    if (trimmedLine.startsWith('```')) {
      inCodeBlock = !inCodeBlock
      continue
    }
    if (trimmedLine.startsWith('<details') || trimmedLine.startsWith('</details')) {
      inDetailsBlock = trimmedLine.startsWith('<details')
      continue
    }
    if (inCodeBlock || inDetailsBlock || trimmedLine.startsWith('<summary') || trimmedLine.startsWith('</summary') || trimmedLine.startsWith('![')) {
      continue
    }

    if (trimmedLine.startsWith('## ') || trimmedLine.startsWith('# ')) {
      if (currentSection && currentSection.items.length > 0) sections.push(currentSection)
      currentSection = {
        title: trimmedLine.replace(/^#+\s*/, '').replace(/^🟢\s*/, '').replace(/^🔍\s*/, '').replace(/^⚠️\s*/, '').replace(/^📊\s*/, '').replace(/^🔹\s*/, '').replace(/^🔗\s*/, '').trim(),
        items: []
      }
    } else if (trimmedLine.match(/^[-*]\s*🔹?\s*.+[｜|].+/) && currentSection) {
      const cleanLine = trimmedLine.replace(/^[-*]\s*/, '').replace(/^🔹\s*/, '').trim()
      const parts = cleanLine.split(/[｜|]/).map(p => p.trim())
      if (parts.length >= 2 && parts[0] && parts[1] && parts[0] !== '日文' && parts[1] !== '中文' && parts[0].length > 2 && parts[1].length > 2) {
        currentSection.items.push({ primary: parts[0], secondary: parts[1] })
      }
    }
  }
  if (currentSection && currentSection.items.length > 0) sections.push(currentSection)
  return sections
})
// ========== Markdown 渲染器結束 ==========

// 系統資源監控狀態
const currentProcessingFilename = ref('')
const showSystemMetrics = ref(true)
const showOllamaPanel = ref(true)
const showPathPanel = ref(true)
const showFolderPanel = ref(true)
const showProcessingPanel = ref(true)

// 即時進度串流狀態
const progressTimeline = ref({})
const progressStreamHealthy = ref(false)
const isProgressPolling = ref(false)
const lastProgressEventAt = ref(0)

const {
  activeProvider: activeLlmProvider,
  providers: llmProviders,
  status: llmProviderStatus,
  error: llmProviderError,
  refresh: refreshLlmProviders
} = useLlmProviders()
const activeProviderInfo = computed(() => activeLlmProvider.value || null)
const availableProviders = computed(() =>
  llmProviders.value.map((item) => ({
    name: item.name,
    title: item.title || item.name,
    endpoint: item.base_url || null,
    models: Array.isArray(item.models) ? item.models : []
  }))
)
const llmStatus = computed(() => llmProviderStatus.value)
const llmErrorMessage = computed(() => llmProviderError.value?.message || llmProviderError.value || null)
const modelList = computed(() => {
  const provider = activeProviderInfo.value
  if (!provider) return []
  if (Array.isArray(provider.models) && provider.models.length) {
    return Array.from(new Set(provider.models))
  }
  return provider.model ? [provider.model] : []
})
const PROGRESS_MAX_EVENTS = 20
watch(modelList, (models) => {
  if (!models.length) {
    selectedModel.value = ''
    return
  }
  if (!models.includes(selectedModel.value)) {
    selectedModel.value = models[0]
  }
})
const activeProviderTitle = computed(() => activeProviderInfo.value?.title || activeProviderInfo.value?.name || '')
const activeProviderEndpoint = computed(() => activeProviderInfo.value?.base_url || '')
const selectedProvider = ref('')
const switchingProvider = ref(false)

watch(
  activeProviderInfo,
  (provider) => {
    selectedProvider.value = provider?.name || ''
  },
  { immediate: true }
)

const handleProviderSwitch = async () => {
  const target = selectedProvider.value
  const current = activeProviderInfo.value?.name || ''
  if (!target || target === current) {
    return
  }
  switchingProvider.value = true
  try {
    const response = await fetch(`/api/llm/providers/${encodeURIComponent(target)}/activate`, {
      method: 'POST',
      headers: {
        Accept: 'application/json'
      }
    })
    if (!response.ok) {
      throw new Error(`切換失敗 (${response.status})`)
    }
    await refreshLlmProviders(true)
    ElMessage.success(`已切換至 ${availableProviders.value.find(p => p.name === target)?.title || target}`)
  } catch (error) {
    console.error('切換 LLM Provider 失敗:', error)
    ElMessage.error('切換 LLM Provider 失敗，請稍後再試')
    selectedProvider.value = current
  } finally {
    switchingProvider.value = false
  }
}

let progressSocket = null
let progressReconnectTimer = null
let progressMonitorTimer = null
let lastOllamaStatusKey = ''

// Ollama 服務監控狀態
const ollamaStatus = ref({
  status: 'unknown',  // 'healthy' | 'error' | 'warning' | 'unknown'
  message: '尚未檢查',
  models: [],
  can_restart: false
})
const checkingOllama = ref(false)
const restartingOllama = ref(false)
let ollamaHealthTimer = null

// UI狀態
const videoSectionCollapsed = ref(false)
const imageSectionCollapsed = ref(false)
const isProcessing = ref(false)
const isProcessingFolders = ref(false)

// 資料夾相關
const videoFolder = ref('/mnt/f/上課影片')
const selectedFolder = ref('')
const selectedFolderKey = ref('')
const includeSubfolders = ref(false)
const folderTree = ref([])
const treeProps = {
  children: 'children',
  label: 'label'
}

// 數據
const quickPaths = ref([
  { name: '上課影片', path: '/mnt/f/上課影片', description: '預設影片資料夾' },
  { name: '講義圖片', path: '/mnt/f/講義圖片', description: '預設圖片資料夾' }
])

// 真實的影片數據
const filteredVideos = ref([])
const allVideos = ref([])
const videoLoading = ref(false)

// 真實的圖片資料夾數據
const imageFolders = ref([])
const allImageFolders = ref([])
const imageLoading = ref(false)

// 計算屬性
const processedVideoCount = computed(() => {
  return filteredVideos.value.filter(v => v.hasResult).length
})

const unprocessedVideoCount = computed(() => {
  return filteredVideos.value.filter(v => !v.hasResult).length
})

const processedFolderCount = computed(() => {
  return imageFolders.value.filter(f => f.hasResult || f.status === 'completed').length
})

const unprocessedFolderCount = computed(() => {
  return imageFolders.value.filter(f => !f.hasResult && f.status !== 'completed' && !f.isProcessing).length
})

const activeProgressJobId = computed(() => {
  if (currentProcessingFilename.value) {
    return currentProcessingFilename.value
  }
  const activeFolder = imageFolders.value.find(
    (folder) => folder && (folder.isProcessing || folder.status === 'processing') && folder.taskId
  )
  return activeFolder ? activeFolder.taskId : ''
})

// 緩存渲染結果 - 避免無限循環

// 格式化經過時間
const formatElapsedTime = (seconds) => {
  if (!seconds || seconds < 0) return '0秒'
  const minutes = Math.floor(seconds / 60)
  const remainingSeconds = Math.floor(seconds % 60)
  if (minutes > 0) {
    return `${minutes}分${remainingSeconds}秒`
  }
  return `${remainingSeconds}秒`
}

// Markdown渲染函數 - 徹底重構確保正常渲染
// 初始化
onMounted(async () => {
  connectProgressStream()
  await refreshLlmProviders(true)
  progressMonitorTimer = window.setInterval(checkProgressHeartbeat, 10000)
  
  // 載入路徑設置 (Load path settings)
  await loadPaths()
  
  // 載入影片列表 (Load video list)
  await refreshVideoList()
  
  // 載入圖片資料夾列表 (Load image folder list)
  await refreshImageFolders()
  
  // 資料夾樹將在載入影片後自動初始化
  
  // 啟動 Ollama 健康監控（30s 一次）
  startOllamaHealthMonitoring()
})

// 組件卸載時清理定時器
onBeforeUnmount(() => {
  stopOllamaHealthMonitoring()
  if (progressMonitorTimer) {
    clearInterval(progressMonitorTimer)
    progressMonitorTimer = null
  }
  if (progressReconnectTimer) {
    clearTimeout(progressReconnectTimer)
    progressReconnectTimer = null
  }
  closeProgressStream()
})

// 監聽渲染內容變化,綁定代碼複製按鈕
// 改用 watch summaryResult.value 而不是 computed property
watch(activeProgressJobId, (jobId) => {
  if (jobId) {
    fetchProgressSnapshot(jobId)
  }
})

// ========== Ollama 服務監控方法 ==========

// 檢查 Ollama 健康狀態
const checkOllamaHealth = async () => {
  if (checkingOllama.value) return
  
  checkingOllama.value = true
  try {
    const response = await fetch('/api/ollama/health')
    const data = await response.json()
    
    if (data.status === 'healthy') {
      ollamaStatus.value = {
        status: 'healthy',
        message: data.message || 'Ollama 服務正常運行',
        models: data.models || [],
        can_restart: data.can_restart || false
      }
      const statusKey = `healthy:${data.message || ''}:${(data.models || []).map((m) => m?.name || m).join(',')}`
      if (lastOllamaStatusKey !== statusKey) {
        debugInfo('✅ Ollama 健康檢查通過:', data)
        lastOllamaStatusKey = statusKey
      }
    } else {
      ollamaStatus.value = {
        status: 'error',
        message: data.message || 'Ollama 服務異常',
        models: [],
        can_restart: data.can_restart || true
      }
      const statusKey = `error:${data.status || ''}:${data.message || ''}`
      if (lastOllamaStatusKey !== statusKey) {
        debugWarn('❌ Ollama 健康檢查失敗:', data)
        lastOllamaStatusKey = statusKey
      }
    }
  } catch (error) {
    ollamaStatus.value = {
      status: 'error',
      message: `無法連接到 Ollama 服務: ${error.message}`,
      models: [],
      can_restart: true
    }
    const statusKey = `exception:${error?.message || ''}`
    if (lastOllamaStatusKey !== statusKey) {
      debugError('❌ Ollama 健康檢查異常:', error)
      lastOllamaStatusKey = statusKey
    }
  } finally {
    checkingOllama.value = false
  }
}

// 重啟 Ollama 服務
const restartOllama = async () => {
  if (restartingOllama.value) return
  
  try {
    const confirmed = await ElMessageBox.confirm(
      '確定要重啟 Ollama 服務嗎? 這將中斷正在進行的 LLM 分析。',
      '確認重啟',
      {
        confirmButtonText: '確定重啟',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    if (!confirmed) return
  } catch {
    return  // 用戶取消
  }
  
  restartingOllama.value = true
  const loading = ElLoading.service({
    lock: true,
    text: '正在重啟 Ollama 服務，請稍候...',
    background: 'rgba(0, 0, 0, 0.7)'
  })
  
  try {
    const response = await fetch('/api/ollama/restart', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    })
    const data = await response.json()
    
    if (data.success) {
      ElMessage.success(data.message || 'Ollama 服務已成功重啟')
      // 重啟後立即檢查健康狀態
      setTimeout(() => checkOllamaHealth(), 2000)
    } else {
      ElMessage.error(data.message || 'Ollama 重啟失敗')
      ollamaStatus.value.status = 'error'
      ollamaStatus.value.message = data.message || '重啟失敗'
    }
  } catch (error) {
    ElMessage.error(`重啟 Ollama 時發生錯誤: ${error.message}`)
    console.error('❌ Ollama 重啟異常:', error)
  } finally {
    restartingOllama.value = false
    loading.close()
  }
}

// 啟動 Ollama 健康監控定時器 (每30秒檢查一次)
const startOllamaHealthMonitoring = () => {
  stopOllamaHealthMonitoring()
  
  // 立即執行一次
  checkOllamaHealth()
  
  // 每30秒自動檢查
  ollamaHealthTimer = setInterval(() => {
    if (!restartingOllama.value && !checkingOllama.value) {
      checkOllamaHealth()
    }
  }, 30000)
  
  debugLog('🟢 Ollama 健康監控已啟動 (每30秒)')
}

// 停止 Ollama 健康監控
const stopOllamaHealthMonitoring = () => {
  if (ollamaHealthTimer) {
    clearInterval(ollamaHealthTimer)
    ollamaHealthTimer = null
    debugLog('🔴 Ollama 健康監控已停止')
  }
}

// ========== Ollama 監控方法結束 ==========

// 基於實際影片數據初始化資料夾樹的函數
const initializeFolderTree = () => {
  if (!allVideos.value || allVideos.value.length === 0) {
    folderTree.value = []
    return
  }

  // 從實際影片數據中提取資料夾結構
  const folderMap = new Map()
  
  allVideos.value.forEach(video => {
    if (video.path) {
      // 提取資料夾路徑 - 改善邏輯
      const pathParts = video.path.split(/[/\\]/)
      let folderName = 'Root'
      
      if (pathParts.length > 1) {
        // 如果路徑有多個部分，取倒數第二個作為資料夾名
        folderName = pathParts[pathParts.length - 2] || 'Root'
      } else if (video.category) {
        // 如果有category屬性，使用它
        folderName = video.category
      }
      
      if (!folderMap.has(folderName)) {
        folderMap.set(folderName, {
          label: folderName,
          key: folderName.toLowerCase().replace(/[\s/\\]+/g, '_'),
          children: [],
          videos: []
        })
      }
      
      folderMap.get(folderName).videos.push(video)
    }
  })

  // 轉換為樹狀結構
  folderTree.value = Array.from(folderMap.values())
  
  debugLog('📁 資料夾樹已更新:', folderTree.value)
  debugLog('📊 資料夾數量:', folderTree.value.length)
  
  // 如果有資料夾，默認選擇第一個
  if (folderTree.value.length > 0) {
    selectedFolder.value = folderTree.value[0].key
    selectedFolderKey.value = folderTree.value[0].key
    filterVideos()
  }
}

// 方法
const updateVideoPath = async () => {
  debugLog('🔄 更新影片路徑:', videoFolderPath.value)
  videoFolder.value = videoFolderPath.value
  
  try {
    const formData = new FormData()
    formData.append('video_path', videoFolderPath.value)
    formData.append('image_path', imageFolderPath.value)
    
    const response = await fetch('/api/set-paths', {
      method: 'POST',
      body: formData
    })
    
    if (response.ok) {
      videoPathStatus.value = { type: 'success', message: '影片路徑設置成功' }
      ElMessage.success('影片路徑設置成功')
      // 重新載入影片列表
      await refreshVideoList()
    } else {
      throw new Error('設置失敗')
    }
  } catch (error) {
    console.error('設置影片路徑失敗:', error)
    videoPathStatus.value = { type: 'error', message: '設置失敗' }
    ElMessage.error('設置影片路徑失敗')
  }
}

const updateImagePath = async () => {
  debugLog('🔄 更新圖片路徑:', imageFolderPath.value)
  
  try {
    const formData = new FormData()
    formData.append('video_path', videoFolderPath.value)
    formData.append('image_path', imageFolderPath.value)
    
    const response = await fetch('/api/set-paths', {
      method: 'POST',
      body: formData
    })
    
    if (response.ok) {
      imagePathStatus.value = { type: 'success', message: '圖片路徑設置成功' }
      ElMessage.success('圖片路徑設置成功')
      // 重新載入圖片資料夾列表
      await refreshImageFolders()
    } else {
      throw new Error('設置失敗')
    }
  } catch (error) {
    console.error('設置圖片路徑失敗:', error)
    imagePathStatus.value = { type: 'error', message: '設置失敗' }
    ElMessage.error('設置圖片路徑失敗')
  }
}

const openPathDialog = (type) => {
  debugLog('📁 打開路徑對話框:', type)
  ElMessage.info('請手動輸入路徑，或使用快速路徑按鈕')
}

const setQuickPath = (path) => {
  if (path.name === '上課影片') {
    videoFolderPath.value = path.path
    updateVideoPath()
  } else if (path.name === '講義圖片') {
    imageFolderPath.value = path.path
    updateImagePath()
  }
}

const onFolderSelect = (data) => {
  debugLog('📁 資料夾選擇事件觸發:', data)
  debugLog('📁 選擇的資料夾key:', data.key)
  debugLog('📁 選擇的資料夾label:', data.label)
  
  selectedFolder.value = data.key
  selectedFolderKey.value = data.key
  
  debugLog('📁 更新後的selectedFolder:', selectedFolder.value)
  debugLog('📁 更新後的selectedFolderKey:', selectedFolderKey.value)
  
  filterVideos()
}

const filterVideos = () => {
  debugLog('🔍 開始過濾影片，選中的資料夾:', selectedFolder.value)
  debugLog('🔍 當前資料夾樹:', folderTree.value)
  debugLog('🔍 所有影片數量:', allVideos.value.length)
  
  if (!selectedFolder.value || selectedFolder.value === 'all') {
    // 顯示所有影片
    filteredVideos.value = allVideos.value
    debugLog('🔍 顯示所有影片:', filteredVideos.value.length)
  } else {
    // 根據選中的資料夾過濾影片
    const selectedFolderData = folderTree.value.find(folder => folder.key === selectedFolder.value)
    debugLog('🔍 找到的資料夾數據:', selectedFolderData)
    
    if (selectedFolderData && selectedFolderData.videos) {
      filteredVideos.value = selectedFolderData.videos
      debugLog('🔍 資料夾中的影片:', selectedFolderData.videos.length)
    } else {
      // 如果沒有找到對應的資料夾，顯示所有影片
      filteredVideos.value = allVideos.value
      debugLog('🔍 未找到資料夾，顯示所有影片:', filteredVideos.value.length)
    }
  }
  
  debugLog('✅ 過濾完成，最終影片數量:', filteredVideos.value.length)
}

const refreshVideoList = async () => {
  debugLog(t('refreshVideoList'))
  videoLoading.value = true
  
  try {
    const response = await fetch('/api/videos')
    if (response.ok) {
      const data = await response.json()
      const existingMap = new Map((allVideos.value || []).map(v => [v.filename || v.name || v.path, v]))
        const normalizedVideos = (data.videos || []).map((video) => {
        const key = video.filename || video.name || video.path
        const existing = existingMap.get(key)
        const tmpType = video.tmpInfo?.type
        const backendHasResult = video.hasResult || tmpType === 'completed'
        const tmpDetail = video.tmpInfo?.detail || ''
        const tmpCurrentFile = video.tmpInfo?.current_file || ''
        const tmpElapsed = typeof video.tmpInfo?.elapsed_time === 'number' ? video.tmpInfo.elapsed_time : 0
        return {
          ...video,
          hasTmp: video.hasTmp || tmpType === 'processing',
          isProcessing: backendHasResult ? false : (existing?.isProcessing || tmpType === 'processing'),
          hasResult: existing?.hasResult || backendHasResult,
          hasFailed: existing?.hasFailed || false,
          isCancelled: existing?.isCancelled || false,
          progress: backendHasResult ? 100 : (existing?.progress || video.tmpInfo?.progress || 0),
          detail: existing?.detail || tmpDetail,
          current_file: existing?.current_file || tmpCurrentFile,
          elapsed_time: existing?.elapsed_time || tmpElapsed,
          runToken: existing?.runToken || ''
        }
      })
      allVideos.value = normalizedVideos
      filteredVideos.value = normalizedVideos
      
      // 基於實際數據初始化資料夾樹
      initializeFolderTree()
      
      ElMessage.success(`載入了 ${allVideos.value.length} 個影片`)
    } else {
      throw new Error('Failed to fetch videos')
    }
  } catch (error) {
    console.error(t('getVideoListFailed') + ':', error)
    ElMessage.error(t('getVideoListFailed'))
    filteredVideos.value = []
    folderTree.value = []
  } finally {
    videoLoading.value = false
  }
}

const syncProgressState = (jobId, events) => {
  const sorted = (events || [])
    .filter(item => item)
    .sort((a, b) => {
      const ta = Number(a.timestamp) || 0
      const tb = Number(b.timestamp) || 0
      return ta - tb
    })
    .slice(-PROGRESS_MAX_EVENTS)
  progressTimeline.value = {
    ...progressTimeline.value,
    [jobId]: sorted
  }
}

const addProgressEvent = (event) => {
  if (!event || !event.job_id) return
  const jobId = event.job_id
  const existing = progressTimeline.value[jobId] ? [...progressTimeline.value[jobId]] : []
  existing.push(event)
  syncProgressState(jobId, existing)
  lastProgressEventAt.value = Date.now()
  isProgressPolling.value = false
}

const fetchProgressSnapshot = async (jobId) => {
  if (!jobId) return
  try {
    const response = await fetch(`/api/progress/${encodeURIComponent(jobId)}?limit=${PROGRESS_MAX_EVENTS}`)
    if (!response.ok) {
      throw new Error(`progress snapshot failed: ${response.status}`)
    }
    const payload = await response.json()
    const events = Array.isArray(payload?.events) ? payload.events : []
    syncProgressState(jobId, events)
    if (events.length) {
      lastProgressEventAt.value = Date.now()
    }
  } catch (error) {
    debugWarn('⚠️ 無法取得進度快照:', error)
  }
}

const scheduleProgressReconnect = (delay = 5000) => {
  if (progressReconnectTimer) {
    return
  }
  progressReconnectTimer = window.setTimeout(() => {
    progressReconnectTimer = null
    connectProgressStream()
  }, delay)
}

const closeProgressStream = () => {
  if (progressSocket) {
    try {
      progressSocket.close()
    } catch (e) {
      debugWarn('關閉進度串流時發生錯誤', e)
    }
    progressSocket = null
  }
}

const connectProgressStream = () => {
  closeProgressStream()
  if (progressReconnectTimer) {
    clearTimeout(progressReconnectTimer)
    progressReconnectTimer = null
  }
  try {
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const wsUrl = `${protocol}://${window.location.host}/ws/progress`
    const socket = new WebSocket(wsUrl)
    progressSocket = socket
    socket.onopen = () => {
      progressStreamHealthy.value = true
    }
    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        addProgressEvent(data)
      } catch (err) {
        console.error('解析進度事件失敗:', err)
      }
    }
    socket.onclose = () => {
      progressStreamHealthy.value = false
      scheduleProgressReconnect()
    }
    socket.onerror = (err) => {
      console.error('進度串流錯誤:', err)
      progressStreamHealthy.value = false
      try {
        socket.close()
      } catch (e) {
        debugWarn('關閉錯誤的進度串流失敗', e)
      }
    }
  } catch (error) {
    console.error('建立進度串流失敗:', error)
    progressStreamHealthy.value = false
    scheduleProgressReconnect()
  }
}

const checkProgressHeartbeat = async () => {
  const jobId = activeProgressJobId.value
  if (!jobId) {
    isProgressPolling.value = false
    return
  }
  const now = Date.now()
  if (now - lastProgressEventAt.value > 15000) {
    isProgressPolling.value = true
    await fetchProgressSnapshot(jobId)
  } else {
    isProgressPolling.value = false
  }
}

const loadPaths = async () => {
  try {
    const response = await fetch('/api/get-paths')
    if (response.ok) {
      const data = await response.json()
      debugLog('📁 載入的路徑配置:', data)
      if (data.video_path) {
        videoFolderPath.value = data.video_path
        videoFolder.value = data.video_path
      }
      if (data.image_path) {
        imageFolderPath.value = data.image_path
      }
    }
  } catch (error) {
    console.error(t('getPathFailed') + ':', error)
  }
}

// 處理佇列管理
const processingQueue = ref([])
const maxConcurrentProcessing = 1 // 最多同時處理1個任務
const currentlyProcessing = ref(0)

const isCancelledStatus = (status) => {
  if (!status) return false
  const code = String(status.status_code || '').toLowerCase()
  const label = String(status.status || '').toLowerCase()
  return code === 'cancelled' || label.includes('取消') || label.includes('cancel')
}

const processVideo = async (video) => {
  debugLog('🎬 [processVideo] 函數被調用')
  debugLog('🎬 [processVideo] video 物件:', video)
  debugLog('🎬 [processVideo] video.path:', video.path)
  debugLog('🎬 [processVideo] video.filename:', video.filename)
  debugLog('🎬 [processVideo] video.name:', video.name)
  
  const filename = video.filename || video.name || t('unknownFile')
  debugLog('🎬 [processVideo] 解析後的 filename:', filename)
  
  // 檢查是否已在處理或達到最大並行數
  debugLog('🎬 [processVideo] currentlyProcessing.value:', currentlyProcessing.value)
  debugLog('🎬 [processVideo] maxConcurrentProcessing:', maxConcurrentProcessing)
  if (currentlyProcessing.value >= maxConcurrentProcessing) {
    debugLog('❌ [processVideo] 阻止: 達到最大並行數')
    ElMessage.warning('系統正在處理其他檔案，請稍候再試')
    return
  }
  
  debugLog('🎬 [processVideo] video.isProcessing:', video.isProcessing)
  if (video.isProcessing) {
    debugLog('❌ [processVideo] 阻止: 檔案正在處理中')
    ElMessage.warning('此檔案正在處理中，請稍候')
    return
  }
  
  debugLog('✅ [processVideo] 通過所有檢查,開始處理')
  debugLog(t('processVideo') + ':', filename)
  currentlyProcessing.value++
  video.isProcessing = true
    video.isCancelled = false
    video.hasFailed = false
    video.hasResult = false
    video.progress = 0
    video.detail = t('startProcessing') || '開始處理中...'
    video.current_file = ''
    video.elapsed_time = 0
  currentProcessingFilename.value = filename
  fetchProgressSnapshot(filename)
  ElMessage.info(t('startProcessingVideo', { filename }))

  try {
    // 強制重新處理：先嘗試刪除既有結果檔，忽略失敗
    await fetch(`/api/result/${encodeURIComponent(filename)}`, { method: 'DELETE' }).catch((err) => {
      debugWarn('刪除舊結果失敗或不存在，略過', err)
      return null
    })
    // 清空目前顯示的結果，避免顯示舊內容
    summaryResult.value = ''
    currentNoteStyle.value = 'detailed' // 使用卡片式渲染
    currentProcessedVideo.value = null

    const formData = new FormData()
    formData.append('video_path', video.path)
    formData.append('with_images', 'true')
    formData.append('device', device.value)
    formData.append('parse_audio', String(parseAudio.value))
    formData.append('language', effectiveLanguage.value)
    formData.append('note_style', normalizeNoteStyle(noteStyle.value))
    // 傳遞雙語開關，確保後端遵循使用者設定
    formData.append('include_japanese', includeJapanese.value)
    formData.append('language_mode', languageMode.value)
    // 唯一 run token，避免併發造成的舊結果誤載
    const runToken = `${Date.now()}_${Math.random().toString(36).slice(2,8)}`
    video.runToken = runToken
    formData.append('run_token', runToken)

    const response = await fetch('/api/process-video', {
      method: 'POST',
      body: formData
    })

    if (response.ok) {
      const result = await response.json()
      debugLog('處理開始:', result)

      // 開始輪詢狀態
      const pollStatus = async () => {
        try {
          const statusResponse = await fetch(`/api/status/${encodeURIComponent(filename)}`)
          if (statusResponse.ok) {
            const statusData = await statusResponse.json()
            debugLog('處理狀態:', statusData)
            // 若狀態屬於上一輪 run，直接忽略
            if (statusData && statusData.run_token && statusData.run_token !== runToken) {
              debugLog('忽略舊 run 狀態')
              setTimeout(pollStatus, 1500)
              return
            }

            // 詳細狀態日誌
            debugLog('📊 [pollStatus] 收到狀態:', {
              status: statusData.status,
              status_code: statusData.status_code,
              progress: statusData.progress,
              result_path: statusData.result_path
            })

            const videoDone = (statusData.status_code && statusData.status_code === 'completed') ||
                              statusData.status === '完成' || statusData.status === 'completed' || statusData.status === '完了'
            const cancelled = isCancelledStatus(statusData)
            const failed = (statusData.status_code && (statusData.status_code === 'error' || statusData.status_code === 'failed')) || statusData.status === '錯誤' || statusData.status === 'error'
            
            debugLog('🎯 [pollStatus] videoDone =', videoDone)
            
            if (videoDone) {
              video.isProcessing = false
              video.hasResult = true
              currentlyProcessing.value = Math.max(0, currentlyProcessing.value - 1) // 釋放處理位置
              currentProcessingFilename.value = ''
              ElMessage.success(t('processComplete'))

              debugLog('✅ [pollStatus] 影片處理完成,準備載入結果')
              debugLog('✅ [pollStatus] statusData.result_path:', statusData.result_path)

              // 自動載入結果
              if (statusData.result_path) {
                debugLog('✅ [pollStatus] 呼叫 loadVideoResult')
                await loadVideoResult(video)
              } else {
                debugWarn('⚠️ [pollStatus] statusData 中無 result_path,嘗試直接載入')
                await loadVideoResult(video)
              }
            } else if (cancelled) {
              video.isProcessing = false
              video.isCancelled = true
              video.hasFailed = false
              video.progress = statusData.progress || 0
              currentlyProcessing.value = Math.max(0, currentlyProcessing.value - 1) // 釋放處理位置
              currentProcessingFilename.value = ''
              ElMessage.warning(t('taskCancelled') || '任務已取消')
            } else if (failed) {
              video.isProcessing = false
              video.hasFailed = true
              video.isCancelled = false
              currentlyProcessing.value = Math.max(0, currentlyProcessing.value - 1) // 釋放處理位置
              currentProcessingFilename.value = ''
              
              // 詳細錯誤信息
              const errorMessage = statusData.detail || statusData.error || '未知錯誤'
              console.error('處理失敗詳細信息:', {
                status: statusData.status,
                status_code: statusData.status_code,
                detail: statusData.detail,
                error: statusData.error,
                full_status: statusData
              })
              
              ElMessage.error(t('processFailed') + ': ' + errorMessage)
            } else {
              // 更新進度百分比（若後端提供 progress）
              if (typeof statusData.progress === 'number') {
                video.progress = statusData.progress
              }
              if (typeof statusData.elapsed_time === 'number') {
                video.elapsed_time = statusData.elapsed_time
              }
              // 更新詳細狀態文字
              if (statusData.detail) {
                video.detail = statusData.detail
              }
              if (statusData.current_file) {
                video.current_file = statusData.current_file
              }
              // 繼續輪詢
              setTimeout(pollStatus, 2000)
            }
          }
        } catch (error) {
          console.error('狀態輪詢錯誤:', error)
          setTimeout(pollStatus, 3000)
        }
      }

      // 開始輪詢（延遲稍長，避免讀到快取文件）
      setTimeout(pollStatus, 2000)

    } else {
      throw new Error('Processing failed')
    }
  } catch (error) {
    console.error(t('processVideoFailed') + ':', error)
    video.isProcessing = false
    video.hasFailed = true
    video.isCancelled = false
    currentlyProcessing.value = Math.max(0, currentlyProcessing.value - 1)
    currentProcessingFilename.value = ''
    ElMessage.error(t('processFailed'))
  }
}

const processAllVideos = async () => {
  const unprocessedVideos = filteredVideos.value.filter(v => !v.hasResult && !v.isProcessing)
  if (unprocessedVideos.length === 0) {
    ElMessage.warning(t('noPendingVideos'))
    return
  }
  
  isProcessing.value = true
  ElMessage.info(t('startBatchProcessVideos', { count: unprocessedVideos.length }))
  
  // 批次處理：逐一處理，等待前一個完成後再開始下一個
  let processedCount = 0
  let failedCount = 0
  const totalCount = unprocessedVideos.length
  
  for (const video of unprocessedVideos) {
    const filename = video.filename || video.name
    debugLog(`🎬 [批次處理] 開始處理 ${processedCount + 1}/${totalCount}: ${filename}`)
    
    try {
      // 等待當前影片處理完成
      await processVideoAndWaitFixed(video)
      processedCount++
      debugLog(`✅ [批次處理] 完成 ${processedCount}/${totalCount}: ${filename}`)
      ElMessage.success(`已處理 ${processedCount}/${totalCount} 個影片`)
    } catch (error) {
      failedCount++
      console.error(`❌ [批次處理] 失敗 (${processedCount + failedCount}/${totalCount}):`, filename, error)
      ElMessage.error(`影片處理失敗: ${filename} - ${error.message}`)
      // 繼續處理下一個影片
    }
  }
  
  isProcessing.value = false
  
  // 顯示最終結果
  if (failedCount === 0) {
    ElMessage.success(`批量處理完成！成功處理全部 ${processedCount} 個影片`)
  } else {
    ElMessage.warning(`批量處理完成！成功 ${processedCount} 個，失敗 ${failedCount} 個，共 ${totalCount} 個影片`)
  }
}

// 修復版：等待影片處理完成（不依賴 processVideo 的內部輪詢）
const processVideoAndWaitFixed = (video) => {
  return new Promise((resolve, reject) => {
    const filename = video.filename || video.name
    
    debugLog(`🔄 [processVideoAndWaitFixed] 開始處理: ${filename}`)
    
    // 使用 IIFE 處理 async 邏輯
    ;(async () => {
      // 檢查是否已在處理中
      if (video.isProcessing) {
        debugLog(`⚠️ [processVideoAndWaitFixed] 影片已在處理中，等待完成: ${filename}`)
        // 直接進入輪詢等待
      } else {
        // 手動設定處理狀態（繞過 processVideo 的同時處理限制）
        debugLog(`🎬 [processVideoAndWaitFixed] 設定處理狀態: ${filename}`)
        video.isProcessing = true
        video.isCancelled = false
        video.hasFailed = false
        video.hasResult = false
        video.progress = 0
        video.detail = t('startProcessing') || '開始處理中...'
        video.current_file = ''
        video.elapsed_time = 0
        currentProcessingFilename.value = filename
        
        try {
          // 發送處理請求
          debugLog(`📤 [processVideoAndWaitFixed] 發送 API 請求: ${filename}`)
          
          const formData = new FormData()
          formData.append('video_path', video.path)
          formData.append('with_images', 'true')
          formData.append('device', device.value)
          formData.append('parse_audio', String(parseAudio.value))
          formData.append('language', effectiveLanguage.value)
    formData.append('note_style', normalizeNoteStyle(noteStyle.value))
          formData.append('include_japanese', includeJapanese.value)
          formData.append('language_mode', languageMode.value)
          
          const runToken = `${Date.now()}_${Math.random().toString(36).slice(2,8)}`
          video.runToken = runToken
          formData.append('run_token', runToken)
          
          const response = await fetch('/api/process-video', {
            method: 'POST',
            body: formData
          })
          
          if (!response.ok) {
            const errorText = await response.text()
            throw new Error(`API 請求失敗 (${response.status}): ${errorText}`)
          }
          
          const result = await response.json()
          debugLog(`✅ [processVideoAndWaitFixed] API 回應成功:`, result)
          
        } catch (error) {
          debugLog(`❌ [processVideoAndWaitFixed] API 請求失敗:`, error)
          video.isProcessing = false
          video.hasFailed = true
          reject(error)
          return
        }
      }
      
      // 輪詢檢查影片狀態
      debugLog(`🔍 [processVideoAndWaitFixed] 開始輪詢狀態: ${filename}`)
      let pollCount = 0
      const maxPolls = 900 // 30分鐘 = 900次 (每2秒)
      
      const checkInterval = setInterval(async () => {
        pollCount++
        
        if (pollCount > maxPolls) {
          clearInterval(checkInterval)
          video.isProcessing = false
          video.hasFailed = true
          reject(new Error(`處理超時 (${maxPolls * 2}秒)`))
          return
        }
        
        try {
          const statusResponse = await fetch(`/api/status/${encodeURIComponent(filename)}`)
          
          if (!statusResponse.ok) {
            debugLog(`⚠️ [processVideoAndWaitFixed] 狀態查詢失敗 (${pollCount}/${maxPolls}): ${statusResponse.status}`)
            return // 繼續輪詢
          }
          
          const statusData = await statusResponse.json()
          
          // 更新進度
          if (typeof statusData.progress === 'number') {
            video.progress = statusData.progress
          }
          if (typeof statusData.elapsed_time === 'number') {
            video.elapsed_time = statusData.elapsed_time
          }
          if (statusData.detail) {
            video.detail = statusData.detail
          }
          if (statusData.current_file) {
            video.current_file = statusData.current_file
          }
          
          const done = (statusData.status_code === 'completed') ||
                       statusData.status === '完成' || statusData.status === 'completed' || statusData.status === '完了'
          const failed = (statusData.status_code === 'error' || statusData.status_code === 'failed') ||
                         statusData.status === '錯誤' || statusData.status === 'error'
          const cancelled = isCancelledStatus(statusData)
          
          if (done) {
            debugLog(`✅ [processVideoAndWaitFixed] 處理完成 (輪詢 ${pollCount} 次): ${filename}`)
            clearInterval(checkInterval)
            video.isProcessing = false
            video.hasResult = true
            
            // 載入結果
            try {
              await loadVideoResult(video)
            } catch (loadError) {
              debugWarn('載入結果失敗，但處理已完成:', loadError)
            }
            
            resolve()
          } else if (failed || cancelled) {
            debugLog(`❌ [processVideoAndWaitFixed] 處理失敗或取消 (輪詢 ${pollCount} 次): ${filename}`)
            clearInterval(checkInterval)
            video.isProcessing = false
            video.hasFailed = failed
            video.isCancelled = cancelled
            reject(new Error(statusData.detail || statusData.error || '處理失敗'))
          } else {
            // 繼續輪詢
            if (pollCount % 10 === 0) {
              debugLog(`🔄 [processVideoAndWaitFixed] 處理中 (輪詢 ${pollCount} 次, 進度 ${video.progress || 0}%): ${filename}`)
            }
          }
        } catch (error) {
          debugWarn(`⚠️ [processVideoAndWaitFixed] 輪詢錯誤 (${pollCount}/${maxPolls}):`, error)
          // 不中斷，繼續輪詢
        }
      }, 2000) // 每 2 秒檢查一次
    })() // 立即執行 async 函數
  })
}

const loadVideoResult = async (video) => {
  const filename = video.filename || video.name || t('unknownFile')
  
  try {
    const apiUrl = `/api/result/${encodeURIComponent(filename)}`
    const response = await fetch(apiUrl)
    
    if (response.ok) {
      const result = await response.json()
      currentProcessedVideo.value = video
      const noteStyle = result?.structured?.noteStyle || (result?.structured?.isVlmNote ? 'blueprint' : 'legacy')
      currentNoteStyle.value = noteStyle || 'legacy'
      
      // Transcript 筆記直接使用後端 Markdown
      if (noteStyle === 'transcript') {
        summaryResult.value = result.content || result.summary || t('noResultFound')
      } else if (result && result.structured && result.structured.useMarkdown === true) {
        summaryResult.value = result.content || result.summary || t('noResultFound')
      } else if (result && result.structured) {
        try {
          summaryResult.value = buildMarkdownFromStructured(result.structured, filename)
        } catch (e) {
          debugWarn('[loadVideoResult] structured->markdown 失敗,使用原始內容:', e)
          summaryResult.value = result.content || result.summary || t('noResultFound')
        }
      } else {
        summaryResult.value = result.content || result.summary || t('noResultFound')
      }
      // 前端立即使用最新渲染（不影響後端）
      rerenderTick.value += 1
      
      ElMessage.success(t('loadedResult', { filename }))
      
      // 自動滾動到結果區域
      await nextTick()
      if (resultSectionEl.value) {
        resultSectionEl.value.scrollIntoView({ behavior: 'smooth' })
      }
    } else {
      const errorText = await response.text()
      console.error('🔴 [loadVideoResult] API 回應失敗:', response.status, errorText)
      throw new Error(`Failed to load result: ${response.status} ${errorText}`)
    }
  } catch (error) {
    console.error('🔴 [loadVideoResult] 載入失敗:', error)
    ElMessage.error(t('loadResultFailed') + `: ${filename}`)
    currentNoteStyle.value = 'detailed' // 使用卡片式渲染
  }
}

const checkProgress = async (video) => {
  debugLog(t('checkProgress') + ':', video.name)
  try {
    const filename = video.filename || video.name
    const res = await fetch(`/api/status/${encodeURIComponent(filename)}`)
    if (!res.ok) throw new Error('status fetch failed')
    const statusData = await res.json()
    const done = (statusData.status_code && statusData.status_code === 'completed') ||
                 statusData.status === '完成' || statusData.status === 'completed' || statusData.status === '完了'
    const failed = (statusData.status_code && (statusData.status_code === 'error' || statusData.status_code === 'failed')) ||
                   statusData.status === '錯誤' || statusData.status === 'error'
    const cancelled = isCancelledStatus(statusData)
    if (done) {
      video.isProcessing = false
      video.hasResult = true
      ElMessage.success(t('processComplete'))
    } else if (failed) {
      video.isProcessing = false
      video.hasFailed = true
      ElMessage.error(t('processFailed') + (statusData.detail ? `: ${statusData.detail}` : ''))
    } else if (cancelled) {
      video.isProcessing = false
      video.isCancelled = true
      video.hasFailed = false
      video.progress = statusData.progress || 0
      currentlyProcessing.value = Math.max(0, currentlyProcessing.value - 1)
      currentProcessingFilename.value = ''
      ElMessage.warning(t('taskCancelled') || '任務已取消')
    } else {
      // 更新進度百分比（若後端提供 progress）
      if (typeof statusData.progress === 'number') {
        video.progress = statusData.progress
      }
      if (typeof statusData.elapsed_time === 'number') {
        video.elapsed_time = statusData.elapsed_time
      }
      if (statusData.detail) {
        video.detail = statusData.detail
      }
      if (statusData.current_file) {
        video.current_file = statusData.current_file
      }
      // 顯示正在檢查提示
      ElMessage.info(t('checkingProgress'))
    }
  } catch (e) {
    console.error('checkProgress error:', e)
    ElMessage.error(t('getStatusFailed') || '獲取狀態失敗')
  }
}

const cancelVideoProcessing = async (video) => {
  const filename = video.filename || video.name
  if (!filename) return
  try {
    await ElMessageBox.confirm(
      t('confirmCancelTask') || '確定要取消當前的處理任務嗎？',
      t('cancelProcessing') || '取消處理',
      {
        confirmButtonText: t('confirmCancelButton') || t('confirm'),
        cancelButtonText: t('continueProcessing') || t('cancel'),
        type: 'warning'
      }
    )
  } catch {
    return
  }

  try {
    const tokenQuery = video.runToken ? `?run_token=${encodeURIComponent(video.runToken)}` : ''
    const res = await fetch(`/api/cancel-task/${encodeURIComponent(filename)}${tokenQuery}`, { method: 'DELETE' })
    const payload = res.ok ? await res.json() : null
    if (res.ok && payload?.status === 'cancelled') {
      video.isProcessing = false
      video.isCancelled = true
      video.hasFailed = false
      video.progress = 0
      currentlyProcessing.value = Math.max(0, currentlyProcessing.value - 1)
      currentProcessingFilename.value = ''
      ElMessage.success(t('taskCancelledSuccessfully') || '任務取消成功')
    } else {
      throw new Error(payload?.message || `cancel failed (${res.status})`)
    }
  } catch (error) {
    console.error('取消影片處理失敗:', error)
    ElMessage.error(t('cancelTaskFailed') || '取消任務失敗')
  }
}

// --- Structured result -> Markdown transformer (defensive)
function buildMarkdownFromStructured(structured, fallbackTitle) {
  const note = Array.isArray(structured) ? { sections: structured } : (structured || {})
  const meta = note.meta || {}
  const title = meta.title || note.title || note.courseName || fallbackTitle || 'Note'
  const parts = [`# ${title}`]

  const metaLines = []
  if (meta.analyzed_at) metaLines.push(`- Date: ${new Date(meta.analyzed_at).toLocaleString()}`)
  if (note.date) metaLines.push(`- Date: ${note.date}`)
  if (meta.lang || meta.language) metaLines.push(`- Lang: ${meta.lang || meta.language}`)
  if (Array.isArray(meta.source)) metaLines.push(`- Sources: ${meta.source.length}`)
  if (typeof meta.sceneCount === 'number') metaLines.push(`- Scenes: ${meta.sceneCount}`)
  if (metaLines.length) parts.push(metaLines.join('\n'))

  const quality = note.quality || 'unknown'
  const rawScenes = Array.isArray(note.sceneSummaries)
    ? note.sceneSummaries
    : Array.isArray(note.scene_summaries)
      ? note.scene_summaries
      : []
  const sceneSummaries = dedupeScenes(rawScenes)
  const isLowQuality = (quality === 'poor' || quality === 'fair') && sceneSummaries.length === 0

  if (isLowQuality) {
    debugLog('🟡 [buildMarkdownFromStructured] 低品質降級輸出', { quality, message: note.message })
    parts.push('## ⚠️ 資料品質提示')
    if (note.message) parts.push(note.message)
    parts.push(`- 等級: **${quality}**`)
    if (Array.isArray(note.tips) && note.tips.length) {
      parts.push('\n## 💡 系統建議')
      note.tips.forEach(tip => parts.push(`- ${tip}`))
    }
    if (typeof note.ocrText === 'string' && note.ocrText.trim()) {
      const ocrLines = note.ocrText
        .split('\n')
        .map(line => line.trim())
        .filter(Boolean)
      parts.push('\n## 📝 OCR 擷取內容')
      ocrLines.slice(0, 50).forEach(line => parts.push(`- ${line}`))
      if (ocrLines.length > 50) parts.push(`... (尚有 ${ocrLines.length - 50} 行未顯示)`)
    } else {
      parts.push('\n## 📝 OCR 狀態\n- ❌ 未能提取講義文字')
    }
    parts.push('\n## 🔧 改善建議')
    parts.push('- 請確認影片中包含清晰的講義或投影片截圖')
    parts.push('- 可以重新上傳較高畫質的影片或 PDF')
    parts.push('- 確保畫面中文字尺寸足夠、對比度清晰')
    return parts.join('\n\n') + '\n'
  }

  if (Array.isArray(note.summary) && note.summary.length) {
    parts.push('## 🎯 課程重點')
    note.summary.forEach(item => parts.push(`- ${String(item).trim()}`))
  }

  if (Array.isArray(note.notes) && note.notes.length) {
    const secondaryLabel = note.secondary_label || '翻譯'
    parts.push(`## 📝 雙語重點整理（日文 + ${secondaryLabel})`)
    note.notes.forEach(entry => {
      if (!entry) return
      const original = entry.original ? `**${entry.original.trim()}**` : ''
      const explanation = entry.explanation ? entry.explanation.trim() : ''
      if (original || explanation) {
        const lines = [original, explanation].filter(Boolean)
        parts.push(`- ${lines.join(' — ')}`)
      }
      if (Array.isArray(entry.supplements) && entry.supplements.length) {
        entry.supplements.forEach(sup => parts.push(`  - ${sup}`))
      }
    })
  }


  if (Array.isArray(note.tips) && note.tips.length && !isLowQuality) {
    parts.push('## 💡 學習建議')
    note.tips.forEach(tip => parts.push(`- ${tip}`))
  }

  if (sceneSummaries.length) {
    parts.push('## 📽️ 場景精華')
    sceneSummaries.forEach((scene, idx) => {
      if (!scene) return
      const titleBits = [`場景 ${idx + 1}`]
      const focus = scene.focus || scene.visual_focus
      const shortSummary = extractSceneHeadline(scene.summary || scene.asr || scene.ocr)
      if (focus) titleBits.push(focus)
      else if (shortSummary) titleBits.push(shortSummary)
      parts.push(`### ${titleBits.join('｜')}`)

      const timing = []
      if (Number.isFinite(scene.start)) timing.push(`起點 ${formatSeconds(scene.start)}`)
      if (Number.isFinite(scene.end)) timing.push(`終點 ${formatSeconds(scene.end)}`)
      if (Number.isFinite(scene.duration)) timing.push(`時長 ${formatSeconds(scene.duration)}`)
      if (timing.length) parts.push(`<div class="scene-timestamp">⏱️ ${timing.join(' ｜ ')}</div>`)

      if (scene.image) {
        parts.push(`![場景 ${idx + 1}](${scene.image})`)
      }
      const cleanedSummary = normalizeSceneSummary(scene.summary)
      if (cleanedSummary) parts.push(cleanedSummary)

      if (Array.isArray(scene.jpTopLines) && scene.jpTopLines.length) {
        parts.push('**📘 日文關鍵句**')
        scene.jpTopLines.forEach(line => parts.push(`- ${line}`))
      }
      if (scene.asr && scene.asr.trim()) {
        parts.push('**🎙️ 語音精選**')
        parts.push(`> ${scene.asr.trim()}`)
      }
    })
  }

  if (Array.isArray(note.terms) && note.terms.length) {
    const secondaryLabel = note.secondary_label || '翻譯'
    parts.push('## 📚 術語對照')
    parts.push(`| 日文 | ${secondaryLabel} |`)
    parts.push('| --- | --- |')
    note.terms.forEach(term => {
      if (!term) return
      parts.push(`| ${term.jp || ''} | ${term.secondary || term.zh || term.tw || ''} |`)
    })
  }

  if (note.code && (note.code.code || (Array.isArray(note.code.snippets) && note.code.snippets.length))) {
    parts.push('## 💻 參考程式碼')
    if (note.code.title) parts.push(`### ${note.code.title}`)
    if (note.code.code) {
      const lang = normalizeCodeLang(note.code.lang)
      parts.push('```' + lang)
      parts.push(String(note.code.code).trim())
      parts.push('```')
    }
    if (Array.isArray(note.code.snippets)) {
      note.code.snippets.forEach(snippet => {
        const lang = normalizeCodeLang(snippet.lang)
        if (snippet.title) parts.push(`#### ${snippet.title}`)
        if (snippet.code) {
          parts.push('```' + lang)
          parts.push(String(snippet.code).trim())
          parts.push('```')
        }
        if (snippet.explain) parts.push(snippet.explain)
      })
    }
    if (Array.isArray(note.codeExplain)) {
      note.codeExplain.forEach(explain => parts.push(`- ${explain}`))
    }
  }

  if (Array.isArray(note.qa) && note.qa.length) {
    parts.push('## ❓ 測驗題')
    note.qa.forEach((item, qIdx) => {
      if (!item) return
      parts.push(`### 題目 ${qIdx + 1}`)
      if (item.q) parts.push(item.q)
      if (Array.isArray(item.options)) {
        item.options.forEach((opt, oIdx) => parts.push(`- ${(oIdx + 10).toString(36).toUpperCase()}. ${opt}`))
      }
      if (typeof item.answer !== 'undefined') {
        parts.push(`> ✅ 答案: ${(item.answer + 10).toString(36).toUpperCase()}`)
      }
      if (Array.isArray(item.grounding) && item.grounding.length) {
        parts.push('> 📎 根據：')
        item.grounding.forEach(ref => parts.push(`> - ${ref}`))
      }
    })
  }

  const sections = Array.isArray(note.sections) ? note.sections : []
  if (sections.length) {
    parts.push('## 🧩 額外內容')
    sections.forEach(section => renderLegacySection(section, parts))
  }

  return parts.join('\n\n') + '\n'

  function dedupeScenes(scenes) {
    const seen = new Set()
    const result = []
    const normalizeTime = value => {
      if (!Number.isFinite(value)) return ''
      return Math.round(value * 10) / 10 // keep 0.1s precision
    }

    for (const scene of scenes || []) {
      if (!scene) continue
      const parts = []
      if (scene.image) parts.push(`img:${scene.image}`)
      const summarySnippet = (scene.summary || '').slice(0, 80).trim()
      if (summarySnippet) parts.push(`txt:${summarySnippet}`)
      if (Number.isFinite(scene.index)) parts.push(`idx:${scene.index}`)
      const startKey = normalizeTime(scene.start)
      const endKey = normalizeTime(scene.end)
      const durationKey = normalizeTime(scene.duration)
      if (startKey !== '') parts.push(`s:${startKey}`)
      if (endKey !== '') parts.push(`e:${endKey}`)
      if (durationKey !== '') parts.push(`d:${durationKey}`)

      const dedupeKey = parts.length ? parts.join('|') : `fallback:${result.length}`
      if (seen.has(dedupeKey)) continue
      seen.add(dedupeKey)
      result.push(scene)
    }
    return result
  }

  function normalizeSceneSummary(summary) {
    if (!summary || typeof summary !== 'string') return ''
    return summary
      .replace(/^[#]+\s?/gm, '') // remove repeated heading markers
      .replace(/\n{3,}/g, '\n\n')
      .trim()
  }

  function extractSceneHeadline(summary) {
    if (!summary || typeof summary !== 'string') return ''
    const firstLine = summary
      .split('\n')
      .map(line => line.replace(/^[#*\-•\s]+/, '').trim())
      .find(Boolean)
    return firstLine ? firstLine.slice(0, 36) : ''
  }

  function formatSeconds(sec) {
    if (!Number.isFinite(sec)) return ''
    const total = Math.max(0, Math.round(sec))
    const hours = Math.floor(total / 3600)
    const minutes = Math.floor((total % 3600) / 60)
    const seconds = total % 60
    if (hours) return `${hours}h${String(minutes).padStart(2, '0')}m${String(seconds).padStart(2, '0')}s`
    if (minutes) return `${minutes}m${String(seconds).padStart(2, '0')}s`
    return `${seconds}s`
  }

  function normalizeCodeLang(lang) {
    if (!lang) return 'plaintext'
    const normalized = String(lang).toLowerCase()
    if (normalized === 'text') return 'plaintext'
    if (normalized === 'c#') return 'csharp'
    if (normalized === 'js') return 'javascript'
    if (normalized === 'ts') return 'typescript'
    return normalized
  }

  function renderLegacySection(section, buffer) {
    if (!section) return
    const sectionTitle = section.title || section.id || ''
    if (sectionTitle) buffer.push(`### ${sectionTitle}`)

    const type = inferSectionType(section)
    if (type === 'bullets' && Array.isArray(section.items)) {
      section.items.forEach(item => {
        if (!item) return
        const jp = item.jp ? `JP: ${item.jp}` : ''
        const tw = item.tw ? `TW: ${item.tw}` : ''
        const line = [jp, tw].filter(Boolean).join(' ｜ ')
        if (line) buffer.push(`- ${line}`)
      })
      return
    }

    if (type === 'paragraphs' && Array.isArray(section.blocks)) {
      section.blocks.forEach(block => {
        if (!block) return
        const text = block.jp && block.tw ? `${block.jp}\n\n${block.tw}` : (block.tw || block.jp || '')
        if (text) buffer.push(text)
      })
      return
    }

    if (type === 'code-list' && Array.isArray(section.items)) {
      const lang = normalizeCodeLang(section.language)
      section.items.forEach(item => {
        if (!item) return
        if (item.title) buffer.push(`#### ${item.title}`)
        if (item.code) {
          buffer.push('```' + lang)
          buffer.push(String(item.code))
          buffer.push('```')
        }
        if (item.explain_tw || item.explain_jp) {
          buffer.push(item.explain_tw || item.explain_jp)
        }
      })
      return
    }

    if ((type === 'table' || type === 'qa' || type === 'problems') && Array.isArray(section.items)) {
      section.items.forEach(item => {
        if (!item) return
        const left = item.left || item.q || ''
        const right = item.right || item.a || ''
        if (left || right) buffer.push(`- ${left} -> ${right}`)
      })
      return
    }

    if (Array.isArray(section.lines)) {
      section.lines.forEach(line => buffer.push(String(line)))
    } else if (typeof section.text === 'string') {
      buffer.push(section.text)
    }
  }
}

function inferSectionType(section) {
  if (Array.isArray(section.items)) {
    if (section.items.every(it => typeof it?.code !== 'undefined')) return 'code-list'
    return 'bullets'
  }
  if (Array.isArray(section.blocks)) return 'paragraphs'
  return 'bullets'
}

// 單一影片卡片刷新狀態
const refreshSingleVideo = async (video) => {
  try {
    const filename = video.filename || video.name
    const res = await fetch(`/api/status/${encodeURIComponent(filename)}`)
    if (!res.ok) {
      ElMessage.error(t('getStatusFailed') || '獲取狀態失敗')
      return
    }

    const status = await res.json()
    const done = (status.status_code && status.status_code === 'completed') ||
                 status.status === '完成' || status.status === 'completed' || status.status === '完了'
    const failed = (status.status_code && (status.status_code === 'error' || status.status_code === 'failed')) ||
                   status.status === '錯誤' || status.status === 'error'
    const cancelled = isCancelledStatus(status)

    if (done) {
      video.isProcessing = false
      video.hasFailed = false
      video.isCancelled = false
      video.hasResult = true
      await loadVideoResult(video)
    } else if (failed) {
      video.isProcessing = false
      video.hasResult = false
      video.hasFailed = true
      video.isCancelled = false
      ElMessage.error(t('processFailed'))
    } else if (cancelled) {
      video.isProcessing = false
      video.isCancelled = true
      video.hasFailed = false
      video.hasResult = false
      video.progress = status.progress || 0
      currentlyProcessing.value = Math.max(0, currentlyProcessing.value - 1)
      currentProcessingFilename.value = ''
      ElMessage.warning(t('taskCancelled') || '任務已取消')
    } else {
      // 只做靜默刷新，不彈出太多提示
      if (typeof status.progress === 'number') {
        video.progress = status.progress
      }
      if (typeof status.elapsed_time === 'number') {
        video.elapsed_time = status.elapsed_time
      }
      if (status.detail) {
        video.detail = status.detail
      }
      if (status.current_file) {
        video.current_file = status.current_file
      }
      debugLog('影片仍在處理中，狀態刷新完成')
    }
  } catch (e) {
    console.error('refreshSingleVideo error:', e)
    ElMessage.error(t('getStatusFailed') || '獲取狀態失敗')
  }
}

const retryVideo = (video) => {
  debugLog(t('retryVideo') + ':', video.name)
  video.hasFailed = false
  video.isProcessing = true
  video.isCancelled = false
  ElMessage.info(`重新處理: ${video.name}`)
}

const showVideoDetails = (video) => {
  debugLog(t('showVideoDetails') + ':', video.name)
  const filename = video.filename || video.name || t('unknownFile')
  const durationText = formatDuration(video.duration)
  const sizeText = formatFileSize(video.size)
  const pathText = video.path || '-'

  // 使用結構化的 HTML 呈現，提升可讀性
  const detailsHtml = `
    <div style="display:flex;flex-direction:column;gap:8px;line-height:1.6;">
      <div><strong>檔案</strong><br>${escapeHtml(filename)}</div>
      <div><strong>路徑</strong><br><code>${escapeHtml(pathText)}</code></div>
      <div style="display:flex;gap:16px;">
        <div><strong>${t('duration') || '時長'}</strong><br>${escapeHtml(durationText)}</div>
        <div><strong>${t('fileSize') || '大小'}</strong><br>${escapeHtml(sizeText)}</div>
      </div>
    </div>`

  ElMessageBox.alert(
    detailsHtml,
    filename,
    { confirmButtonText: t('confirm'), dangerouslyUseHTMLString: true }
  )
}

function openBiliNoteDialog() {
  // 盡量自動導向：優先使用當前處理結果的 doc_id
  const autoId = currentProcessedVideo.value?.tmpInfo?.doc_id || currentProcessedVideo.value?.doc_id
  if (autoId && String(autoId).trim()) {
    const id = String(autoId).trim()
    try { localStorage.setItem('last_doc_id', id) } catch(_) {}
    window.location.href = `/bili/${id}`
    return
  }
  // 如果沒有doc_id，直接跳轉到BiliNote首頁
  window.location.href = '/bili'
}

function goToBiliNote() {
  if (!biliNoteId.value.trim()) {
    ElMessage.error('請輸入 doc_id')
    return
  }
  showBiliNoteDialog.value = false
  const id = biliNoteId.value.trim()
  try { localStorage.setItem('last_doc_id', id) } catch(_) {}
  // 跳轉到新的 BiliNote 頁面
  window.location.href = `/bili/${id}`
}

const clearResults = () => {
  summaryResult.value = ''
  currentProcessedVideo.value = null
  markdownDiagnostics.value = null
  currentNoteStyle.value = 'legacy'
  rerenderTick.value = 0
  ElMessage.success(t('resultsCleared'))
}

// 僅前端重新渲染，不觸發後端重算
const rerenderMarkdown = () => {
  if (!summaryResult.value) return
  rerenderTick.value += 1
  ElMessage.info('已在前端重新渲染（未呼叫後端）')
}

const onNoteSaved = () => {
  ElMessage.success(t('noteSaved'))
  showSaveDialog.value = false
}

// Watch summaryResult and trigger markdown rendering
watch(summaryResult, (value) => {
  if (value) {
    console.log('[Home.vue] summaryResult changed, triggering updateMarkdownFallback, length:', value.length)
    updateMarkdownFallback(value)
  }
}, { immediate: true })


// 時間格式化函數
const formatDuration = (duration) => {
  if (!duration) return t('unknown')
  
  if (typeof duration === 'string' && duration.includes(':')) {
    // 解析 HH:MM:SS 或 MM:SS 格式
    const parts = duration.split(':').map(p => parseInt(p))
    if (parts.length === 3) {
      const [hours, minutes, seconds] = parts
      if (hours > 0) {
        return `${hours}小時 ${minutes}分鐘 ${seconds}秒`
      } else if (minutes > 0) {
        return `${minutes}分鐘 ${seconds}秒`
      } else {
        return `${seconds}秒`
      }
    } else if (parts.length === 2) {
      const [minutes, seconds] = parts
      if (minutes > 0) {
        return `${minutes}分鐘 ${seconds}秒`
      } else {
        return `${seconds}秒`
      }
    }
    return duration
  }
  
  if (typeof duration === 'number') {
    const hours = Math.floor(duration / 3600)
    const minutes = Math.floor((duration % 3600) / 60)
    const seconds = Math.floor(duration % 60)
    
    if (hours > 0) {
      return `${hours}小時 ${minutes}分鐘 ${seconds}秒`
    } else if (minutes > 0) {
      return `${minutes}分鐘 ${seconds}秒`
    } else {
      return `${seconds}秒`
    }
  }
  
  return duration.toString()
}

// 轉換檔案大小為人類可讀格式
const formatFileSize = (size) => {
  if (size === undefined || size === null || isNaN(Number(size))) return t('unknown')
  const bytes = Number(size)
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let idx = 0
  let val = bytes
  while (val >= 1024 && idx < units.length - 1) {
    val /= 1024
    idx += 1
  }
  const fixed = val >= 100 ? val.toFixed(0) : val >= 10 ? val.toFixed(1) : val.toFixed(2)
  return `${fixed} ${units[idx]}`
}

// 簡單的HTML轉義，避免特殊字元破壞排版
const escapeHtml = (str) => {
  if (str === undefined || str === null) return ''
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

// 圖片資料夾處理相關函數
const refreshImageFolders = async () => {
  debugLog('🔄 刷新圖片資料夾列表')
  imageLoading.value = true
  
  try {
    const response = await fetch('/api/images')
    if (response.ok) {
      const data = await response.json()
      debugLog('📥 API返回的圖片數據:', data)
      
      // 直接使用後端返回的folders數據，如果存在的話
      if (data.folders && data.folders.length > 0) {
        imageFolders.value = data.folders.map(folder => ({
          name: folder.name,
          path: folder.path,
          images: folder.images,
          image_count: folder.image_count,
          hasResult: folder.has_combined_result || false,
          isProcessing: false,
          hasFailed: false,
          status: folder.has_combined_result ? 'completed' : 'pending'
        }))
        allImageFolders.value = imageFolders.value
        debugLog('📁 載入的資料夾:', imageFolders.value)
        ElMessage.success(`載入了 ${imageFolders.value.length} 個圖片資料夾`)
      } else if (data.images && data.images.length > 0) {
        // 如果沒有folders數據，則從images數據中構建
        const folderMap = new Map()
        
        data.images.forEach(image => {
          const folderPath = image.folder || ''
          const folderKey = folderPath || 'root'
          
          if (!folderMap.has(folderKey)) {
            folderMap.set(folderKey, {
              name: folderPath || '根目錄',
              path: folderPath,
              images: [],
              image_count: 0,
              hasResult: false,
              isProcessing: false,
              hasFailed: false,
              status: 'pending'
            })
          }
          folderMap.get(folderKey).images.push(image)
          folderMap.get(folderKey).image_count++
        })
        
        allImageFolders.value = Array.from(folderMap.values())
        imageFolders.value = allImageFolders.value
        debugLog('📁 從圖片數據構建的資料夾:', imageFolders.value)
        ElMessage.success(`載入了 ${imageFolders.value.length} 個圖片資料夾`)
      } else {
        imageFolders.value = []
        ElMessage.info('沒有找到圖片資料夾')
      }
    } else {
      throw new Error('Failed to fetch image folders')
    }
  } catch (error) {
    console.error('❌ 獲取圖片資料夾失敗:', error)
    ElMessage.error('獲取圖片資料夾失敗')
    imageFolders.value = []
  } finally {
    imageLoading.value = false
  }
}

const processFolder = async (folder) => {
  const folderName = folder.name || t('unknownFolder')
  
  // 檢查是否已在處理或達到最大並行數
  if (currentlyProcessing.value >= maxConcurrentProcessing) {
    ElMessage.warning('系統正在處理其他檔案，請稍候再試')
    return
  }
  
  if (folder.isProcessing) {
    ElMessage.warning('此資料夾正在處理中，請稍候')
    return
  }
  
  debugLog('🚀 開始處理資料夾:', folderName, '路徑:', folder.path)
  
  // 初始化處理狀態
  currentlyProcessing.value++
  folder.isProcessing = true
  folder.hasFailed = false
  folder.hasResult = false
  folder.progress = 0
  folder.progressDetail = t('preparingFolderImages')
  folder.status = 'preparing'
  
  // 清除顯示的舊筆記內容
  summaryResult.value = ''
  currentNoteStyle.value = 'legacy'
  debugLog('🗑️ 已清除舊的筆記內容')
  
  ElMessage.info(t('startBatchProcessingFolder', { folder: folderName }))
  
  try {
    const formData = new FormData()
    formData.append('folder_path', folder.path === 'root' ? '' : folder.path)
    formData.append('device', device.value)
    formData.append('language', effectiveLanguage.value)
    formData.append('include_japanese', includeJapanese.value)
    formData.append('language_mode', languageMode.value)
    
    debugLog('📤 發送處理請求:', {
      folder_path: folder.path === 'root' ? '' : folder.path,
      device: device.value,
      language: effectiveLanguage.value
    })
    
    const response = await fetch('/api/process-folder-images', {
      method: 'POST',
      body: formData
    })
    
    debugLog('📥 API響應狀態:', response.status)
    
    if (response.ok) {
      const result = await response.json()
      folder.taskId = result.task_id
      folder.progressDetail = t('processingStarted')
      folder.progress = 5
      if (folder.taskId) {
        fetchProgressSnapshot(folder.taskId)
      }
      
      debugLog(`✅ 處理任務已啟動 - ${folderName} - Task ID: ${folder.taskId}`)
      ElMessage.success(`處理任務已啟動: ${folderName}`)
      
      // 立即開始輪詢檢查進度
      setTimeout(() => checkFolderProgressLoop(folder), 1000)
    } else {
      const errorText = await response.text()
      console.error('❌ API調用失敗:', response.status, errorText)
      throw new Error(`API調用失敗: ${response.status} - ${errorText}`)
    }
  } catch (error) {
    console.error('❌ 處理資料夾失敗:', error)
    folder.isProcessing = false
    folder.hasFailed = true
    folder.progress = 0
    folder.progressDetail = t('processFailed')
    currentlyProcessing.value-- // 釋放處理位置
    ElMessage.error(`處理失敗: ${folderName} - ${error.message}`)
  }
}

const checkFolderProgressLoop = async (folder) => {
  if (!folder.taskId || !folder.isProcessing) {
    debugLog('⏹️ 停止進度檢查:', folder.name, '原因: taskId或isProcessing為false')
    return
  }
  
  try {
    debugLog('🔍 檢查進度:', folder.name, 'Task ID:', folder.taskId)
    const response = await fetch(`/api/folder-status/${folder.taskId}`)
    
    if (response.ok) {
      const status = await response.json()
      
      // 🚨 檢查是否需要重啟 Ollama
      if (status.needs_ollama_restart) {
        console.error('🚨 檢測到 Ollama 需要重啟:', status)
        folder.isProcessing = false
        folder.hasFailed = true
        folder.progress = 100
        folder.status = 'ollama_failed'
        currentlyProcessing.value--
        
        // 更新 Ollama 狀態
        ollamaStatus.value = {
          status: 'error',
          message: 'Ollama 服務已崩潰，無法進行 LLM 分析',
          models: [],
          can_restart: true
        }
        
        // 彈出警告對話框
        ElMessageBox.confirm(
          '🚨 LLM 分析服務已停止響應\n\nOllama 服務可能已崩潰或 VRAM 資源耗盡。\n\n請點擊「立即重啟」來修復此問題，或稍後手動重啟。',
          'Ollama 服務異常',
          {
            confirmButtonText: '🔄 立即重啟',
            cancelButtonText: '稍後處理',
            type: 'error',
            distinguishCancelAndClose: true
          }
        ).then(() => {
          // 用戶點擊立即重啟
          restartOllama()
        }).catch(() => {
          // 用戶點擊取消或關閉
          ElMessage.info('請在準備好時點擊側邊欄的「重啟 Ollama」按鈕')
        })
        
        return  // 停止繼續檢查進度
      }
      
      // 更新進度信息
      folder.progress = status.progress || 0
      folder.progressDetail = status.detail || t('processing')
      folder.status = status.status
      folder.current_stage = status.current_stage || ''
      folder.current_file = status.current_file || ''
      folder.elapsed_time = status.elapsed_time || 0
      
  debugLog(`📊 進度更新 [${folder.name}]: ${folder.progress}% - ${status.status} - ${folder.progressDetail}`)
      
  // 檢查完成狀態（優先使用 status_code）
  const done = (status.status_code && status.status_code === 'completed') ||
       status.status === 'completed' || status.status === '完成' || status.status === 'finished' || status.status === '完了'
      if (done) {
        folder.isProcessing = false
        folder.hasResult = true
        folder.progress = 100
        folder.status = 'completed'
        currentlyProcessing.value-- // 釋放處理位置
        
        debugLog('✅ 資料夾處理完成:', folder.name)
        ElMessage.success(`資料夾處理完成: ${folder.name}`)
        
        // 自動載入結果，增加延遲以確保文件已生成
        setTimeout(() => {
          debugLog('🔄 開始自動載入結果:', folder.name)
          loadFolderResult(folder)
        }, 3000) // 增加延遲時間到3秒
        
  } else if ((status.status_code && (status.status_code === 'failed' || status.status_code === 'error')) || status.status === 'failed' || status.status === 'error' || status.status === '錯誤' || status.status === '失敗') {
        folder.isProcessing = false
        folder.hasFailed = true
        folder.progress = 100
        folder.status = 'failed'
        currentlyProcessing.value-- // 釋放處理位置
        
        debugLog('❌ 資料夾處理失敗:', folder.name, status.detail)
        ElMessage.error(`資料夾處理失敗: ${folder.name} - ${status.detail}`)
        
      } else {
        // 繼續輪詢
        setTimeout(() => checkFolderProgressLoop(folder), 2000)
      }
    } else {
      console.error('❌ 獲取進度失敗:', response.status)
      setTimeout(() => checkFolderProgressLoop(folder), 3000)
    }
  } catch (error) {
    console.error('❌ 檢查資料夾進度失敗:', error)
    setTimeout(() => checkFolderProgressLoop(folder), 5000)
  }
}

const processAllFolders = () => {
  const unprocessedFolders = imageFolders.value.filter(f => !f.hasResult && !f.isProcessing)
  if (unprocessedFolders.length === 0) {
    ElMessage.warning(t('noPendingImages'))
    return
  }
  
  isProcessingFolders.value = true
  ElMessage.info(t('startBatchProcessImages', { count: unprocessedFolders.length }))
  
  unprocessedFolders.forEach((folder, index) => {
    setTimeout(() => {
      processFolder(folder)
      if (index === unprocessedFolders.length - 1) {
        isProcessingFolders.value = false
      }
    }, index * 2000)
  })
}

const loadFolderResult = async (folder) => {
  const folderName = folder.name || t('unknownFolder')
  debugLog('📂 正在載入資料夾結果:', folderName, '路徑:', folder.path)
  
  try {
    // 根據後端的檔案命名邏輯生成可能的檔案名
    // 後端邏輯：folder_name = folder_path.strip().replace('/', '_').replace('\\', '_') if folder_path else 'root'
    // 檔案名：{folder_name}_combined.md
    const possibleFilenames = []
    
    if (folder.path === 'root' || !folder.path || folder.path.trim() === '') {
      // 根目錄的情況
      possibleFilenames.push('root_combined')
    } else {
      // 子資料夾的情況 - 完全按照後端邏輯
      const cleanPath = folder.path.trim().replace(/[/\\]/g, '_')
      possibleFilenames.push(`${cleanPath}_combined`)
    }
    
    debugLog('📋 根據後端邏輯生成的檔案名:', possibleFilenames)
    
    debugLog('🔍 嘗試載入檔案名:', possibleFilenames)
    
    let result = null
    let successFilename = null
    
    // 嘗試每個可能的檔案名
    for (const filename of possibleFilenames) {
      try {
        debugLog(`📄 嘗試檔案名: ${filename}`)
        const response = await fetch(`/api/result/${encodeURIComponent(filename)}`)
        if (response.ok) {
          result = await response.json()
          successFilename = filename
          debugLog(`✅ 成功載入: ${filename}`)
          break
        } else {
          debugLog(`❌ 檔案不存在: ${filename} (${response.status})`)
        }
      } catch (err) {
        debugLog(`❌ 載入失敗: ${filename} - ${err.message}`)
        continue
      }
    }
    
    if (result && successFilename) {
      currentProcessedVideo.value = folder
      summaryResult.value = result.content || result.summary || result.result || t('noResultContentFound')
      ElMessage.success(`成功載入資料夾結果: ${folderName}`)
      
      // 滾動到結果區域
      nextTick(() => {
        if (resultSectionEl.value) {
          resultSectionEl.value.scrollIntoView({ behavior: 'smooth' })
        }
      })
    } else {
      throw new Error(t('cannotFindResultFile') + `: ${possibleFilenames.join(', ')}`)
    }
  } catch (error) {
    console.error(t('loadResultFailed') + ':', error)
    ElMessage.error(`${t('loadResultFailed')}: ${folderName} - ${error.message}`)
    
    // 提供手動檢查的建議
    ElMessageBox.alert(
      t('folderLoadFailureMessage', { folderName }),
      t('loadResultFailed'),
      { confirmButtonText: t('confirm'), type: 'warning' }
    )
  }
}

const checkFolderProgress = (folder) => {
  const folderName = folder.name || t('unknownFolder')
  debugLog(t('checkFolderProgress') + ':', folderName)
  
  if (folder.taskId) {
    checkFolderProgressLoop(folder)
  } else {
    ElMessage.info(t('checkingProgress'))
  }
}

const retryFolder = (folder) => {
  const folderName = folder.name || t('unknownFolder')
  debugLog(t('retryFolder') + ':', folderName)
  folder.hasFailed = false
  folder.isProcessing = false
  currentlyProcessing.value-- // 釋放處理位置（重新嘗試）
  ElMessage.info(`準備重新處理: ${folderName}`)
  processFolder(folder)
}

const showFolderDetails = (folder) => {
  const folderName = folder.name || t('unknownFolder')
  debugLog(t('showFolderDetails') + ':', folderName)
  ElMessageBox.alert(
    t('folderDetailsMessage', { 
      folderName: folderName, 
      path: folder.path, 
      imageCount: folder.image_count || 0 
    }),
    folderName,
    { confirmButtonText: t('confirm') }
  )
}

// 重複的onMounted已移除

// 系統診斷：呼叫 /api/diagnose 並在 Console 與對話框顯示
const runDiagnose = async () => {
  try {
    const res = await fetch('/api/diagnose')
    if (!res.ok) throw new Error('diagnose failed')
    const d = await res.json()
    debugLog('🩺 系統診斷結果:', d)

    // 判斷狀態
    const ok = (v) => v === true || v === 'true'
    const s_ollama = d.ollama?.ok && (typeof d.ollama.models === 'number' ? d.ollama.models >= 0 : true)
    const s_ffmpeg = d.ffmpeg?.ok
    const s_nv = d.nvidia_smi?.ok
    const s_paddle = d.paddleocr_vl?.ok
    const s_gpuocr = !!d.paddleocr_vl?.use_gpu
    const s_qwen = d.qwen?.ok
    const formatTime = (value) => {
      if (!value) return '-'
      try {
        return new Date(value).toLocaleString()
      } catch (err) {
        debugWarn('診斷時間格式化失敗', err)
        return value
      }
    }

    const icon = (b) => b ? '🟢' : '🔴'
    const html = `
      <div style="line-height:1.7">
        <div><strong>Ollama</strong>：${icon(!!s_ollama)} ${d.ollama?.status ?? ''}（models: ${d.ollama?.models ?? '-'}）</div>
        <div><strong>FFmpeg</strong>：${icon(!!s_ffmpeg)} ${d.ffmpeg?.version ?? ''}</div>
        <div><strong>GPU / nvidia-smi</strong>：${icon(!!s_nv)} ${s_nv ? 'available' : (d.nvidia_smi?.error ?? '-') }</div>
        <div><strong>PaddleOCR-VL</strong>：${icon(!!s_paddle)} version=${d.paddleocr_vl?.version ?? '-'} device=${d.paddleocr_vl?.device ?? '-'} batch=${d.paddleocr_vl?.batch_size ?? '-'}</div>
        <div style="margin-left:1.5em;font-size:13px">root=${d.paddleocr_vl?.model_root ?? '-'} layout=${d.paddleocr_vl?.layout_model_dir ?? '-'}<br/>layout files：pdmodel=${d.paddleocr_vl?.layout_files?.pdmodel ? '✅' : '⚠️'} , pdiparams=${d.paddleocr_vl?.layout_files?.pdiparams ? '✅' : '⚠️'} 使用 GPU：${s_gpuocr ? '是' : '否'}<br/>最後檢查：${formatTime(d.paddleocr_vl?.checked_at)}</div>
        <div><strong>Qwen 2.5VL</strong>：${icon(!!s_qwen)} model=${d.qwen?.configured_model ?? '-'} ${d.qwen?.present_in_ollama ? '(Ollama 已載入)' : '(Ollama 未載入)'}</div>
        <div style="margin-left:1.5em;font-size:13px">scene=${d.qwen?.scene_model ?? '-'} / image=${d.qwen?.image_model ?? '-'}<br/>Ollama 模型：${(d.qwen?.available_models || []).join(', ') || '-'}<br/>最後檢查：${formatTime(d.qwen?.checked_at)}</div>
        <hr/>
        <div style="font-size:12px;color:#888">完整 JSON 已輸出到 Console（F12）。</div>
      </div>`

    ElMessageBox.alert(html, `🩺 ${t('systemDiagnosis') || '系統診斷'}`, { dangerouslyUseHTMLString: true, confirmButtonText: t('confirm') })
  } catch (e) {
    console.error('診斷失敗:', e)
    ElMessage.error('診斷失敗')
  }
}
</script>

<style scoped>
/* ========== Markdown 渲染器樣式 (整合自 BilingualMarkdownRenderer) ========== */
.bilingual-markdown-renderer {
  padding: 1.5rem;
  max-width: 1200px;
  margin: 0 auto;
}

/* Legacy Styles */
.section { margin-bottom: 3rem; }
.section-title {
  font-size: 1.75rem;
  font-weight: 700;
  margin-bottom: 1.5rem;
  color: var(--el-text-color-primary);
  padding-bottom: 0.75rem;
  border-bottom: 3px solid var(--el-color-primary);
}
.bilingual-item {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.5rem;
  margin-bottom: 1rem;
  padding: 1.25rem;
  background: var(--el-bg-color-page);
  border-radius: 12px;
  border: 1px solid var(--el-border-color-light);
  transition: all 0.3s ease;
}
.bilingual-item:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
  transform: translateY(-2px);
}
.lang-box {
  padding: 1rem;
  border-radius: 8px;
  background: var(--lang-bg-color);
  border-left: 4px solid var(--lang-border-color);
  position: relative;
  min-height: 60px;
}
.lang-label {
  position: absolute;
  top: -10px;
  left: 12px;
  background: white;
  padding: 2px 10px;
  font-size: 0.7rem;
  font-weight: 700;
  color: var(--lang-main-color);
  border-radius: 10px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.1);
}
.lang-content {
  padding-top: 8px;
  font-size: 1rem;
  line-height: 1.7;
  color: var(--el-text-color-primary);
}

/* Math Block */
:deep(.math-text-block) {
  padding: 16px 18px;
  margin: 14px 0;
  background: rgba(14, 165, 233, 0.08);
  border: 1px solid rgba(14, 165, 233, 0.22);
  border-radius: 12px;
  color: var(--el-text-color-primary);
  overflow-x: auto;
}
:deep(.math-text-block .katex) { font-size: 1.05rem; }

/* Fallback & Card Styles */
.fallback-markdown {
  padding: 1rem 0;
  line-height: 1.8;
}

/* Note Card Structure */
:deep(.note-card) {
  background: var(--el-bg-color-overlay, #ffffff);
  border: 1px solid var(--el-border-color-light, #e4e7ed);
  border-radius: 16px;
  margin-bottom: 24px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
  overflow: hidden;
  transition: all 0.3s ease;
}
:deep(.note-card:hover) {
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.08);
  border-color: var(--el-color-primary-light-5);
}
:deep(.note-card-header) {
  padding: 16px 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: var(--el-fill-color-light, #f5f7fa);
  border-bottom: 1px solid var(--el-border-color-lighter, #ebeef5);
  cursor: pointer;
  user-select: none;
}
:deep(.note-card-header:hover) { background: var(--el-fill-color, #f0f2f5); }
:deep(.note-card-body) { padding: 24px; background: var(--el-bg-color, #ffffff); }
:deep(.note-card.collapsed .note-card-body) { display: none; }
:deep(.card-toggle-btn) {
  background: none;
  border: none;
  padding: 6px;
  color: var(--el-text-color-secondary);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  transition: all 0.3s ease;
}
:deep(.card-toggle-btn:hover) { background: var(--el-fill-color-dark); color: var(--el-color-primary); }
:deep(.note-card.collapsed .card-toggle-btn) { transform: rotate(-90deg); }

/* Headings inside Card Header */
:deep(.note-heading) {
  display: flex;
  align-items: center;
  gap: 0.8rem;
  font-size: 1.25rem;
  font-weight: 700;
  margin: 0 !important;
  padding: 0 !important;
  border: none !important;
  background: none !important;
  box-shadow: none !important;
  color: var(--el-text-color-primary);
}
:deep(.note-heading--primary) { color: var(--el-color-primary); }
:deep(.note-heading--explain) { color: #409eff; }
:deep(.note-heading--image) { color: #e6a23c; }

/* Code Blocks */
:deep(.code-container) {
  margin: 16px 0;
  border-radius: 12px;
  overflow: hidden;
  border: 1px solid var(--el-border-color-darker);
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}
:deep(.code-header) {
  background: #2b2d31;
  padding: 8px 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.85rem;
  color: #a0a0a0;
}
:deep(.code-copy-btn) {
  background: rgba(255,255,255,0.1);
  border: none;
  border-radius: 4px;
  color: #fff;
  padding: 4px 10px;
  cursor: pointer;
  font-size: 0.8rem;
}
:deep(pre.code-block) {
  margin: 0 !important;
  padding: 16px;
  background: #1e1e1e;
  overflow-x: auto;
  color: #d4d4d4;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.9rem;
}

/* Images */
:deep(img.mk-img) {
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
  max-width: 100%;
  display: block;
  margin: 16px auto;
}

@media (max-width: 768px) {
  .bilingual-markdown-renderer { padding: 1rem; }
  .bilingual-item { grid-template-columns: 1fr; gap: 1rem; padding: 1rem; }
  :deep(.note-card-header) { padding: 12px 16px; }
  :deep(.note-card-body) { padding: 16px; }
  :deep(.note-heading) { font-size: 1.1rem; }
}

@media (prefers-color-scheme: dark) {
  .lang-label { background: #2c2c2c; box-shadow: 0 2px 6px rgba(0, 0, 0, 0.3); }
  :deep(.note-card) { background: #1e1e20; border-color: #333; }
  :deep(.note-card-header) { background: #262729; border-color: #333; }
  :deep(.note-card-body) { background: #1e1e20; }
  :deep(.math-text-block) { background: rgba(14, 165, 233, 0.15); border-color: rgba(14, 165, 233, 0.3); }
}
/* ========== Markdown 渲染器樣式結束 ========== */

/* ========== 原有 Home.vue 樣式 ========== */
.action-buttons {
  margin-top: 1rem;
  text-align: center;
}
/* 使用統一的CSS變量系統 */
.home-content {
  display: flex;
  gap: var(--spacing-lg);
  padding: var(--spacing-lg);
  min-height: calc(100vh - 80px);
  max-width: 1400px;
  margin: 0 auto;
}

.app-sidebar {
  width: 320px;
  flex-shrink: 0;
  position: sticky;
  top: 12px;
  align-self: flex-start;
  max-height: calc(100vh - 24px);
  overflow-y: auto;
  padding-right: 6px;
}
.collapse-toggle {
  width: 100%;
  margin: 6px 0 12px 0;
  padding: 6px 10px;
  font-size: 13px;
  background: var(--bg-secondary);
  color: var(--text-color);
  border: 1px solid var(--border-color);
  border-radius: var(--border-radius-sm);
  cursor: pointer;
  text-align: left;
}
.collapsible-panel {
  margin-bottom: 12px;
}
.collapsible-title {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--border-radius-md);
  padding: 8px 10px;
  font-weight: 600;
  color: var(--text-color);
}
.title-with-icon {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.collapse-arrow {
  transition: transform 0.2s ease;
}
.collapse-arrow.open {
  transform: rotate(180deg);
}
.collapsible-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  cursor: pointer;
}

/* Ollama 狀態監控樣式 */
.ollama-status-panel.panel-error {
  border-left: 4px solid var(--color-danger);
}

.ollama-status-panel.panel-warning {
  border-left: 4px solid var(--color-warning);
}

.ollama-status-container {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-sm);
  border-radius: var(--border-radius-md);
  background: var(--bg-secondary);
}

.status-indicator.healthy {
  background: rgba(82, 196, 26, 0.1);
  border: 1px solid rgba(82, 196, 26, 0.3);
}

.status-indicator.error {
  background: rgba(255, 77, 79, 0.1);
  border: 1px solid rgba(255, 77, 79, 0.3);
}

.status-indicator.warning {
  background: rgba(250, 173, 20, 0.1);
  border: 1px solid rgba(250, 173, 20, 0.3);
}

.status-indicator.unknown {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
}

.status-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}

.status-indicator.healthy .status-dot {
  background: #52c41a;
  box-shadow: 0 0 8px rgba(82, 196, 26, 0.6);
}

.status-indicator.error .status-dot {
  background: #ff4d4f;
  box-shadow: 0 0 8px rgba(255, 77, 79, 0.6);
}

.status-indicator.warning .status-dot {
  background: #faad14;
  box-shadow: 0 0 8px rgba(250, 173, 20, 0.6);
}

.status-indicator.unknown .status-dot {
  background: #8c8c8c;
}

.status-text {
  flex: 1;
  font-size: var(--font-size-sm);
  color: var(--text-color);
}

.ollama-actions {
  display: flex;
  gap: var(--spacing-sm);
}

.ollama-actions .btn {
  flex: 1;
}

.ollama-models {
  padding: var(--spacing-sm);
  background: var(--bg-secondary);
  border-radius: var(--border-radius-md);
  border: 1px solid var(--border-color);
}

.models-label {
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
  margin-bottom: var(--spacing-xs);
}

.models-list {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-xs);
}

.model-tag {
  display: inline-block;
  padding: 4px 8px;
  background: var(--color-primary);
  color: white;
  border-radius: var(--border-radius-sm);
  font-size: var(--font-size-xs);
  font-family: 'Courier New', monospace;
}

.ollama-hint {
  padding: var(--spacing-sm);
  background: rgba(255, 77, 79, 0.1);
  border-left: 3px solid var(--color-danger);
  border-radius: var(--border-radius-sm);
  font-size: var(--font-size-xs);
  color: var(--text-color);
  line-height: 1.5;
}

.app-content {
  flex: 1;
  min-width: 0;
}

/* 設置面板樣式 */
.settings-panel,
.folder-panel {
  background: var(--card-bg);
  border: 1px solid var(--border-color);
  border-radius: var(--border-radius-lg);
  padding: var(--spacing-lg);
  margin-bottom: var(--spacing-lg);
}

.provider-summary {
  margin-top: 8px;
  padding: 10px 12px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(148, 163, 184, 0.2);
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.provider-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  font-size: 0.92rem;
  flex-wrap: wrap;
}

.provider-label {
  color: #94a3b8;
  font-weight: 500;
  letter-spacing: 0.4px;
}

.provider-value {
  color: #e2e8f0;
  font-weight: 600;
  text-align: right;
  word-break: break-word;
}

.provider-warning {
  margin: 0;
  color: #f97316;
  font-size: 0.88rem;
  line-height: 1.4;
}

.provider-select {
  min-width: 140px;
  padding: 6px 10px;
  border-radius: 6px;
  background: rgba(15, 23, 42, 0.6);
  border: 1px solid rgba(148, 163, 184, 0.3);
  color: var(--text-color);
}

.provider-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.provider-hint {
  font-size: 0.8rem;
  color: #94a3b8;
  opacity: 0.8;
}

.provider-summary .refresh-llm {
  margin-right: 4px;
}

.btn-sm {
  padding: 6px 10px;
  font-size: 0.85rem;
  line-height: 1.2;
}

.panel-title {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  margin: 0 0 var(--spacing-lg) 0;
  font-size: var(--font-size-lg);
  font-weight: 600;
  color: var(--text-color);
}

.title-icon {
  width: 20px;
  height: 20px;
}

.setting-group {
  margin-bottom: var(--spacing-md);
}

.setting-label {
  display: block;
  margin-bottom: var(--spacing-sm);
  font-weight: 500;
  color: var(--text-color);
}

.setting-select,
.setting-input {
  width: 100%;
  padding: var(--spacing-sm);
  border: 1px solid var(--border-color);
  border-radius: var(--border-radius-md);
  background: var(--input-bg);
  color: var(--text-color);
}

.setting-textarea {
  width: 100%;
  min-height: 80px;
  padding: var(--spacing-sm);
  border: 1px solid var(--border-color);
  border-radius: var(--border-radius-md);
  background: var(--input-bg);
  color: var(--text-color);
  resize: vertical;
}

.path-input-group {
  display: flex;
  gap: var(--spacing-sm);
}

.path-btn {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
}

.path-btn svg {
  width: 16px;
  height: 16px;
}

.path-status {
  margin-top: var(--spacing-xs);
  font-size: var(--font-size-sm);
}

.quick-paths {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-sm);
}

.quick-path-btn {
  font-size: var(--font-size-sm);
}

/* 資料夾樹樣式 */
.folder-path {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-sm);
  background: var(--bg-secondary);
  border-radius: var(--border-radius-md);
  margin-bottom: var(--spacing-md);
}

.path-icon {
  width: 16px;
  height: 16px;
}

.path-text {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}

.folder-tree {
  max-height: 200px;
  overflow-y: auto;
  margin-bottom: var(--spacing-md);
}

.folder-options {
  padding-top: var(--spacing-md);
  border-top: 1px solid var(--border-color);
}

.option-toggle {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  cursor: pointer;
}

.toggle-text {
  font-size: var(--font-size-sm);
}

/* 內容區域樣式 */
.content-section {
  background: var(--card-bg);
  border: 1px solid var(--border-color);
  border-radius: var(--border-radius-lg);
  padding: var(--spacing-lg);
  margin-bottom: var(--spacing-lg);
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--spacing-lg);
}

.section-title {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}

.section-title h2 {
  margin: 0;
  font-size: var(--font-size-xl);
  color: var(--text-color);
}

.section-icon {
  width: 24px;
  height: 24px;
}

.section-actions {
  display: flex;
  gap: var(--spacing-sm);
}

.collapse-btn,
.refresh-btn {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
  padding: var(--spacing-sm);
  border: 1px solid var(--border-color);
  border-radius: var(--border-radius-md);
  background: var(--button-bg);
  color: var(--text-color);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.collapse-btn:hover,
.refresh-btn:hover {
  background: var(--button-hover);
}

.collapse-btn svg,
.refresh-btn svg {
  width: 16px;
  height: 16px;
}

.collapsible-content {
  transition: all 0.3s ease;
}

/* 統計信息欄樣式 */
.stats-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  background: var(--bg-secondary);
  border-radius: var(--border-radius-md);
  margin-bottom: 12px;
  position: sticky;
  top: 12px;
  z-index: 5;
  border: 1px solid var(--border-color);
}

.stats-info {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-color);
}

.stat-item svg {
  width: 16px;
  height: 16px;
}

.stat-item.success {
  color: var(--success-color);
}

.stat-item.pending {
  color: var(--warning-color);
}

.stats-actions {
  display: flex;
  gap: var(--spacing-sm);
}

.batch-process-btn {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
  background: var(--warning-color);
  color: white;
  border-color: var(--warning-color);
}

.batch-process-btn:hover {
  background: #e0a800;
  border-color: #e0a800;
}

.batch-process-btn svg {
  width: 16px;
  height: 16px;
}

/* 影片網格樣式 */
.media-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 14px;
}

.media-card {
  border: 1px solid var(--border-color);
  border-radius: var(--border-radius-md);
  background: var(--card-bg);
  overflow: hidden;
  transition: all var(--transition-normal);
  font-size: 13px;
}

.media-card:hover {
  box-shadow: var(--shadow-md);
  transform: translateY(-2px);
}

.media-card.has-result {
  border-color: var(--success-color);
  background: rgba(40, 167, 69, 0.05);
}

.media-card.processing {
  border-color: var(--primary-color);
  background: rgba(0, 120, 215, 0.05);
}

.media-card.cancelled {
  border-color: var(--border-color);
  background: rgba(156, 163, 175, 0.08);
  opacity: 0.9;
}

.media-card.failed {
  border-color: var(--danger-color);
  background: rgba(220, 53, 69, 0.05);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 10px 12px;
  border-bottom: 1px solid var(--border-color);
  background: var(--bg-secondary);
}

.media-title {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-color);
  line-height: 1.35;
}

.media-status {
  flex-shrink: 0;
  margin-left: var(--spacing-sm);
}

.status-badge {
  padding: var(--spacing-xs) var(--spacing-sm);
  border-radius: var(--border-radius-sm);
  font-size: var(--font-size-xs);
  font-weight: 600;
  text-transform: uppercase;
}

.status-badge.success {
  background: var(--success-color);
  color: white;
}

.status-badge.processing {
  background: var(--primary-color);
  color: white;
}

.status-badge.failed {
  background: var(--danger-color);
  color: white;
}

.status-badge.pending {
  background: var(--warning-color);
  color: white;
}

/* 狀態指示器樣式 */
.status-indicator {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
  padding: var(--spacing-xs) var(--spacing-sm);
  border-radius: var(--border-radius-sm);
  font-size: var(--font-size-xs);
  font-weight: 600;
  text-transform: uppercase;
}

.status-indicator.completed {
  background: rgba(40, 167, 69, 0.1);
  color: white; /* 完成狀態用白色文字 */
  border: 1px solid var(--success-color);
}

.status-indicator.processing {
  background: rgba(0, 120, 215, 0.1);
  color: var(--primary-color);
  border: 1px solid var(--primary-color);
}

.status-indicator.pending {
  background: rgba(255, 193, 7, 0.1);
  color: #ffc107; /* 待處理狀態用黃色文字 */
  border: 1px solid var(--warning-color);
}

.status-indicator.cancelled {
  background: rgba(108, 117, 125, 0.12);
  color: var(--text-secondary);
  border: 1px solid rgba(108, 117, 125, 0.6);
}

.status-indicator.failed {
  background: rgba(220, 53, 69, 0.1);
  color: var(--danger-color);
  border: 1px solid var(--danger-color);
}

.status-indicator svg {
  width: 12px;
  height: 12px;
  flex-shrink: 0;
}

.card-body {
  padding: var(--spacing-md);
}

.media-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.info-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12.5px;
}

.info-label {
  font-weight: 500;
  color: var(--text-secondary);
  min-width: 40px;
}

.info-value {
  color: var(--text-color);
  text-align: right;
  word-break: break-all;
}

.card-actions {
  display: flex;
  gap: 8px;
  padding: 10px 12px;
  border-top: 1px solid var(--border-color);
  background: var(--bg-secondary);
}

.card-actions .btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  padding: 7px 12px;
  font-size: 12px;
  font-weight: 600;
}

.card-actions .btn svg {
  width: 13px;
  height: 13px;
}

/* 空狀態樣式 */
.empty-state {
  text-align: center;
  padding: var(--spacing-xxl);
  color: var(--text-secondary);
}

.empty-icon {
  font-size: 4rem;
  margin-bottom: var(--spacing-md);
}

.empty-state h3 {
  margin: var(--spacing-md) 0;
  color: var(--text-color);
}

.empty-hint {
  font-size: var(--font-size-sm);
  margin-bottom: var(--spacing-lg);
}

/* 結果區域樣式 */
.result-section {
  background: var(--card-bg);
  border: 1px solid var(--border-color);
  border-radius: var(--border-radius-lg);
  padding: var(--spacing-lg);
}

.result-diagnostics {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 8px;
  font-size: 12px;
  color: var(--muted);
}

.result-diagnostics span {
  background: rgba(255, 255, 255, 0.05);
  padding: 4px 8px;
  border-radius: 6px;
}

.result-actions {
  display: flex;
  gap: var(--spacing-sm);
}

.result-content {
  margin-top: var(--spacing-lg);
}

.note-content {
  background: var(--card-bg);
  border: 1px solid var(--border-color);
  border-radius: var(--border-radius-md);
  padding: var(--spacing-lg);
  line-height: 1.6;
  color: var(--text-color);
}

.note-content h1,
.note-content h2,
.note-content h3,
.note-content h4,
.note-content h5,
.note-content h6 {
  color: var(--text-color);
  margin-top: var(--spacing-md);
  margin-bottom: var(--spacing-sm);
}

.note-content p {
  margin-bottom: var(--spacing-sm);
}

.note-content ul,
.note-content ol {
  margin-bottom: var(--spacing-sm);
  padding-left: var(--spacing-lg);
}

.note-content li {
  margin-bottom: var(--spacing-xs);
}

.note-content code {
  background: var(--bg-secondary);
  padding: 2px 4px;
  border-radius: 3px;
  font-family: 'Courier New', monospace;
}

.note-content pre {
  background: var(--bg-secondary);
  padding: var(--spacing-md);
  border-radius: var(--border-radius-md);
  overflow-x: auto;
  margin-bottom: var(--spacing-md);
}

.note-content blockquote {
  border-left: 4px solid var(--primary-color);
  padding-left: var(--spacing-md);
  margin: var(--spacing-md) 0;
  color: var(--text-secondary);
}

/* ========================================
   舊的 Markdown 渲染樣式已移除
   現由 BilingualMarkdownRenderer.vue 負責
   ======================================== */
</style>

<!-- 🎯 非 scoped 樣式 - 引入外部 CSS -->
<style>
@import '../styles/home-markdown.css';

.code-container {
  background: linear-gradient(135deg, #1a1f29 0%, #1e232e 100%) !important;
  border: 2px solid rgba(59, 130, 246, 0.5) !important;
  border-radius: 12px !important;
  margin: 24px 0 !important;
  overflow: hidden !important;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4), inset 0 1px 0 rgba(255, 255, 255, 0.05) !important;
  transition: all 0.3s ease !important;
}

.code-container:hover {
  border-color: rgba(59, 130, 246, 0.8) !important;
  box-shadow: 0 12px 32px rgba(59, 130, 246, 0.2), inset 0 1px 0 rgba(255, 255, 255, 0.05) !important;
  transform: translateY(-2px) !important;
}

/* 代碼頭部 - 語言標籤 + 複製按鈕 */
.code-header {
  display: flex !important;
  justify-content: space-between !important;
  align-items: center !important;
  padding: 12px 20px !important;
  background: rgba(0, 0, 0, 0.3) !important;
  border-bottom: 1px solid rgba(59, 130, 246, 0.3) !important;
}

.code-language {
  font-family: system-ui, -apple-system !important;
  font-size: 13px !important;
  font-weight: 700 !important;
  color: #60a5fa !important;
  background: rgba(59, 130, 246, 0.2) !important;
  padding: 4px 12px !important;
  border-radius: 6px !important;
  border: 1px solid rgba(59, 130, 246, 0.4) !important;
  text-transform: uppercase !important;
  letter-spacing: 1px !important;
}

.code-copy-btn {
  font-family: system-ui, -apple-system !important;
  font-size: 12px !important;
  font-weight: 600 !important;
  color: #e5e7eb !important;
  background: rgba(59, 130, 246, 0.8) !important;  /* 改成更明顯的藍色 */
  padding: 6px 14px !important;
  border: 1px solid rgba(255, 255, 255, 0.2) !important;
  border-radius: 6px !important;
  cursor: pointer !important;
  transition: all 0.2s ease !important;
  position: relative !important;  /* 確保可見 */
  z-index: 100 !important;  /* 提高層級 */
  opacity: 1 !important;  /* 強制不透明 */
  visibility: visible !important;  /* 強制可見 */
  display: inline-block !important;  /* 強制顯示 */
}

.code-copy-btn:hover {
  background: rgba(59, 130, 246, 0.3) !important;
  border-color: rgba(59, 130, 246, 0.5) !important;
  transform: translateY(-1px) !important;
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2) !important;
}

.code-copy-btn:active {
  transform: translateY(0) !important;
}

/* 代碼塊本體 */
.code-block {
  background: transparent !important;
  border: none !important;
  padding: 24px !important;
  margin: 0 !important;
  max-width: 100% !important;
  box-sizing: border-box !important;
  overflow-x: auto !important;
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace !important;
  font-size: 14px !important;
  line-height: 1.8 !important;
  scroll-behavior: smooth !important;  /* 平滑滾動 */
}

.code-block::-webkit-scrollbar {
  height: 8px !important;
}

.code-block::-webkit-scrollbar-track {
  background: rgba(0, 0, 0, 0.2) !important;
  border-radius: 4px !important;
}

.code-block::-webkit-scrollbar-thumb {
  background: rgba(59, 130, 246, 0.5) !important;
  border-radius: 4px !important;
}

.code-block::-webkit-scrollbar-thumb:hover {
  background: rgba(59, 130, 246, 0.7) !important;
}

.code-block code {
  color: #e5e7eb !important;
  background: transparent !important;
  padding: 0 !important;
  border: none !important;
  font-size: 14px !important;
  display: block !important;
  white-space: pre-wrap !important;
  overflow-wrap: anywhere !important;
  word-break: break-word !important;
}

/* markdownRenderer 輸出的 <pre class="plain-code-block"> 兜底樣式（避免長行被父容器裁切） */
pre.plain-code-block,
.plain-code-block {
  max-width: 100% !important;
  box-sizing: border-box !important;
  overflow: auto !important;
  white-space: pre-wrap !important;
  overflow-wrap: anywhere !important;
  word-break: break-word !important;
}
.plain-code-block code,
code.plain-code {
  white-space: inherit !important;
  overflow-wrap: inherit !important;
  word-break: inherit !important;
}

/* 強制代碼塊內容換行，避免變成單行文字牆（對應 AI 沒換行的輸出） */
pre code.hljs {
  white-space: pre-wrap !important;
  overflow-wrap: anywhere !important;
  word-break: break-word !important;
}

/* 讓數學公式稍微大一點 */
.katex {
  font-size: 1.12em !important;
}

/* 🎨 語法高亮增強 - highlight.js 樣式覆蓋 */
.code-block code {
  /* 會由 highlight.js 自動添加類別 */
}

/* 代碼註解顏色增強 */
.code-block .hljs-comment {
  color: #6b7280 !important;  /* 灰色註解 */
  font-style: italic !important;
}

/* 字符串顏色 */
.code-block .hljs-string {
  color: #86efac !important;  /* 綠色字符串 */
}

/* 數字顏色 */
.code-block .hljs-number {
  color: #fbbf24 !important;  /* 金黃色數字 */
}

/* 關鍵字顏色 */
.code-block .hljs-keyword {
  color: #c084fc !important;  /* 紫色關鍵字 */
  font-weight: 600 !important;
}

/* 函數名稱 */
.code-block .hljs-title,
.code-block .hljs-function {
  color: #60a5fa !important;  /* 藍色函數 */
}

/* 變數名稱 */
.code-block .hljs-variable,
.code-block .hljs-attr {
  color: #e5e7eb !important;  /* 白色變數 */
}

/* 內建對象 (console, Number, String...) */
.code-block .hljs-built_in {
  color: #fbbf24 !important;  /* 金黃色內建對象 */
  font-weight: 600 !important;
}

/* 術語高亮增強 - 段落中的代碼術語 - 移除螢光 */
code:not(.code-block code):not(.code-block *), .code-term {
  background: rgba(59, 130, 246, 0.2) !important;
  color: #60a5fa !important;
  padding: 4px 10px !important;
  border-radius: 5px !important;
  font-family: 'Consolas', 'Monaco', monospace !important;
  font-size: 0.92em !important;
  font-weight: 600 !important;
  border: 1px solid rgba(59, 130, 246, 0.3) !important;
  letter-spacing: 0.5px !important;
}

/* 粗體文字增強 - 重點內容 (限縮到 .summary-result) */
.summary-result strong, .summary-result b {
  color: #fbbf24 !important;  /* 金黃色 */
  font-weight: 700 !important;
  text-shadow: 0 0 10px rgba(251, 191, 36, 0.3) !important;  /* 輕微光暈 */
  letter-spacing: 0.5px !important;
}

/* 列表中的粗體 */
.summary-result li strong, .summary-result li b {
  color: #fbbf24 !important;
  font-weight: 700 !important;
}

/* 標題中的粗體 */
.summary-result h1 strong, .summary-result h2 strong, .summary-result h3 strong, .summary-result h4 strong {
  color: #60a5fa !important;  /* 藍色 */
  font-weight: 800 !important;
}

/* 📊 表格樣式增強 (限縮到 .summary-result) */
.summary-result table {
  width: 100% !important;
  border-collapse: collapse !important;
  margin: 20px 0 !important;
  background: rgba(0, 0, 0, 0.2) !important;
  border-radius: 8px !important;
  overflow: hidden !important;
}

.summary-result thead {
  background: rgba(59, 130, 246, 0.2) !important;
}

.summary-result th {
  padding: 12px 16px !important;
  text-align: left !important;
  font-weight: 700 !important;
  color: #60a5fa !important;
  border-bottom: 2px solid rgba(59, 130, 246, 0.5) !important;
}

.summary-result td {
  padding: 12px 16px !important;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1) !important;
  color: #e5e7eb !important;
}

.summary-result tr:hover {
  background: rgba(59, 130, 246, 0.1) !important;
}

/* 表格中的代碼 */
.summary-result table code {
  background: rgba(59, 130, 246, 0.3) !important;
  color: #60a5fa !important;
  padding: 2px 8px !important;
  border-radius: 4px !important;
  font-size: 0.9em !important;
}

/* 🎯 重點排版 - 移除所有螢光效果 (限縮到 .summary-result) */
/* 金黃色重點標題 */
.summary-result strong:first-child,
.summary-result b:first-child,
.summary-result p > strong:first-of-type,
.summary-result p > b:first-of-type {
  display: inline-block !important;
  color: #fbbf24 !important;
  font-weight: 900 !important;
  font-size: 1.1em !important;
  /* 移除 text-shadow 螢光 */
  letter-spacing: 1px !important;
  padding: 4px 0 !important;
  margin-bottom: 8px !important;
}

/* 一般重點粗體 */
.summary-result strong,
.summary-result b {
  color: #fbbf24 !important;
  font-weight: 900 !important;
  /* 移除 text-shadow 螢光 */
  font-size: 1.05em !important;
  letter-spacing: 0.3px !important;
}

/* 列表項目全域樣式 */
.markdown-list-item {
  background: rgba(26, 31, 41, 0.6) !important;
  border: 1px solid rgba(255, 255, 255, 0.1) !important;
  border-radius: 8px !important;
  padding: 14px 18px !important;
  margin: 10px 0 !important;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2) !important;
  line-height: 1.8 !important;
}

.markdown-list-item:hover {
  transform: translateX(6px) !important;
  border-color: rgba(59, 130, 246, 0.6) !important;
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3) !important;
  background: rgba(26, 31, 41, 0.8) !important;
}

/* H2 標題增強 (限縮到 .summary-result) */
.summary-result h2 {
  font-weight: 700 !important;
  letter-spacing: 0.5px !important;
  line-height: 1.5 !important;
}

.summary-result h2[style*="border-left"] {
  box-shadow: 0 3px 10px rgba(0, 0, 0, 0.25) !important;
  transition: all 0.3s ease !important;
}

.summary-result h2[style*="border-left"]:hover {
  transform: translateX(6px) !important;
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.35) !important;
}

/* 段落增強 (限縮到 .summary-result) */
.summary-result p {
  line-height: 1.8 !important;
  letter-spacing: 0.3px !important;
  margin: 12px 0 !important;
}

/* 空代碼區塊 */
.empty-code {
  background: rgba(30, 30, 30, 0.8) !important;
  border: 2px dashed rgba(255, 255, 255, 0.3) !important;
  border-radius: 8px !important;
  padding: 30px !important;
  margin: 20px 0 !important;
  text-align: center !important;
  color: rgba(156, 163, 175, 0.8) !important;
  font-size: 15px !important;
  font-weight: 600 !important;
}

/* 🎨 捲軸美化 */
.code-block::-webkit-scrollbar {
  height: 8px !important;
}

.code-block::-webkit-scrollbar-track {
  background: rgba(0, 0, 0, 0.2) !important;
  border-radius: 4px !important;
}

.code-block::-webkit-scrollbar-thumb {
  background: rgba(59, 130, 246, 0.5) !important;
  border-radius: 4px !important;
}

.code-block::-webkit-scrollbar-thumb:hover {
  background: rgba(59, 130, 246, 0.7) !important;
}

/* ⏱️ 場景時間標記 */
.scene-timestamp {
  display: inline-block !important;
  background: rgba(59, 130, 246, 0.15) !important;
  color: #60a5fa !important;
  padding: 4px 12px !important;
  border-radius: 16px !important;
  font-size: 0.9em !important;
  font-weight: 600 !important;
  margin: 12px 0 !important;
  border: 1px solid rgba(59, 130, 246, 0.3) !important;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2) !important;
  letter-spacing: 0.5px !important;
}
</style>
