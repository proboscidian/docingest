<?php
/**
 * WordPress Plugin - API Key Validation Example
 * 
 * This shows how your WordPress plugin should check if its API key is still active
 * before allowing any document ingestion or vector database access.
 */

class DocumentIngestPlugin {
    
    private $api_key;
    private $api_url;
    private $is_active;
    
    public function __construct() {
        $this->api_key = get_option('docingest_api_key', '');
        $this->api_url = 'https://docingest.industrialwebworks.net/ingestapp/health/validate-key';
        $this->is_active = false;
        
        // Check API key status on plugin initialization
        $this->check_api_key_status();
    }
    
    /**
     * Check if API key is valid and active
     */
    public function check_api_key_status() {
        if (empty($this->api_key)) {
            $this->is_active = false;
            $this->show_api_key_error('No API key configured');
            return false;
        }
        
        $response = wp_remote_get($this->api_url, [
            'headers' => [
                'Authorization' => 'Bearer ' . $this->api_key
            ],
            'timeout' => 10
        ]);
        
        if (is_wp_error($response)) {
            $this->is_active = false;
            $this->show_api_key_error('Failed to connect to Document Ingest Service');
            return false;
        }
        
        $body = wp_remote_retrieve_body($response);
        $data = json_decode($body, true);
        
        if (!$data || !$data['valid']) {
            $this->is_active = false;
            $this->show_api_key_error('Invalid API key');
            return false;
        }
        
        if (!$data['active']) {
            $this->is_active = false;
            $this->show_api_key_error('API key is disabled. Please contact support.');
            return false;
        }
        
        $this->is_active = true;
        $this->show_api_key_success($data);
        return true;
    }
    
    /**
     * Show error message when API key is invalid/disabled
     */
    private function show_api_key_error($message) {
        add_action('admin_notices', function() use ($message) {
            echo '<div class="notice notice-error"><p>';
            echo '<strong>Document Ingest Service:</strong> ' . esc_html($message);
            echo '</p></div>';
        });
        
        // Disable all plugin functionality
        $this->disable_plugin_features();
    }
    
    /**
     * Show success message when API key is valid
     */
    private function show_api_key_success($data) {
        add_action('admin_notices', function() use ($data) {
            echo '<div class="notice notice-success"><p>';
            echo '<strong>Document Ingest Service:</strong> Connected successfully. ';
            echo 'Plan: ' . esc_html($data['plan_type']) . ' | ';
            echo 'Site: ' . esc_html($data['site_name']);
            echo '</p></div>';
        });
    }
    
    /**
     * Disable all plugin features when API key is invalid/disabled
     */
    private function disable_plugin_features() {
        // Remove all hooks that would access vector database
        remove_action('wp_ajax_docingest_search', [$this, 'handle_search']);
        remove_action('wp_ajax_docingest_ingest', [$this, 'handle_ingest']);
        
        // Disable cron jobs
        wp_clear_scheduled_hook('docingest_scheduled_ingest');
        
        // Hide admin menu items
        add_action('admin_menu', function() {
            remove_menu_page('docingest-settings');
        });
    }
    
    /**
     * Only allow document ingestion if API key is active
     */
    public function handle_ingest() {
        if (!$this->is_active) {
            wp_die('Document Ingest Service is not available. Please check your API key.');
        }
        
        // Proceed with ingestion...
        $this->perform_document_ingest();
    }
    
    /**
     * Only allow vector database search if API key is active
     */
    public function handle_search() {
        if (!$this->is_active) {
            wp_die('Document Ingest Service is not available. Please check your API key.');
        }
        
        // Proceed with search...
        $this->perform_vector_search();
    }
    
    /**
     * Schedule periodic API key checks
     */
    public function schedule_api_key_checks() {
        if (!wp_next_scheduled('docingest_check_api_key')) {
            wp_schedule_event(time(), 'hourly', 'docingest_check_api_key');
        }
        
        add_action('docingest_check_api_key', [$this, 'check_api_key_status']);
    }
}

// Initialize the plugin
$docingest_plugin = new DocumentIngestPlugin();

/**
 * Example of how to use in your plugin:
 * 
 * 1. Check API key status on plugin activation
 * 2. Disable all features if key is invalid/disabled
 * 3. Show clear error messages to admin
 * 4. Schedule periodic checks (hourly)
 * 5. Block all vector DB access when disabled
 */
