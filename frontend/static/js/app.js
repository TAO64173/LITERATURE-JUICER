// ===== Smooth scroll for nav links =====
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
  anchor.addEventListener('click', function (e) {
    e.preventDefault();
    const target = document.querySelector(this.getAttribute('href'));
    if (target) target.scrollIntoView({ behavior: 'smooth' });
  });
});

// ===== Navbar scroll effect =====
const navbar = document.querySelector('.navbar');
window.addEventListener('scroll', () => {
  navbar.style.boxShadow = window.scrollY > 10 ? '0 1px 3px rgba(0,0,0,0.08)' : 'none';
});

// ===== Toast 通知系统 =====
function showToast(message, type, duration) {
  type = type || 'info';
  duration = duration || 4000;
  const container = document.getElementById('toastContainer');
  if (!container) return;

  const icons = {
    error: '<svg viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.28 7.22a.75.75 0 00-1.06 1.06L8.94 10l-1.72 1.72a.75.75 0 101.06 1.06L10 11.06l1.72 1.72a.75.75 0 101.06-1.06L11.06 10l1.72-1.72a.75.75 0 00-1.06-1.06L10 8.94 8.28 7.22z" clip-rule="evenodd"/></svg>',
    success: '<svg viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.857-9.809a.75.75 0 00-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 10-1.06 1.061l2.5 2.5a.75.75 0 001.137-.089l4-5.5z" clip-rule="evenodd"/></svg>',
    info: '<svg viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a.75.75 0 000 1.5h.253a.25.25 0 01.244.304l-.459 2.066A1.75 1.75 0 0010.747 15H11a.75.75 0 000-1.5h-.253a.25.25 0 01-.244-.304l.459-2.066A1.75 1.75 0 009.253 9H9z" clip-rule="evenodd"/></svg>',
  };

  const toast = document.createElement('div');
  toast.className = 'toast toast-' + type;
  toast.innerHTML =
    '<span class="toast-icon">' + (icons[type] || icons.info) + '</span>' +
    '<span class="toast-body">' + message + '</span>' +
    '<button class="toast-dismiss" aria-label="关闭">&times;</button>';

  container.appendChild(toast);

  const dismiss = toast.querySelector('.toast-dismiss');
  dismiss.addEventListener('click', function() { removeToast(toast); });

  setTimeout(function() { removeToast(toast); }, duration);
}

function removeToast(toast) {
  if (!toast.parentNode) return;
  toast.classList.add('toast-exit');
  setTimeout(function() {
    if (toast.parentNode) toast.parentNode.removeChild(toast);
  }, 250);
}

function showError(message) { showToast(message, 'error', 6000); }
function showSuccess(message) { showToast(message, 'success', 3000); }

// ===== Code validation =====
const ctaBtn = document.querySelector('.cta-btn');
const ctaInput = document.querySelector('.cta-input');
const uploadSection = document.getElementById('upload');

if (ctaBtn && ctaInput) {
  ctaBtn.addEventListener('click', async () => {
    const code = ctaInput.value.trim();
    if (!code) {
      ctaInput.classList.add('ring-2', 'ring-red-400');
      setTimeout(() => ctaInput.classList.remove('ring-2', 'ring-red-400'), 1500);
      showError('请输入卡密');
      return;
    }

    ctaBtn.disabled = true;
    ctaBtn.textContent = '验证中...';

    try {
      const res = await fetch('/validate-code', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code }),
      });
      var rawText = await res.text();
      var data;
      try {
        data = JSON.parse(rawText);
      } catch (e) {
        data = { success: false, message: '服务器响应格式错误' };
      }

      if (data.success) {
        ctaBtn.textContent = '✓ 验证成功';
        ctaBtn.classList.remove('cta-btn');
        ctaBtn.classList.add('bg-green-500');
        ctaInput.disabled = true;
        showSuccess('验证成功，剩余次数：' + (data.remaining_quota != null ? data.remaining_quota : ''));
        if (uploadSection) uploadSection.scrollIntoView({ behavior: 'smooth' });
      } else {
        ctaBtn.textContent = '验证并开始';
        ctaBtn.disabled = false;
        ctaInput.classList.add('ring-2', 'ring-red-400');
        setTimeout(() => ctaInput.classList.remove('ring-2', 'ring-red-400'), 1500);
        showError(data.message || '卡密无效或已用完');
      }
    } catch {
      ctaBtn.textContent = '验证并开始';
      ctaBtn.disabled = false;
      showError('网络错误，请检查连接后重试');
    }
  });

  ctaInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') ctaBtn.click();
  });
}

// ===== Beta code copy =====
var copyBetaBtn = document.getElementById('copyBetaBtn');
var betaCodeDisplay = document.getElementById('betaCodeDisplay');

function fetchNextBetaCode() {
  fetch('/next-beta-code')
    .then(function(res) { return res.json(); })
    .then(function(data) {
      if (data.success && data.code) {
        betaCodeDisplay.textContent = data.code;
      } else {
        betaCodeDisplay.textContent = '暂无可用卡密';
        betaCodeDisplay.classList.add('text-red-400');
      }
    })
    .catch(function() {
      betaCodeDisplay.textContent = '获取失败';
    });
}

// 页面加载时获取最新可用卡密
if (betaCodeDisplay) {
  fetchNextBetaCode();
}

if (copyBetaBtn && betaCodeDisplay) {
  copyBetaBtn.addEventListener('click', function() {
    var code = betaCodeDisplay.textContent.trim();
    if (!code || code === '暂无可用卡密' || code === '获取失败') return;
    navigator.clipboard.writeText(code).then(function() {
      copyBetaBtn.textContent = '✓ 已复制';
      showSuccess('卡密已复制：' + code);
      // 自动填入上方输入框
      if (ctaInput) {
        ctaInput.value = code;
        ctaInput.dispatchEvent(new Event('input'));
      }
      setTimeout(function() {
        copyBetaBtn.innerHTML =
          '<svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"/></svg> 复制卡密';
      }, 2000);
    }).catch(function() {
      showError('复制失败，请手动复制');
    });
  });
}

// ===== File upload management =====
const fileInput = document.getElementById('fileInput');
const uploadZone = document.getElementById('uploadZone');
const fileCount = document.getElementById('fileCount');
const fileList = document.getElementById('fileList');
const emptyHint = document.getElementById('emptyHint');
const processBtn = document.getElementById('processBtn');
const statusArea = document.getElementById('statusArea');
const statusText = document.getElementById('statusText');
const progressBar = document.getElementById('progressBar');
const downloadBtn = document.getElementById('downloadBtn');

// status: 'ready' | 'processing' | 'done' | 'error'
/** @type {{name: string, size: number, file: File, status: string, errorMsg: string}[]} */
let selectedFiles = [];
let isUploading = false;

function formatSize(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

const STATUS_LABELS = {
  ready: '待上传',
  processing: '解析中',
  done: '已完成',
  error: '失败',
};

const PDF_ICON_SVG = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
  <path stroke-linecap="round" stroke-linejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z"/>
</svg>`;

function renderFileList() {
  if (!fileList) return;

  // Update count
  if (fileCount) fileCount.textContent = selectedFiles.length + ' 个';

  // Toggle empty hint
  if (emptyHint) {
    emptyHint.style.display = selectedFiles.length === 0 ? '' : 'none';
  }

  // Clear grid
  fileList.innerHTML = '';

  if (selectedFiles.length === 0) {
    if (processBtn) processBtn.classList.add('hidden');
    if (downloadBtn) downloadBtn.classList.add('hidden');
    if (statusArea) statusArea.classList.add('hidden');
    return;
  }

  // Build thumbnail cards
  selectedFiles.forEach((item, index) => {
    const card = document.createElement('div');
    card.className = 'pdf-thumb';
    card.innerHTML =
      '<button data-index="' + index + '" class="pdf-thumb-delete" aria-label="删除"' +
      (item.status === 'processing' ? ' disabled' : '') + '>×</button>' +
      '<div class="pdf-thumb-icon">' + PDF_ICON_SVG + '</div>' +
      '<div class="pdf-thumb-name" title="' + item.name + '">' + item.name + '</div>' +
      '<div class="pdf-thumb-size">' + formatSize(item.size) + '</div>' +
      '<span class="pdf-thumb-status status-' + item.status + '">' + STATUS_LABELS[item.status] + '</span>';
    fileList.appendChild(card);
  });

  // Toggle buttons
  const allReady = selectedFiles.every(function(f) { return f.status === 'ready'; });
  const anyDone = selectedFiles.some(function(f) { return f.status === 'done'; });

  if (processBtn) {
    processBtn.classList.toggle('hidden', !allReady || selectedFiles.length === 0);
  }
  if (downloadBtn) {
    downloadBtn.classList.toggle('hidden', !anyDone);
  }
}

function addFiles(fileListInput) {
  if (!fileListInput || fileListInput.length === 0) return;
  if (isUploading) return;

  let added = 0;
  const files = Array.from(fileListInput);
  for (const file of files) {
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      showError('文件 ' + file.name + ' 不是 PDF 格式，已跳过');
      continue;
    }
    if (file.size > 10 * 1024 * 1024) {
      showError('文件 ' + file.name + ' 超过 10MB 限制，已跳过');
      continue;
    }
    if (selectedFiles.length >= 20) {
      showError('最多上传 20 个文件');
      break;
    }
    if (selectedFiles.some(f => f.name === file.name && f.size === file.size)) continue;
    selectedFiles.push({
      name: file.name,
      size: file.size,
      file: file,
      status: 'ready',
      errorMsg: '',
    });
    added++;
  }
  renderFileList();
  if (added > 0) {
    setStatus('已添加 ' + added + ' 个文件，共 ' + selectedFiles.length + ' 个待处理', 0);
  }
}

function removeFile(index) {
  if (selectedFiles[index] && selectedFiles[index].status === 'processing') return;
  selectedFiles.splice(index, 1);
  renderFileList();
}

function updateFileStatus(index, status, errorMsg) {
  if (selectedFiles[index]) {
    selectedFiles[index].status = status;
    selectedFiles[index].errorMsg = errorMsg || '';
    renderFileList();
  }
}

// Upload zone events
if (uploadZone && fileInput) {
  uploadZone.addEventListener('click', (e) => {
    if (isUploading) return;
    if (e.target.closest('button') || e.target.closest('a')) return;
    fileInput.click();
  });

  uploadZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    if (!isUploading) uploadZone.classList.add('drag-over');
  });

  uploadZone.addEventListener('dragleave', () => {
    uploadZone.classList.remove('drag-over');
  });

  uploadZone.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadZone.classList.remove('drag-over');
    if (!isUploading) addFiles(e.dataTransfer.files);
  });

  fileInput.addEventListener('change', () => {
    if (fileInput.files && fileInput.files.length > 0) {
      addFiles(fileInput.files);
    }
    fileInput.value = '';
  });
}

// Delete file (event delegation on grid)
if (fileList) {
  fileList.addEventListener('click', (e) => {
    const btn = e.target.closest('.pdf-thumb-delete');
    if (btn && !btn.disabled) removeFile(parseInt(btn.dataset.index, 10));
  });
}

// ===== 读取 SSE 流，如果不是 SSE 则降级为 JSON =====
function readSSEStream(response, onEvent) {
  var contentType = response.headers.get('content-type') || '';

  // 非 SSE 响应：整体读取后作为 JSON 处理
  if (!contentType.includes('text/event-stream')) {
    return response.text().then(function(text) {
      var data = null;
      try {
        data = JSON.parse(text);
      } catch (e) {
        throw new Error('服务器返回了无法解析的响应');
      }
      if (data && data.success === false) {
        throw new Error(data.message || data.detail || '处理失败');
      }
      if (data && data.event && data.data) {
        onEvent(data.event, data.data);
      } else if (data && data.success === true) {
        onEvent('done', data);
      }
    });
  }

  // SSE 流式读取
  if (!response.body) {
    return Promise.reject(new Error('浏览器不支持流式读取响应'));
  }

  var reader = response.body.getReader();
  var decoder = new TextDecoder();
  var buffer = '';

  function processChunk() {
    return reader.read().then(function(result) {
      if (result.done) {
        if (buffer.trim()) {
          processSSEPart(buffer);
        }
        return;
      }

      buffer += decoder.decode(result.value, { stream: true });

      // SSE 事件以 \n\n 分隔
      var parts = buffer.split('\n\n');
      buffer = parts.pop(); // 保留未完成的部分

      for (var i = 0; i < parts.length; i++) {
        processSSEPart(parts[i]);
      }

      return processChunk();
    });
  }

  function processSSEPart(part) {
    if (!part.trim()) return;
    var eventName = 'message';
    var dataStr = '';
    var lines = part.split('\n');
    for (var j = 0; j < lines.length; j++) {
      var line = lines[j];
      if (line.startsWith('event: ')) {
        eventName = line.slice(7);
      } else if (line.startsWith('data: ')) {
        dataStr = line.slice(6);
      }
    }
    if (dataStr) {
      try {
        var parsed = JSON.parse(dataStr);
        onEvent(eventName, parsed);
      } catch (e) {
        // 解析失败时静默忽略，防止中断整个流
      }
    }
  }

  return processChunk();
}

// ===== Upload & Process =====
function setStatus(text, progress) {
  if (statusArea) statusArea.classList.remove('hidden');
  if (statusText) statusText.textContent = text;
  if (progressBar) {
    progressBar.style.width = progress + '%';
    progressBar.style.transition = 'width 0.5s ease';
  }
}

function showDownloadButton(url) {
  if (!downloadBtn) return;
  if (!url || url === '#') return;
  downloadBtn.href = url;
  downloadBtn.classList.remove('hidden');
  downloadBtn.style.display = '';
  downloadBtn.setAttribute('href', url);
  downloadBtn.textContent = '下载 Excel';
}

async function processFiles() {
  if (selectedFiles.length === 0) return;
  if (!selectedFiles.every(f => f.status === 'ready')) return;
  if (isUploading) return;

  isUploading = true;

  if (processBtn) {
    processBtn.disabled = true;
    processBtn.classList.add('hidden');
  }
  if (downloadBtn) downloadBtn.classList.add('hidden');

  const total = selectedFiles.length;
  setStatus('正在上传 ' + total + ' 个文件...', 5);

  // Mark all processing
  for (let i = 0; i < selectedFiles.length; i++) updateFileStatus(i, 'processing');

  const formData = new FormData();
  selectedFiles.forEach(item => formData.append('files', item.file));

  try {
    var controller = new AbortController();
    var timeoutId = setTimeout(function() { controller.abort(); }, 300000); // 5分钟超时

    var res;
    try {
      res = await fetch('/upload', { method: 'POST', body: formData, signal: controller.signal });
    } finally {
      clearTimeout(timeoutId);
    }

    // 非 SSE 错误（如 422）
    if (!res.ok) {
      var errMsg = '上传失败';
      var errText = await res.text();
      try {
        var errData = JSON.parse(errText);
        errMsg = errData.detail || errData.message || errMsg;
      } catch (e) {
        // 响应体不是 JSON，使用默认消息
      }
      throw new Error(errMsg);
    }

    // 统一走 SSE 流读取，内部自动解析
    var downloadUrl = null;
    await readSSEStream(res, function(event, data) {
      switch (event) {
        case 'progress':
          setStatus(data.message, data.percent);
          break;

        case 'file_done':
          updateFileStatus(data.index, 'done');
          break;

        case 'error':
          showError(data.message);
          break;

        case 'done':
          if (data.success) {
            var doneCount = selectedFiles.filter(function(f) { return f.status === 'done'; }).length;
            var errCount = (data.errors || []).length;
            if (errCount > 0) {
              setStatus('完成 ' + doneCount + '/' + total + ' 篇，' + errCount + ' 个失败', 100);
            } else {
              setStatus('全部完成！成功处理 ' + doneCount + ' 篇论文', 100);
            }
            if (data.download_url && data.results && data.results.length > 0) {
              downloadUrl = data.download_url;
            }
          } else {
            // 所有文件失败
            selectedFiles.forEach(function(item, i) {
              if (item.status === 'processing') updateFileStatus(i, 'error', '处理失败');
            });
            setStatus('处理失败：' + (data.errors || []).join('；'), 0);
          }
          break;

        case 'fatal':
          showError(data.message);
          selectedFiles.forEach(function(item, i) {
            if (item.status === 'processing') updateFileStatus(i, 'error', data.message);
          });
          setStatus('错误：' + data.message, 0);
          break;
      }
    });

    // 流读取完毕后显示下载按钮
    if (downloadUrl) {
      showDownloadButton(downloadUrl);
      showSuccess('处理完成，可以下载 Excel');
      // 上传成功后刷新 beta 卡密（当前卡密可能已用完）
      if (typeof fetchNextBetaCode === 'function') fetchNextBetaCode();
    }
  } catch (err) {
    selectedFiles.forEach((item, i) => {
      if (item.status === 'processing') updateFileStatus(i, 'error', err.message);
    });
    setStatus('错误：' + err.message, 0);
    showError(err.message || '网络错误，请检查连接后重试');
  } finally {
    isUploading = false;
    if (processBtn) {
      processBtn.disabled = false;
    }
  }
}

if (processBtn) {
  processBtn.addEventListener('click', processFiles);
}

// Download button click handler
if (downloadBtn) {
  downloadBtn.addEventListener('click', function(e) {
    var href = this.getAttribute('href');
    if (!href || href === '#') {
      e.preventDefault();
      showError('没有可下载的数据');
      return;
    }
  });
}
