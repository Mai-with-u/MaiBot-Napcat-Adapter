"""
静态资源 - 提供 HTML 页面
"""


def get_index_html() -> str:
    """返回主页面 HTML"""
    return '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MaiBot Adapter 配置管理</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 800px;
            margin: 0 auto;
        }
        
        h1 {
            color: white;
            text-align: center;
            margin-bottom: 30px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }
        
        .card {
            background: white;
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 20px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
        }
        
        .card h2 {
            color: #333;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #667eea;
        }
        
        .form-group {
            margin-bottom: 20px;
        }
        
        .form-group label {
            display: block;
            font-weight: 600;
            color: #555;
            margin-bottom: 8px;
        }
        
        .form-group select {
            width: 100%;
            padding: 12px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            font-size: 16px;
            transition: border-color 0.3s;
        }
        
        .form-group select:focus {
            outline: none;
            border-color: #667eea;
        }
        
        .form-group input[type="password"],
        .form-group input[type="text"] {
            width: 100%;
            padding: 12px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            font-size: 16px;
            transition: border-color 0.3s;
        }
        
        .form-group input[type="password"]:focus,
        .form-group input[type="text"]:focus {
            outline: none;
            border-color: #667eea;
        }
        
        .list-container {
            background: #f8f9fa;
            border-radius: 8px;
            padding: 16px;
        }
        
        .list-items {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-bottom: 12px;
            min-height: 40px;
        }
        
        .list-item {
            background: #667eea;
            color: white;
            padding: 6px 12px;
            border-radius: 20px;
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 14px;
        }
        
        .list-item .remove-btn {
            background: rgba(255,255,255,0.3);
            border: none;
            color: white;
            width: 20px;
            height: 20px;
            border-radius: 50%;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 12px;
            transition: background 0.3s;
        }
        
        .list-item .remove-btn:hover {
            background: rgba(255,255,255,0.5);
        }
        
        .add-form {
            display: flex;
            gap: 10px;
        }
        
        .add-form input {
            flex: 1;
            padding: 10px 14px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            font-size: 14px;
        }
        
        .add-form input:focus {
            outline: none;
            border-color: #667eea;
        }
        
        .add-form button {
            padding: 10px 20px;
            background: #667eea;
            color: white;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-weight: 600;
            transition: background 0.3s;
        }
        
        .add-form button:hover {
            background: #5a6fd6;
        }
        
        .login-btn {
            width: 100%;
            padding: 14px 20px;
            background: #667eea;
            color: white;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-weight: 600;
            font-size: 16px;
            transition: background 0.3s;
        }
        
        .login-btn:hover {
            background: #5a6fd6;
        }
        
        .login-btn:disabled {
            background: #ccc;
            cursor: not-allowed;
        }
        
        .status {
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 12px 24px;
            border-radius: 8px;
            color: white;
            font-weight: 600;
            opacity: 0;
            transform: translateY(-20px);
            transition: all 0.3s;
            z-index: 1000;
        }
        
        .status.show {
            opacity: 1;
            transform: translateY(0);
        }
        
        .status.success {
            background: #28a745;
        }
        
        .status.error {
            background: #dc3545;
        }
        
        .loading {
            text-align: center;
            padding: 40px;
            color: #666;
        }
        
        .empty-list {
            color: #999;
            font-style: italic;
            padding: 10px 0;
        }
        
        .hidden {
            display: none !important;
        }
        
        .login-container {
            max-width: 400px;
            margin: 100px auto;
        }
        
        .login-container .card {
            text-align: center;
        }
        
        .login-container h2 {
            border-bottom: none !important;
        }
        
        .login-icon {
            font-size: 48px;
            margin-bottom: 10px;
        }
    </style>
</head>
<body>
    <!-- 登录界面 -->
    <div id="login-page" class="login-container hidden">
        <h1>🤖 MaiBot Adapter</h1>
        <div class="card">
            <div class="login-icon">🔐</div>
            <h2>请输入访问令牌</h2>
            <div class="form-group">
                <input type="password" id="token-input" placeholder="输入 Token" onkeypress="if(event.key==='Enter') login()" />
            </div>
            <button class="login-btn" onclick="login()">登录</button>
        </div>
    </div>
    
    <!-- 主界面 -->
    <div id="main-page" class="container hidden">
        <h1>🤖 MaiBot Adapter 配置管理</h1>
        
        <div class="card">
            <h2>📋 群聊设置</h2>
            <div class="form-group">
                <label for="group_list_type">群聊列表类型</label>
                <select id="group_list_type" onchange="updateConfig('group_list_type', this.value)">
                    <option value="whitelist">白名单 (仅允许列表中的群聊)</option>
                    <option value="blacklist">黑名单 (禁止列表中的群聊)</option>
                </select>
            </div>
            <div class="form-group">
                <label>群聊列表</label>
                <div class="list-container">
                    <div id="group_list" class="list-items">
                        <div class="loading">加载中...</div>
                    </div>
                    <div class="add-form">
                        <input type="number" id="new_group" placeholder="输入群号" />
                        <button onclick="addItem('group_list')">添加</button>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="card">
            <h2>💬 私聊设置</h2>
            <div class="form-group">
                <label for="private_list_type">私聊列表类型</label>
                <select id="private_list_type" onchange="updateConfig('private_list_type', this.value)">
                    <option value="whitelist">白名单 (仅允许列表中的用户)</option>
                    <option value="blacklist">黑名单 (禁止列表中的用户)</option>
                </select>
            </div>
            <div class="form-group">
                <label>私聊列表</label>
                <div class="list-container">
                    <div id="private_list" class="list-items">
                        <div class="loading">加载中...</div>
                    </div>
                    <div class="add-form">
                        <input type="number" id="new_private" placeholder="输入QQ号" />
                        <button onclick="addItem('private_list')">添加</button>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <div id="status" class="status"></div>
    
    <script>
        let config = {
            group_list_type: 'whitelist',
            group_list: [],
            private_list_type: 'whitelist',
            private_list: []
        };
        
        // 获取存储的 token
        function getStoredToken() {
            return localStorage.getItem('webui_token') || '';
        }
        
        // 存储 token
        function storeToken(token) {
            localStorage.setItem('webui_token', token);
        }
        
        // 清除 token
        function clearToken() {
            localStorage.removeItem('webui_token');
        }
        
        // 获取带认证的 headers
        function getAuthHeaders() {
            const token = getStoredToken();
            const headers = { 'Content-Type': 'application/json' };
            if (token) {
                headers['Authorization'] = 'Bearer ' + token;
            }
            return headers;
        }
        
        // 显示登录页面
        function showLoginPage() {
            document.getElementById('login-page').classList.remove('hidden');
            document.getElementById('main-page').classList.add('hidden');
        }
        
        // 显示主页面
        function showMainPage() {
            document.getElementById('login-page').classList.add('hidden');
            document.getElementById('main-page').classList.remove('hidden');
        }
        
        // 检查认证状态
        async function checkAuth() {
            try {
                const response = await fetch('/api/auth/check', {
                    headers: getAuthHeaders()
                });
                const data = await response.json();
                
                if (!data.required) {
                    // 不需要认证
                    showMainPage();
                    await loadConfig();
                } else if (data.valid) {
                    // 需要认证且当前 token 有效
                    showMainPage();
                    await loadConfig();
                } else {
                    // 需要认证但 token 无效
                    clearToken();
                    showLoginPage();
                }
            } catch (error) {
                showStatus('检查认证状态失败: ' + error.message, 'error');
                showLoginPage();
            }
        }
        
        // 登录
        async function login() {
            const tokenInput = document.getElementById('token-input');
            const token = tokenInput.value.trim();
            
            if (!token) {
                showStatus('请输入 Token', 'error');
                return;
            }
            
            try {
                const response = await fetch('/api/auth/verify', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ token })
                });
                const data = await response.json();
                
                if (data.success) {
                    storeToken(token);
                    showStatus('登录成功', 'success');
                    tokenInput.value = '';
                    showMainPage();
                    await loadConfig();
                } else {
                    showStatus(data.message || 'Token 错误', 'error');
                }
            } catch (error) {
                showStatus('登录失败: ' + error.message, 'error');
            }
        }
        
        // 加载配置
        async function loadConfig() {
            try {
                const response = await fetch('/api/config', {
                    headers: getAuthHeaders()
                });
                
                if (response.status === 401) {
                    // 未授权，跳转到登录页
                    clearToken();
                    showLoginPage();
                    showStatus('登录已过期，请重新登录', 'error');
                    return;
                }
                
                const data = await response.json();
                
                if (data.success === false) {
                    showStatus('加载配置失败: ' + (data.error || '未知错误'), 'error');
                    return;
                }
                
                config = data;
                renderConfig();
            } catch (error) {
                showStatus('加载配置失败: ' + error.message, 'error');
            }
        }
        
        // 渲染配置
        function renderConfig() {
            // 设置选择框
            document.getElementById('group_list_type').value = config.group_list_type || 'whitelist';
            document.getElementById('private_list_type').value = config.private_list_type || 'whitelist';
            
            // 渲染列表
            renderList('group_list', config.group_list || []);
            renderList('private_list', config.private_list || []);
        }
        
        // 渲染列表
        function renderList(listId, items) {
            const container = document.getElementById(listId);
            if (!items || items.length === 0) {
                container.innerHTML = '<div class="empty-list">列表为空</div>';
            } else {
                container.innerHTML = items.map(item => `
                    <div class="list-item">
                        <span>${item}</span>
                        <button class="remove-btn" onclick="removeItem('${listId}', ${item})">×</button>
                    </div>
                `).join('');
            }
        }
        
        // 更新配置
        async function updateConfig(field, value) {
            try {
                const response = await fetch('/api/config', {
                    method: 'POST',
                    headers: getAuthHeaders(),
                    body: JSON.stringify({ field, value })
                });
                
                if (response.status === 401) {
                    clearToken();
                    showLoginPage();
                    showStatus('登录已过期，请重新登录', 'error');
                    return;
                }
                
                const result = await response.json();
                if (result.success) {
                    config = result.config;
                    renderConfig();
                    showStatus(result.message, 'success');
                } else {
                    showStatus(result.error, 'error');
                }
            } catch (error) {
                showStatus('更新失败: ' + error.message, 'error');
            }
        }
        
        // 添加项目
        function addItem(listId) {
            const inputId = listId === 'group_list' ? 'new_group' : 'new_private';
            const input = document.getElementById(inputId);
            const value = parseInt(input.value);
            
            if (isNaN(value) || value <= 0) {
                showStatus('请输入有效的数字', 'error');
                return;
            }
            
            const list = [...(config[listId] || [])];
            if (list.includes(value)) {
                showStatus('该项已存在', 'error');
                return;
            }
            
            list.push(value);
            updateConfig(listId, list);
            input.value = '';
        }
        
        // 删除项目
        function removeItem(listId, value) {
            const list = (config[listId] || []).filter(item => item !== value);
            updateConfig(listId, list);
        }
        
        // 显示状态提示
        function showStatus(message, type) {
            const status = document.getElementById('status');
            status.textContent = message;
            status.className = 'status show ' + type;
            setTimeout(() => {
                status.className = 'status';
            }, 3000);
        }
        
        // 页面加载时检查认证状态
        checkAuth();
    </script>
</body>
</html>'''

