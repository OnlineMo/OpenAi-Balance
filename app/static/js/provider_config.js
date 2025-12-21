// Provider Configuration Management
// This file handles the multi-provider configuration UI

// Provider data storage
let providersConfig = [];
let editingProviderIndex = -1; // -1 means adding new, >= 0 means editing

// DOM Elements
const providerModal = document.getElementById("providerModal");
const providerModalTitle = document.getElementById("providerModalTitle");
const providersContainer = document.getElementById("PROVIDERS_container");
const defaultProviderSelect = document.getElementById("DEFAULT_PROVIDER");

// Provider Modal Elements
const providerNameInput = document.getElementById("providerName");
const providerPathInput = document.getElementById("providerPath");
const providerBaseUrlInput = document.getElementById("providerBaseUrl");
const providerApiKeysInput = document.getElementById("providerApiKeys");
const providerCustomHeadersInput = document.getElementById("providerCustomHeaders");
const providerTimeoutInput = document.getElementById("providerTimeout");
const providerMaxFailuresInput = document.getElementById("providerMaxFailures");
const providerMaxRetriesInput = document.getElementById("providerMaxRetries");
const providerEnabledInput = document.getElementById("providerEnabled");
const providerTestModelInput = document.getElementById("providerTestModel");
const pathPreviewContent = document.getElementById("pathPreviewContent");

// Initialize provider configuration UI
document.addEventListener("DOMContentLoaded", function () {
  // Add Provider button
  const addProviderBtn = document.getElementById("addProviderBtn");
  if (addProviderBtn) {
    addProviderBtn.addEventListener("click", () => openProviderModal());
  }

  // Provider Modal buttons
  const closeProviderModalBtn = document.getElementById("closeProviderModalBtn");
  const cancelProviderBtn = document.getElementById("cancelProviderBtn");
  const confirmProviderBtn = document.getElementById("confirmProviderBtn");

  if (closeProviderModalBtn) {
    closeProviderModalBtn.addEventListener("click", () => closeModal(providerModal));
  }
  if (cancelProviderBtn) {
    cancelProviderBtn.addEventListener("click", () => closeModal(providerModal));
  }
  if (confirmProviderBtn) {
    confirmProviderBtn.addEventListener("click", handleProviderConfirm);
  }

  // Auto-fill path from name and update URL preview
  if (providerNameInput && providerPathInput) {
    providerNameInput.addEventListener("input", function () {
      if (!providerPathInput.value || providerPathInput.value === providerNameInput.dataset.lastAutoValue) {
        const autoValue = this.value.toLowerCase().replace(/[^a-z0-9-]/g, "");
        providerPathInput.value = autoValue;
        providerNameInput.dataset.lastAutoValue = autoValue;
        updatePathPreview(autoValue);
      }
    });
  }

  // Update URL preview when path changes
  if (providerPathInput) {
    providerPathInput.addEventListener("input", function () {
      updatePathPreview(this.value);
    });
  }

  // Click outside modal to close
  window.addEventListener("click", (event) => {
    if (event.target === providerModal) {
      closeModal(providerModal);
    }
  });
});

/**
 * Updates the URL path preview with the current path value
 * @param {string} path - The path value to display
 */
function updatePathPreview(path) {
  if (!pathPreviewContent) return;

  const displayPath = path.trim() || "{path}";
  const pathClass = path.trim() ? "text-blue-600 font-semibold" : "text-gray-400";

  pathPreviewContent.innerHTML = `
    <div>/<span class="${pathClass}">${escapeHtml(displayPath)}</span>/v1/chat/completions</div>
    <div>/hf/<span class="${pathClass}">${escapeHtml(displayPath)}</span>/v1/chat/completions</div>
    <div>/openai/<span class="${pathClass}">${escapeHtml(displayPath)}</span>/v1/chat/completions</div>
  `;
}

/**
 * Opens the provider modal for adding or editing
 * @param {number} index - Index of provider to edit, or -1 for new
 */
function openProviderModal(index = -1) {
  editingProviderIndex = index;

  // 获取代码执行工具复选框
  const providerCodeExecutionEnabledInput = document.getElementById("providerCodeExecutionEnabled");
  const providerModelRequestKeySelect = document.getElementById("providerModelRequestKey");

  // 隐藏模型选择下拉框
  const modelSelectContainer = document.getElementById("providerModelSelectContainer");
  if (modelSelectContainer) modelSelectContainer.style.display = "none";

  if (index >= 0 && providersConfig[index]) {
    // Editing existing provider
    const provider = providersConfig[index];
    if (providerModalTitle) providerModalTitle.textContent = "编辑提供商";
    if (providerNameInput) providerNameInput.value = provider.name || "";
    if (providerPathInput) providerPathInput.value = provider.path || "";
    if (providerBaseUrlInput) providerBaseUrlInput.value = provider.base_url || "";
    if (providerApiKeysInput) providerApiKeysInput.value = (provider.api_keys || []).join("\n");
    if (providerCustomHeadersInput) {
      providerCustomHeadersInput.value = provider.custom_headers
        ? JSON.stringify(provider.custom_headers, null, 2)
        : "";
    }
    if (providerTimeoutInput) providerTimeoutInput.value = provider.timeout || 300;
    if (providerMaxFailuresInput) providerMaxFailuresInput.value = provider.max_failures || 3;
    if (providerMaxRetriesInput) providerMaxRetriesInput.value = provider.max_retries || 3;
    if (providerTestModelInput) providerTestModelInput.value = provider.test_model || "";
    if (providerCodeExecutionEnabledInput) providerCodeExecutionEnabledInput.checked = provider.tools_code_execution_enabled === true;
    if (providerEnabledInput) providerEnabledInput.checked = provider.enabled !== false;
    // Update path preview
    updatePathPreview(provider.path || "");
    // Update model request key options and set value
    updateModelRequestKeyOptions();
    if (providerModelRequestKeySelect) {
      providerModelRequestKeySelect.value = provider.model_request_key || "";
    }
  } else {
    // Adding new provider
    if (providerModalTitle) providerModalTitle.textContent = "添加提供商";
    clearProviderModal();
  }

  openModal(providerModal);
}

/**
 * Clears the provider modal form
 */
function clearProviderModal() {
  const providerCodeExecutionEnabledInput = document.getElementById("providerCodeExecutionEnabled");
  const providerModelRequestKeySelect = document.getElementById("providerModelRequestKey");

  if (providerNameInput) providerNameInput.value = "";
  if (providerPathInput) providerPathInput.value = "";
  if (providerBaseUrlInput) providerBaseUrlInput.value = "";
  if (providerApiKeysInput) providerApiKeysInput.value = "";
  if (providerCustomHeadersInput) providerCustomHeadersInput.value = "";
  if (providerTimeoutInput) providerTimeoutInput.value = 300;
  if (providerMaxFailuresInput) providerMaxFailuresInput.value = 3;
  if (providerMaxRetriesInput) providerMaxRetriesInput.value = 3;
  if (providerTestModelInput) providerTestModelInput.value = "";
  if (providerCodeExecutionEnabledInput) providerCodeExecutionEnabledInput.checked = false;
  if (providerEnabledInput) providerEnabledInput.checked = true;
  if (providerNameInput) providerNameInput.dataset.lastAutoValue = "";
  if (providerModelRequestKeySelect) {
    providerModelRequestKeySelect.innerHTML = '<option value="">使用第一个 API 密钥</option>';
  }
  // Reset path preview
  updatePathPreview("");
}

/**
 * Handles the confirm button click in provider modal
 */
function handleProviderConfirm() {
  // Validate required fields
  const name = providerNameInput?.value?.trim();
  const path = providerPathInput?.value?.trim();
  const baseUrl = providerBaseUrlInput?.value?.trim();

  if (!name) {
    showNotification("请输入提供商名称", "warning");
    return;
  }
  if (!path) {
    showNotification("请输入路由路径", "warning");
    return;
  }
  if (!baseUrl) {
    showNotification("请输入 API Base URL", "warning");
    return;
  }

  // Check for duplicate name (except when editing the same provider)
  const duplicateIndex = providersConfig.findIndex(
    (p, i) => p.name === name && i !== editingProviderIndex
  );
  if (duplicateIndex >= 0) {
    showNotification("提供商名称已存在", "warning");
    return;
  }

  // Parse API keys
  const apiKeysText = providerApiKeysInput?.value || "";
  const apiKeys = apiKeysText
    .split("\n")
    .map((k) => k.trim())
    .filter((k) => k.length > 0);

  // Parse custom headers
  let customHeaders = {};
  const customHeadersText = providerCustomHeadersInput?.value?.trim();
  if (customHeadersText) {
    try {
      customHeaders = JSON.parse(customHeadersText);
      if (typeof customHeaders !== "object" || Array.isArray(customHeaders)) {
        throw new Error("Invalid format");
      }
    } catch (e) {
      showNotification("自定义 Headers 格式无效，请使用 JSON 对象格式", "warning");
      return;
    }
  }

  // 获取代码执行工具复选框和模型请求密钥
  const providerCodeExecutionEnabledInput = document.getElementById("providerCodeExecutionEnabled");
  const providerModelRequestKeySelect = document.getElementById("providerModelRequestKey");

  // Build provider object
  const provider = {
    name: name,
    path: path,
    base_url: baseUrl,
    api_keys: apiKeys,
    model_request_key: providerModelRequestKeySelect?.value || "",
    custom_headers: customHeaders,
    timeout: parseInt(providerTimeoutInput?.value) || 300,
    max_failures: parseInt(providerMaxFailuresInput?.value) || 3,
    max_retries: parseInt(providerMaxRetriesInput?.value) || 3,
    test_model: providerTestModelInput?.value?.trim() || "",
    tools_code_execution_enabled: providerCodeExecutionEnabledInput?.checked === true,
    enabled: providerEnabledInput?.checked !== false,
  };

  if (editingProviderIndex >= 0) {
    // Update existing provider
    providersConfig[editingProviderIndex] = provider;
    showNotification("提供商已更新", "success");
  } else {
    // Add new provider
    providersConfig.push(provider);
    showNotification("提供商已添加", "success");
  }

  // Refresh UI
  renderProvidersList();
  updateDefaultProviderOptions();
  closeModal(providerModal);
}

/**
 * Deletes a provider by index
 * @param {number} index - Index of provider to delete
 */
function deleteProvider(index) {
  if (index < 0 || index >= providersConfig.length) return;

  const provider = providersConfig[index];
  if (confirm(`确定要删除提供商 "${provider.name}" 吗？`)) {
    providersConfig.splice(index, 1);
    renderProvidersList();
    updateDefaultProviderOptions();
    showNotification("提供商已删除", "success");
  }
}

/**
 * Renders the providers list in the UI
 */
function renderProvidersList() {
  if (!providersContainer) return;

  if (providersConfig.length === 0) {
    providersContainer.innerHTML =
      '<div class="text-gray-500 text-sm italic">点击下方按钮添加提供商配置</div>';
    // 显示默认提供商配置
    updateDefaultProviderSectionsVisibility();
    return;
  }

  providersContainer.innerHTML = "";

  providersConfig.forEach((provider, index) => {
    const card = document.createElement("div");
    card.className = `provider-card p-4 rounded-lg border ${
      provider.enabled ? "border-blue-200 bg-blue-50" : "border-gray-200 bg-gray-50"
    }`;

    const statusBadge = provider.enabled
      ? '<span class="px-2 py-1 text-xs rounded-full bg-green-100 text-green-700">启用</span>'
      : '<span class="px-2 py-1 text-xs rounded-full bg-gray-100 text-gray-500">禁用</span>';

    const codeExecutionBadge = provider.tools_code_execution_enabled
      ? '<span class="px-2 py-1 text-xs rounded-full bg-purple-100 text-purple-700" title="代码执行已启用"><i class="fas fa-code"></i></span>'
      : '';

    card.innerHTML = `
      <div class="flex items-center justify-between mb-2">
        <div class="flex items-center gap-2">
          <span class="font-semibold text-gray-800">${escapeHtml(provider.name)}</span>
          ${statusBadge}
          ${codeExecutionBadge}
        </div>
        <div class="flex items-center gap-2">
          <button
            type="button"
            class="text-blue-500 hover:text-blue-700 transition-colors"
            onclick="openProviderModal(${index})"
            title="编辑"
          >
            <i class="fas fa-edit"></i>
          </button>
          <button
            type="button"
            class="text-red-500 hover:text-red-700 transition-colors"
            onclick="deleteProvider(${index})"
            title="删除"
          >
            <i class="fas fa-trash-alt"></i>
          </button>
        </div>
      </div>
      <div class="text-sm text-gray-600 space-y-1">
        <div><span class="font-medium">路径:</span> /${escapeHtml(provider.path)}/v1/*</div>
        <div><span class="font-medium">Base URL:</span> ${escapeHtml(provider.base_url)}</div>
        <div><span class="font-medium">API Keys:</span> ${provider.api_keys?.length || 0} 个</div>
      </div>
    `;

    providersContainer.appendChild(card);
  });

  // 更新默认提供商配置的显示/隐藏
  updateDefaultProviderSectionsVisibility();
}

/**
 * Updates the visibility of default provider configuration sections
 * based on whether custom providers are configured
 */
function updateDefaultProviderSectionsVisibility() {
  const hasCustomProviders = providersConfig && providersConfig.length > 0;

  // 需要隐藏/显示的元素
  const sectionsToToggle = [
    'defaultProviderKeysSection',    // 默认 API 密钥
    'defaultProviderConfigSection',  // BASE_URL 和 CUSTOM_HEADERS
  ];

  sectionsToToggle.forEach(sectionId => {
    const section = document.getElementById(sectionId);
    if (section) {
      section.style.display = hasCustomProviders ? 'none' : '';
    }
  });

  // 隐藏/显示整个模型配置部分（包括导航标签）
  const modelSection = document.getElementById('model-section');
  if (modelSection) {
    modelSection.style.display = hasCustomProviders ? 'none' : '';
  }

  // 隐藏/显示模型配置的导航标签
  const modelNavTab = document.querySelector('[data-section="model-section"]');
  if (modelNavTab) {
    modelNavTab.style.display = hasCustomProviders ? 'none' : '';
  }
}

/**
 * Updates the default provider select options
 */
function updateDefaultProviderOptions() {
  if (!defaultProviderSelect) return;

  const currentValue = defaultProviderSelect.value;

  // Clear existing options except the first one
  while (defaultProviderSelect.options.length > 1) {
    defaultProviderSelect.remove(1);
  }

  // Add options for each provider
  providersConfig.forEach((provider) => {
    if (provider.enabled) {
      const option = document.createElement("option");
      option.value = provider.name;
      option.textContent = provider.name;
      defaultProviderSelect.appendChild(option);
    }
  });

  // Restore previous selection if still valid
  if (currentValue) {
    const optionExists = Array.from(defaultProviderSelect.options).some(
      (opt) => opt.value === currentValue
    );
    if (optionExists) {
      defaultProviderSelect.value = currentValue;
    }
  }
}

/**
 * Populates providers configuration from loaded config
 * @param {object} config - The configuration object
 */
function populateProvidersConfig(config) {
  // Parse PROVIDERS_CONFIG from JSON string
  if (config.PROVIDERS_CONFIG) {
    try {
      if (typeof config.PROVIDERS_CONFIG === "string") {
        providersConfig = JSON.parse(config.PROVIDERS_CONFIG);
      } else if (Array.isArray(config.PROVIDERS_CONFIG)) {
        providersConfig = config.PROVIDERS_CONFIG;
      }
    } catch (e) {
      console.error("Failed to parse PROVIDERS_CONFIG:", e);
      providersConfig = [];
    }
  } else {
    providersConfig = [];
  }

  // Set default provider
  if (defaultProviderSelect && config.DEFAULT_PROVIDER) {
    // First update options
    updateDefaultProviderOptions();
    // Then set value
    defaultProviderSelect.value = config.DEFAULT_PROVIDER;
  }

  // Render the list
  renderProvidersList();
  updateDefaultProviderOptions();

  // Render provider keys section in API config tab
  renderProviderKeysSection();
}

/**
 * Collects providers configuration for saving
 * @returns {object} Object containing DEFAULT_PROVIDER and PROVIDERS_CONFIG
 */
function collectProvidersConfig() {
  return {
    DEFAULT_PROVIDER: defaultProviderSelect?.value || "default",
    PROVIDERS_CONFIG: JSON.stringify(providersConfig),
  };
}

/**
 * Escapes HTML special characters
 * @param {string} text - Text to escape
 * @returns {string} Escaped text
 */
function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

/**
 * Renders provider API keys sections in the API config tab
 */
function renderProviderKeysSection() {
  const container = document.getElementById("customProviderKeysContainer");
  if (!container) return;

  // 更新默认密钥计数
  const defaultKeysCount = document.getElementById("defaultKeysCount");
  if (defaultKeysCount && typeof allApiKeys !== "undefined") {
    defaultKeysCount.textContent = `(${allApiKeys.length} 个)`;
  }

  // 清空容器
  container.innerHTML = "";

  // 如果没有提供商配置，不显示任何内容
  if (!providersConfig || providersConfig.length === 0) {
    return;
  }

  // 为每个提供商创建密钥部分
  providersConfig.forEach((provider, index) => {
    if (!provider.enabled) return;

    const keysCount = provider.api_keys ? provider.api_keys.length : 0;
    const section = document.createElement("div");
    section.className = "provider-keys-section border rounded-lg p-4 bg-gray-50";
    section.setAttribute("data-provider", provider.name);

    section.innerHTML = `
      <div class="flex items-center justify-between mb-3">
        <h3 class="font-semibold text-gray-700 flex items-center gap-2">
          <i class="fas fa-cloud text-blue-500"></i>
          <span>${escapeHtml(provider.name)} API 密钥</span>
          <span class="text-sm text-gray-500">(${keysCount} 个)</span>
        </h3>
        <div class="flex gap-2">
          <button
            type="button"
            class="text-sm bg-blue-500 hover:bg-blue-600 text-white px-3 py-1 rounded flex items-center gap-1"
            onclick="openAddKeyModal('${escapeHtml(provider.name)}')"
          >
            <i class="fas fa-plus"></i> 添加
          </button>
        </div>
      </div>
      <div class="text-xs text-gray-400 mb-2">路由: /${escapeHtml(provider.path)}/v1/*</div>
      <div class="mb-2">
        <input type="search" id="providerKeySearch_${index}" placeholder="搜索密钥..." class="w-full px-3 py-2 rounded-lg form-input-themed text-sm" oninput="filterProviderKeys(${index})">
      </div>
      <div class="array-container" id="providerKeysContainer_${index}" style="max-height: 200px;">
        ${renderProviderKeysList(provider.api_keys || [], index)}
      </div>
    `;

    container.appendChild(section);
  });
}

/**
 * Renders the list of keys for a provider
 * @param {Array} keys - Array of API keys
 * @param {number} providerIndex - Index of the provider
 * @returns {string} HTML string
 */
function renderProviderKeysList(keys, providerIndex) {
  if (!keys || keys.length === 0) {
    return '<div class="text-gray-500 text-sm italic p-2">暂无密钥</div>';
  }

  let html = '';
  keys.forEach((key, keyIndex) => {
    const maskedKey = key.length > 12 ? key.substring(0, 8) + "..." + key.substring(key.length - 4) : key;
    html += `
      <div class="array-item flex items-center mb-2 gap-2" data-key-index="${keyIndex}">
        <div class="flex items-center flex-grow rounded-md focus-within:border-blue-500 focus-within:ring focus-within:ring-blue-500 focus-within:ring-opacity-50" style="border: 1px solid rgba(0, 0, 0, 0.12); background-color: transparent;">
          <input
            type="text"
            class="array-input flex-grow px-3 py-2 border-none rounded-l-md focus:outline-none form-input-themed sensitive-input rounded-r-md"
            data-real-value="${escapeHtml(key)}"
            value="${escapeHtml(maskedKey)}"
            data-provider-index="${providerIndex}"
            data-key-index="${keyIndex}"
            onfocus="unmaskProviderKey(this)"
            onblur="maskProviderKey(this)"
          >
        </div>
        <button
          type="button"
          class="remove-btn text-gray-400 hover:text-red-500 focus:outline-none transition-colors duration-150"
          onclick="removeProviderKey(${providerIndex}, ${keyIndex})"
          title="删除"
        >
          <i class="fas fa-trash-alt"></i>
        </button>
      </div>
    `;
  });
  return html;
}

/**
 * Unmasks a provider key input field
 * @param {HTMLInputElement} field - The input field
 */
function unmaskProviderKey(field) {
  if (field.hasAttribute("data-real-value")) {
    field.value = field.getAttribute("data-real-value");
  }
}

/**
 * Masks a provider key input field
 * @param {HTMLInputElement} field - The input field
 */
function maskProviderKey(field) {
  const realValue = field.value;
  if (realValue && realValue.length > 12) {
    field.setAttribute("data-real-value", realValue);
    field.value = realValue.substring(0, 8) + "..." + realValue.substring(realValue.length - 4);

    // 更新 providersConfig 中的值
    const providerIndex = parseInt(field.getAttribute("data-provider-index"));
    const keyIndex = parseInt(field.getAttribute("data-key-index"));
    if (!isNaN(providerIndex) && !isNaN(keyIndex) && providersConfig[providerIndex]) {
      providersConfig[providerIndex].api_keys[keyIndex] = realValue;
    }
  }
}

/**
 * Filters provider keys based on search input
 * @param {number} providerIndex - Index of the provider
 */
function filterProviderKeys(providerIndex) {
  const searchInput = document.getElementById(`providerKeySearch_${providerIndex}`);
  const container = document.getElementById(`providerKeysContainer_${providerIndex}`);
  if (!searchInput || !container) return;

  const searchTerm = searchInput.value.toLowerCase().trim();
  const items = container.querySelectorAll('.array-item');

  items.forEach(item => {
    const input = item.querySelector('input');
    if (!input) return;

    const realValue = input.getAttribute('data-real-value') || input.value;
    const matches = realValue.toLowerCase().includes(searchTerm);
    item.style.display = matches ? '' : 'none';
  });
}

/**
 * Toggles the visibility of provider keys
 * @param {string} providerName - Name of the provider
 */
function toggleProviderKeys(providerName) {
  const index = providersConfig.findIndex(p => p.name === providerName);
  if (index < 0) return;

  const keysList = document.getElementById(`providerKeys_${index}`);
  const toggleIcon = document.getElementById(`toggleIcon_${index}`);

  if (keysList) {
    if (keysList.style.display === "none") {
      keysList.style.display = "block";
      if (toggleIcon) toggleIcon.className = "fas fa-eye-slash";
    } else {
      keysList.style.display = "none";
      if (toggleIcon) toggleIcon.className = "fas fa-eye";
    }
  }
}

/**
 * Removes a key from a provider
 * @param {number} providerIndex - Index of the provider
 * @param {number} keyIndex - Index of the key to remove
 */
function removeProviderKey(providerIndex, keyIndex) {
  if (providerIndex < 0 || providerIndex >= providersConfig.length) return;

  const provider = providersConfig[providerIndex];
  if (!provider.api_keys || keyIndex < 0 || keyIndex >= provider.api_keys.length) return;

  if (confirm(`确定要删除此密钥吗？`)) {
    provider.api_keys.splice(keyIndex, 1);
    renderProviderKeysSection();
    showNotification("密钥已删除", "success");
  }
}

/**
 * Opens the add key modal with a specific provider selected
 * @param {string} providerName - Name of the provider to add keys to
 */
function openAddKeyModal(providerName) {
  const apiKeyModal = document.getElementById("apiKeyModal");
  const apiKeyBulkInput = document.getElementById("apiKeyBulkInput");
  const targetProviderSelect = document.getElementById("apiKeyTargetProvider");

  if (apiKeyModal) {
    // 更新提供商选项
    if (typeof updateApiKeyTargetProviderOptions === "function") {
      updateApiKeyTargetProviderOptions();
    }

    // 设置目标提供商
    if (targetProviderSelect) {
      targetProviderSelect.value = providerName;
    }

    // 清空输入
    if (apiKeyBulkInput) {
      apiKeyBulkInput.value = "";
    }

    // 打开模态框
    if (typeof openModal === "function") {
      openModal(apiKeyModal);
    }
  }
}

/**
 * Fetches models from the provider's API and populates the model select dropdown
 */
async function fetchProviderModels() {
  const baseUrl = providerBaseUrlInput?.value?.trim();
  const apiKeysText = providerApiKeysInput?.value || "";
  const apiKeys = apiKeysText.split("\n").map(k => k.trim()).filter(k => k.length > 0);
  const modelRequestKeySelect = document.getElementById("providerModelRequestKey");
  const selectedModelRequestKey = modelRequestKeySelect?.value;

  if (!baseUrl) {
    showNotification("请先输入 API Base URL", "warning");
    return;
  }

  if (apiKeys.length === 0) {
    showNotification("请先输入至少一个 API 密钥", "warning");
    return;
  }

  const fetchBtn = document.getElementById("fetchProviderModelsBtn");
  const modelSelectContainer = document.getElementById("providerModelSelectContainer");
  const modelSelect = document.getElementById("providerModelSelect");

  if (!fetchBtn || !modelSelectContainer || !modelSelect) return;

  // 显示加载状态
  const originalIcon = fetchBtn.innerHTML;
  fetchBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
  fetchBtn.disabled = true;

  try {
    // 使用选定的模型请求密钥，如果没有选择则使用第一个 API 密钥
    const apiKey = selectedModelRequestKey || apiKeys[0];
    const modelsUrl = baseUrl.endsWith('/') ? `${baseUrl}models` : `${baseUrl}/models`;

    const response = await fetch(modelsUrl, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${apiKey}`,
        'Content-Type': 'application/json'
      }
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    const data = await response.json();
    const models = data.data || data.models || [];

    if (models.length === 0) {
      showNotification("未找到可用模型", "warning");
      return;
    }

    // 清空并填充下拉框
    modelSelect.innerHTML = '<option value="">-- 选择模型 --</option>';
    models.forEach(model => {
      const modelId = model.id || model.name || model;
      const option = document.createElement("option");
      option.value = modelId;
      option.textContent = modelId;
      modelSelect.appendChild(option);
    });

    // 显示下拉框
    modelSelectContainer.style.display = "block";
    showNotification(`成功获取 ${models.length} 个模型`, "success");

  } catch (error) {
    console.error("获取模型列表失败:", error);
    showNotification(`获取模型列表失败: ${error.message}`, "error");
  } finally {
    // 恢复按钮状态
    fetchBtn.innerHTML = originalIcon;
    fetchBtn.disabled = false;
  }
}

/**
 * Updates the model request key select options based on current API keys
 */
function updateModelRequestKeyOptions() {
  const modelRequestKeySelect = document.getElementById("providerModelRequestKey");
  if (!modelRequestKeySelect) return;

  const apiKeysText = providerApiKeysInput?.value || "";
  const apiKeys = apiKeysText.split("\n").map(k => k.trim()).filter(k => k.length > 0);

  // 保存当前选中的值
  const currentValue = modelRequestKeySelect.value;

  // 清空并重新填充选项
  modelRequestKeySelect.innerHTML = '<option value="">使用第一个 API 密钥</option>';

  apiKeys.forEach((key, index) => {
    const maskedKey = key.length > 12 ? key.substring(0, 8) + "..." + key.substring(key.length - 4) : key;
    const option = document.createElement("option");
    option.value = key;
    option.textContent = `密钥 ${index + 1}: ${maskedKey}`;
    modelRequestKeySelect.appendChild(option);
  });

  // 恢复之前选中的值（如果仍然存在）
  if (currentValue && apiKeys.includes(currentValue)) {
    modelRequestKeySelect.value = currentValue;
  }
}

/**
 * Selects a model from the dropdown and fills the test model input
 * @param {string} modelId - The selected model ID
 */
function selectProviderModel(modelId) {
  if (modelId && providerTestModelInput) {
    providerTestModelInput.value = modelId;
  }
}

// Export functions for use in config_editor.js
window.populateProvidersConfig = populateProvidersConfig;
window.collectProvidersConfig = collectProvidersConfig;
window.openProviderModal = openProviderModal;
window.deleteProvider = deleteProvider;
window.renderProviderKeysSection = renderProviderKeysSection;
window.toggleProviderKeys = toggleProviderKeys;
window.removeProviderKey = removeProviderKey;
window.openAddKeyModal = openAddKeyModal;
window.unmaskProviderKey = unmaskProviderKey;
window.maskProviderKey = maskProviderKey;
window.filterProviderKeys = filterProviderKeys;
window.fetchProviderModels = fetchProviderModels;
window.selectProviderModel = selectProviderModel;
window.updateDefaultProviderSectionsVisibility = updateDefaultProviderSectionsVisibility;
window.updateModelRequestKeyOptions = updateModelRequestKeyOptions;
