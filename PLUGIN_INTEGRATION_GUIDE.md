# Document Ingest Service - Plugin Integration Guide (Centralized OAuth)

## Overview

This guide explains how to integrate your WordPress plugin with the Document Ingest Service using the new **centralized OAuth system**. The service now handles all Google OAuth authentication, while your plugin manages the user interface and triggers ingestion jobs.

## 🆕 **What Changed: Centralized OAuth**

### **OLD WAY (BYO-Google):**
```
WordPress Plugin → User sets up Google Cloud → Plugin stores Google credentials → Plugin sends credentials to docingest
```

### **NEW WAY (Centralized OAuth):**
```
WordPress Plugin → Redirects user to docingest → docingest handles Google OAuth → docingest stores tokens → Plugin uses connection_id
```

## Architecture

```
WordPress Plugin → Document Ingest Service → Google Drive → Qdrant Vector DB
     ↓                    ↓                      ↓              ↓
- User Interface      - OAuth Management      - File Access   - Vector Storage
- Connection Flow     - Token Storage         - Downloads     - Similarity Search
- Job Triggers        - Document Processing   - File Listing  - Retrieval
- Q&A Interface       - Embedding Generation  - Search        - Citations
```

## 1. API Key Management

### Getting an API Key

1. **Contact Admin**: Request an API key from the service administrator
2. **Provide Details**: Give your site URL, contact email, and desired plan
3. **Receive Key**: Admin creates key and provides it to you
4. **Store Securely**: Save the API key in WordPress options

### Storing the API Key

```php
// Store API key securely
update_option('docingest_api_key', 'your-api-key-here');
update_option('docingest_api_url', 'https://docingest.industrialwebworks.net/ingestapp/');
```

## 2. API Key Validation

### Critical: Always Validate API Key

Your plugin MUST check the API key status before allowing any functionality:

```php
class DocumentIngestPlugin {
    
    private $api_key;
    private $api_url;
    private $is_active = false;
    
    public function __construct() {
        $this->api_key = get_option('docingest_api_key', '');
        $this->api_url = get_option('docingest_api_url', '') . 'health/validate-key';
        
        // CRITICAL: Check API key on every plugin load
        $this->validate_api_key();
        
        // Schedule hourly validation checks
        $this->schedule_validation_checks();
    }
    
    /**
     * Validate API key with the service
     */
    public function validate_api_key() {
        if (empty($this->api_key)) {
            $this->disable_plugin('No API key configured');
            return false;
        }
        
        $response = wp_remote_get($this->api_url, [
            'headers' => [
                'Authorization' => 'Bearer ' . $this->api_key
            ],
            'timeout' => 10
        ]);
        
        if (is_wp_error($response)) {
            $this->disable_plugin('Cannot connect to Document Ingest Service');
            return false;
        }
        
        $body = wp_remote_retrieve_body($response);
        $data = json_decode($body, true);
        
        if (!$data || !$data['valid']) {
            $this->disable_plugin('Invalid API key');
            return false;
        }
        
        if (!$data['active']) {
            $this->disable_plugin('API key is disabled. Please contact support.');
            return false;
        }
        
        $this->is_active = true;
        $this->show_success_message($data);
        return true;
    }
    
    /**
     * Disable all plugin functionality
     */
    private function disable_plugin($reason) {
        $this->is_active = false;
        
        // Show error message to admin
        add_action('admin_notices', function() use ($reason) {
            echo '<div class="notice notice-error"><p>';
            echo '<strong>Document Ingest Service:</strong> ' . esc_html($reason);
            echo '</p></div>';
        });
        
        // Remove all functionality
        $this->remove_all_hooks();
        $this->disable_cron_jobs();
        $this->hide_admin_menus();
    }
    
    /**
     * Show success message
     */
    private function show_success_message($data) {
        add_action('admin_notices', function() use ($data) {
            echo '<div class="notice notice-success"><p>';
            echo '<strong>Document Ingest Service:</strong> Connected successfully. ';
            echo 'Plan: ' . esc_html($data['plan_type']) . ' | ';
            echo 'Site: ' . esc_html($data['site_name']);
            echo '</p></div>';
        });
    }
}
```

## 3. 🆕 **Google Drive OAuth Flow (Centralized)**

### **Step 1: Initiate OAuth Connection**

```php
/**
 * Start Google Drive OAuth flow
 */
public function start_google_oauth() {
    if (!$this->is_active) {
        wp_die('Document Ingest Service is not available');
    }
    
    $tenant = $this->get_tenant_name();
    $site_id = $this->get_site_id();
    $return_url = admin_url('admin.php?page=docingest-settings&tab=google');
    
    // Redirect to docingest OAuth endpoint
    $oauth_url = add_query_arg([
        'tenant' => $tenant,
        'site_id' => $site_id,
        'return_url' => urlencode($return_url)
    ], 'https://docingest.industrialwebworks.net/ingestapp/oauth/start');
    
    wp_redirect($oauth_url);
    exit;
}
```

### **Step 2: Handle OAuth Callback**

```php
/**
 * Handle OAuth callback from docingest
 */
public function handle_oauth_callback() {
    if (!isset($_GET['ok']) || $_GET['ok'] !== '1') {
        $this->show_error('Google Drive connection failed');
        return;
    }
    
    $connection_id = sanitize_text_field($_GET['connection_id'] ?? '');
    $user_email = sanitize_email($_GET['user_email'] ?? '');
    
    if (empty($connection_id)) {
        $this->show_error('No connection ID received');
        return;
    }
    
    // Store connection ID
    update_option('docingest_connection_id', $connection_id);
    update_option('docingest_user_email', $user_email);
    
    $this->show_success('Google Drive connected successfully!');
}
```

### **Step 3: Test Connection**

```php
/**
 * Test Google Drive connection
 */
public function test_google_connection() {
    if (!$this->is_active) {
        return ['success' => false, 'error' => 'Service not available'];
    }
    
    $connection_id = get_option('docingest_connection_id', '');
    if (empty($connection_id)) {
        return ['success' => false, 'error' => 'No Google Drive connection'];
    }
    
    $response = wp_remote_get($this->api_url . '../oauth/status', [
        'headers' => [
            'Authorization' => 'Bearer ' . $this->api_key
        ],
        'body' => [
            'connection_id' => $connection_id
        ],
        'timeout' => 10
    ]);
    
    if (is_wp_error($response)) {
        return ['success' => false, 'error' => 'Failed to test connection'];
    }
    
    $body = wp_remote_retrieve_body($response);
    $data = json_decode($body, true);
    
    return $data;
}
```

## 4. 🆕 **Google Drive Folder Management**

### **List Available Folders**

```php
/**
 * Get Google Drive folders for user to select
 */
public function get_google_drive_folders() {
    if (!$this->is_active) {
        return ['success' => false, 'error' => 'Service not available'];
    }
    
    $connection_id = get_option('docingest_connection_id', '');
    if (empty($connection_id)) {
        return ['success' => false, 'error' => 'No Google Drive connection'];
    }
    
    $response = wp_remote_get($this->api_url . '../drive/list', [
        'headers' => [
            'Authorization' => 'Bearer ' . $this->api_key
        ],
        'body' => [
            'connection_id' => $connection_id
        ],
        'timeout' => 15
    ]);
    
    if (is_wp_error($response)) {
        return ['success' => false, 'error' => 'Failed to list folders'];
    }
    
    $body = wp_remote_retrieve_body($response);
    $data = json_decode($body, true);
    
    return $data;
}
```

### **List Files in Folder**

```php
/**
 * Get files in a specific Google Drive folder
 */
public function get_google_drive_files($folder_id) {
    if (!$this->is_active) {
        return ['success' => false, 'error' => 'Service not available'];
    }
    
    $connection_id = get_option('docingest_connection_id', '');
    if (empty($connection_id)) {
        return ['success' => false, 'error' => 'No Google Drive connection'];
    }
    
    $response = wp_remote_get($this->api_url . '../drive/files', [
        'headers' => [
            'Authorization' => 'Bearer ' . $this->api_key
        ],
        'body' => [
            'connection_id' => $connection_id,
            'folder_id' => $folder_id
        ],
        'timeout' => 15
    ]);
    
    if (is_wp_error($response)) {
        return ['success' => false, 'error' => 'Failed to list files'];
    }
    
    $body = wp_remote_retrieve_body($response);
    $data = json_decode($body, true);
    
    return $data;
}
```

## 5. 🆕 **Document Ingestion (Updated)**

### **Starting Document Ingestion**

```php
/**
 * Start document ingestion process using connection
 */
public function start_document_ingestion($folder_ids, $reingest = 'incremental') {
    if (!$this->is_active) {
        return ['success' => false, 'error' => 'Service not available'];
    }
    
    $connection_id = get_option('docingest_connection_id', '');
    if (empty($connection_id)) {
        return ['success' => false, 'error' => 'No Google Drive connection'];
    }
    
    $payload = [
        'tenant' => $this->get_tenant_name(),
        'connection_id' => $connection_id,  // 🆕 Use connection_id instead of Google credentials
        'drive' => [
            'folder_ids' => $folder_ids
        ],
        'reingest' => $reingest
    ];
    
    $response = wp_remote_post($this->api_url . '../ingest/', [
        'headers' => [
            'Authorization' => 'Bearer ' . $this->api_key,
            'Content-Type' => 'application/json'
        ],
        'body' => json_encode($payload),
        'timeout' => 30
    ]);
    
    if (is_wp_error($response)) {
        return ['success' => false, 'error' => 'Failed to start ingestion'];
    }
    
    $body = wp_remote_retrieve_body($response);
    $data = json_decode($body, true);
    
    return $data;
}
```

### **Monitoring Ingestion Progress**

```php
/**
 * Check ingestion job progress
 */
public function check_ingestion_progress($job_id) {
    if (!$this->is_active) {
        return ['success' => false, 'error' => 'Service not available'];
    }
    
    $response = wp_remote_get($this->api_url . '../ingest/job/' . $job_id, [
        'headers' => [
            'Authorization' => 'Bearer ' . $this->api_key
        ],
        'timeout' => 10
    ]);
    
    if (is_wp_error($response)) {
        return ['success' => false, 'error' => 'Failed to check progress'];
    }
    
    $body = wp_remote_retrieve_body($response);
    $data = json_decode($body, true);
    
    return $data;
}
```

## 6. 🆕 **Updated User Interface**

### **Settings Page (Updated)**

```php
/**
 * Add settings page to WordPress admin
 */
public function add_admin_menu() {
    if (!$this->is_active) {
        return; // Don't show menu if service is disabled
    }
    
    add_menu_page(
        'Document Ingest',
        'Document Ingest',
        'manage_options',
        'docingest-settings',
        [$this, 'render_settings_page']
    );
}

/**
 * Render settings page
 */
public function render_settings_page() {
    if (!$this->is_active) {
        echo '<div class="notice notice-error"><p>Document Ingest Service is not available</p></div>';
        return;
    }
    
    $connection_id = get_option('docingest_connection_id', '');
    $user_email = get_option('docingest_user_email', '');
    $folder_ids = get_option('docingest_folder_ids', []);
    
    ?>
    <div class="wrap">
        <h1>Document Ingest Settings</h1>
        
        <!-- API Key Section -->
        <form method="post" action="options.php">
            <?php settings_fields('docingest_settings'); ?>
            
            <table class="form-table">
                <tr>
                    <th scope="row">API Key</th>
                    <td>
                        <input type="text" name="docingest_api_key" 
                               value="<?php echo esc_attr(get_option('docingest_api_key')); ?>" 
                               class="regular-text" />
                        <p class="description">Your Document Ingest Service API key</p>
                    </td>
                </tr>
            </table>
            
            <?php submit_button(); ?>
        </form>
        
        <!-- Google Drive Connection Section -->
        <h2>Google Drive Connection</h2>
        
        <?php if (empty($connection_id)): ?>
            <div class="notice notice-warning">
                <p>No Google Drive connection found. <a href="<?php echo admin_url('admin.php?page=docingest-settings&action=connect_google'); ?>" class="button button-primary">Connect Google Drive</a></p>
            </div>
        <?php else: ?>
            <div class="notice notice-success">
                <p><strong>Connected:</strong> <?php echo esc_html($user_email); ?></p>
                <p><strong>Connection ID:</strong> <?php echo esc_html($connection_id); ?></p>
                <a href="<?php echo admin_url('admin.php?page=docingest-settings&action=reconnect_google'); ?>" class="button">Reconnect</a>
                <a href="<?php echo admin_url('admin.php?page=docingest-settings&action=test_connection'); ?>" class="button">Test Connection</a>
            </div>
        <?php endif; ?>
        
        <!-- Folder Selection -->
        <?php if (!empty($connection_id)): ?>
            <h2>Select Folders to Ingest</h2>
            <div id="folder-selection">
                <button id="load-folders" class="button">Load Google Drive Folders</button>
                <div id="folders-list"></div>
            </div>
            
            <h2>Document Ingestion</h2>
            <button id="start-ingestion" class="button button-primary" <?php echo empty($folder_ids) ? 'disabled' : ''; ?>>Start Document Ingestion</button>
            <div id="ingestion-status"></div>
        <?php endif; ?>
    </div>
    
    <script>
    // Load folders when button is clicked
    document.getElementById('load-folders')?.addEventListener('click', function() {
        fetch('<?php echo admin_url('admin-ajax.php'); ?>', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: 'action=docingest_load_folders'
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                displayFolders(data.folders);
            } else {
                alert('Error: ' + data.error);
            }
        });
    });
    
    function displayFolders(folders) {
        const container = document.getElementById('folders-list');
        container.innerHTML = '<h3>Select Folders:</h3>';
        
        folders.forEach(folder => {
            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.value = folder.id;
            checkbox.id = 'folder-' + folder.id;
            
            const label = document.createElement('label');
            label.htmlFor = 'folder-' + folder.id;
            label.textContent = folder.name;
            
            const div = document.createElement('div');
            div.appendChild(checkbox);
            div.appendChild(label);
            container.appendChild(div);
        });
        
        // Add save button
        const saveButton = document.createElement('button');
        saveButton.textContent = 'Save Selected Folders';
        saveButton.className = 'button button-primary';
        saveButton.onclick = saveSelectedFolders;
        container.appendChild(saveButton);
    }
    
    function saveSelectedFolders() {
        const selectedFolders = Array.from(document.querySelectorAll('input[type="checkbox"]:checked'))
            .map(cb => cb.value);
        
        fetch('<?php echo admin_url('admin-ajax.php'); ?>', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: 'action=docingest_save_folders&folders=' + encodeURIComponent(JSON.stringify(selectedFolders))
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert('Folders saved successfully!');
                document.getElementById('start-ingestion').disabled = false;
            } else {
                alert('Error: ' + data.error);
            }
        });
    }
    </script>
    <?php
}
```

## 7. 🆕 **AJAX Handlers**

### **Load Folders AJAX**

```php
/**
 * AJAX handler to load Google Drive folders
 */
public function ajax_load_folders() {
    check_ajax_referer('docingest_nonce', 'nonce');
    
    if (!current_user_can('manage_options')) {
        wp_die('Insufficient permissions');
    }
    
    $result = $this->get_google_drive_folders();
    
    if ($result['success']) {
        wp_send_json_success(['folders' => $result['folders']]);
    } else {
        wp_send_json_error(['error' => $result['error']]);
    }
}

/**
 * AJAX handler to save selected folders
 */
public function ajax_save_folders() {
    check_ajax_referer('docingest_nonce', 'nonce');
    
    if (!current_user_can('manage_options')) {
        wp_die('Insufficient permissions');
    }
    
    $folders = json_decode(stripslashes($_POST['folders']), true);
    
    if (is_array($folders)) {
        update_option('docingest_folder_ids', $folders);
        wp_send_json_success(['message' => 'Folders saved successfully']);
    } else {
        wp_send_json_error(['error' => 'Invalid folder data']);
    }
}

/**
 * AJAX handler to start ingestion
 */
public function ajax_start_ingestion() {
    check_ajax_referer('docingest_nonce', 'nonce');
    
    if (!current_user_can('manage_options')) {
        wp_die('Insufficient permissions');
    }
    
    $folder_ids = get_option('docingest_folder_ids', []);
    $reingest = sanitize_text_field($_POST['reingest'] ?? 'incremental');
    
    if (empty($folder_ids)) {
        wp_send_json_error(['error' => 'No folders selected']);
    }
    
    $result = $this->start_document_ingestion($folder_ids, $reingest);
    
    if ($result['success']) {
        wp_send_json_success(['job_id' => $result['job_id']]);
    } else {
        wp_send_json_error(['error' => $result['error']]);
    }
}
```

## 8. 🆕 **Updated Cron Job Management**

### **Scheduled Ingestion (Updated)**

```php
/**
 * Schedule document ingestion based on user settings
 */
public function schedule_ingestion() {
    if (!$this->is_active) {
        return;
    }
    
    $frequency = get_option('docingest_frequency', 'never');
    
    // Clear existing schedules
    wp_clear_scheduled_hook('docingest_scheduled_ingest');
    
    if ($frequency !== 'never') {
        $interval = $this->get_cron_interval($frequency);
        wp_schedule_event(time(), $interval, 'docingest_scheduled_ingest');
        
        add_action('docingest_scheduled_ingest', [$this, 'run_scheduled_ingestion']);
    }
}

/**
 * Run scheduled ingestion
 */
public function run_scheduled_ingestion() {
    if (!$this->is_active) {
        return;
    }
    
    $connection_id = get_option('docingest_connection_id', '');
    $folder_ids = get_option('docingest_folder_ids', []);
    
    if (empty($connection_id) || empty($folder_ids)) {
        error_log('Document Ingest: Missing Google Drive connection or folder IDs');
        return;
    }
    
    $result = $this->start_document_ingestion($folder_ids, 'incremental');
    
    if ($result['success']) {
        error_log('Document Ingest: Scheduled ingestion started successfully');
    } else {
        error_log('Document Ingest: Scheduled ingestion failed: ' . $result['error']);
    }
}
```

## 9. 🆕 **API Endpoints Reference (Updated)**

### **Available Endpoints**

| Endpoint | Method | Purpose | Authentication |
|----------|--------|---------|----------------|
| `/health/` | GET | Service health check | None |
| `/health/validate-key` | GET | Validate API key | Bearer Token |
| `/oauth/start` | GET | Start OAuth flow | None |
| `/oauth/callback` | GET | Handle OAuth callback | None |
| `/oauth/status` | GET | Check connection status | Bearer Token |
| `/drive/list` | GET | List Drive folders | Bearer Token |
| `/drive/files` | GET | List Drive files | Bearer Token |
| `/ingest/` | POST | Start document ingestion | Bearer Token |
| `/ingest/job/{job_id}` | GET | Check ingestion progress | Bearer Token |

### **Example API Calls**

```php
// Health check
$response = wp_remote_get('https://docingest.industrialwebworks.net/ingestapp/health/');

// Validate API key
$response = wp_remote_get('https://docingest.industrialwebworks.net/ingestapp/health/validate-key', [
    'headers' => ['Authorization' => 'Bearer your-api-key']
]);

// Start OAuth flow
$oauth_url = add_query_arg([
    'tenant' => 'your-tenant',
    'site_id' => 'your-site-id',
    'return_url' => 'https://yoursite.com/callback'
], 'https://docingest.industrialwebworks.net/ingestapp/oauth/start');

// Start ingestion (NEW WAY)
$response = wp_remote_post('https://docingest.industrialwebworks.net/ingestapp/ingest/', [
    'headers' => [
        'Authorization' => 'Bearer your-api-key',
        'Content-Type' => 'application/json'
    ],
    'body' => json_encode([
        'tenant' => 'your-tenant',
        'connection_id' => 'conn_abc123',  // 🆕 Use connection_id
        'drive' => [
            'folder_ids' => ['folder1', 'folder2']
        ],
        'reingest' => 'incremental'
    ])
]);
```

## 10. 🆕 **Migration from BYO-Google**

### **What to Remove from Your Plugin:**

1. **Google OAuth handling code** - docingest now handles this
2. **Google credentials storage** - no longer needed
3. **Google Cloud project setup instructions** - users don't need this anymore

### **What to Add to Your Plugin:**

1. **OAuth initiation** - redirect to docingest OAuth endpoint
2. **OAuth callback handling** - process connection_id from docingest
3. **Connection management** - store and use connection_id
4. **Folder selection UI** - let users pick folders from their Drive

### **Migration Steps:**

```php
/**
 * Migrate from BYO-Google to Centralized OAuth
 */
public function migrate_to_centralized_oauth() {
    // Remove old Google credentials
    delete_option('docingest_google_client_id');
    delete_option('docingest_google_client_secret');
    delete_option('docingest_google_refresh_token');
    
    // Clear any existing connections
    delete_option('docingest_connection_id');
    delete_option('docingest_user_email');
    
    // Show migration notice
    add_action('admin_notices', function() {
        echo '<div class="notice notice-info"><p>';
        echo '<strong>Document Ingest Service:</strong> ';
        echo 'Please reconnect your Google Drive account using the new centralized OAuth system.';
        echo '</p></div>';
    });
}
```

## 11. **Complete Plugin Structure (Updated)**

### **Main Plugin File**

```php
<?php
/**
 * Plugin Name: Document Ingest Integration (Centralized OAuth)
 * Description: Integrates with Document Ingest Service using centralized OAuth
 * Version: 2.0.0
 */

// Prevent direct access
if (!defined('ABSPATH')) {
    exit;
}

// Include the main plugin class
require_once plugin_dir_path(__FILE__) . 'includes/class-document-ingest-plugin.php';

// Initialize the plugin
function docingest_init() {
    new DocumentIngestPlugin();
}
add_action('plugins_loaded', 'docingest_init');

// Handle OAuth callback
add_action('init', function() {
    if (isset($_GET['page']) && $_GET['page'] === 'docingest-settings') {
        if (isset($_GET['ok']) && $_GET['ok'] === '1') {
            // Handle OAuth success callback
            $plugin = new DocumentIngestPlugin();
            $plugin->handle_oauth_callback();
        }
    }
});

// AJAX handlers
add_action('wp_ajax_docingest_load_folders', function() {
    $plugin = new DocumentIngestPlugin();
    $plugin->ajax_load_folders();
});

add_action('wp_ajax_docingest_save_folders', function() {
    $plugin = new DocumentIngestPlugin();
    $plugin->ajax_save_folders();
});

add_action('wp_ajax_docingest_start_ingestion', function() {
    $plugin = new DocumentIngestPlugin();
    $plugin->ajax_start_ingestion();
});

// Activation hook
register_activation_hook(__FILE__, function() {
    // Schedule validation checks
    wp_schedule_event(time(), 'hourly', 'docingest_validate_key');
});

// Deactivation hook
register_deactivation_hook(__FILE__, function() {
    // Clear scheduled events
    wp_clear_scheduled_hook('docingest_validate_key');
    wp_clear_scheduled_hook('docingest_scheduled_ingest');
});
```

## 12. **Summary of Changes**

### **🆕 What's New:**
1. **Centralized OAuth** - docingest handles all Google authentication
2. **Connection-based system** - use connection_id instead of credentials
3. **Simplified user experience** - no Google Cloud setup required
4. **Better security** - encrypted token storage
5. **Easier support** - no user Google Cloud issues

### **🔄 What Changed:**
1. **OAuth flow** - redirect to docingest instead of handling locally
2. **API calls** - use connection_id instead of Google credentials
3. **User interface** - add folder selection and connection management
4. **Storage** - store connection_id instead of refresh tokens

### **✅ Benefits:**
1. **Users don't need Google Cloud accounts**
2. **Centralized token management**
3. **Better security with encrypted storage**
4. **Easier support and troubleshooting**
5. **Scalable architecture**

**The plugin should now work with the centralized OAuth system!** 🚀